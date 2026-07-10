"""GitHub issue fetch helpers for ArtifactForge dispatch."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse

from .models import IssueComment, IssueSnapshot


RunCommand = Callable[[Sequence[str]], Any]


class GitHubFetchError(RuntimeError):
    pass


class GitHubRepoInferenceError(RuntimeError):
    pass


def _default_runner(args: Sequence[str]) -> Any:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_repo_name(repo: str) -> str:
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("repo must be OWNER/REPO")
    return repo


def _repo_from_remote_path(path: str) -> Optional[str]:
    repo_path = unquote(path.strip().strip("/"))
    if repo_path.endswith(".git"):
        repo_path = repo_path[:-4]
    repo_path = repo_path.strip("/")
    parts = repo_path.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    try:
        return validate_repo_name(f"{parts[0]}/{parts[1]}")
    except ValueError:
        return None


def parse_github_repo_from_remote_url(remote_url: str) -> Optional[str]:
    value = remote_url.strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme in ("http", "https", "ssh", "git"):
        if (parsed.hostname or "").lower() != "github.com":
            return None
        return _repo_from_remote_path(parsed.path)

    scp_match = re.match(r"^(?:[^@]+@)?github\.com:(.+)$", value)
    if scp_match:
        return _repo_from_remote_path(scp_match.group(1))
    return None


def infer_repo_from_origin_remote(
    repo_dir: str | Path,
    *,
    git_bin: str = "git",
    runner: RunCommand = _default_runner,
) -> str:
    result = runner([git_bin, "-C", str(repo_dir), "remote", "get-url", "origin"])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        message = (
            "could not infer GitHub repository because origin remote could not be read; "
            "pass --repo OWNER/REPO"
        )
        if detail:
            message = f"{message} ({detail})"
        raise GitHubRepoInferenceError(message)

    repo = parse_github_repo_from_remote_url(result.stdout)
    if repo is None:
        raise GitHubRepoInferenceError(
            "could not infer GitHub repository from origin remote; "
            "expected a GitHub URL like https://github.com/OWNER/REPO.git "
            "or git@github.com:OWNER/REPO.git, or pass --repo OWNER/REPO"
        )
    return repo


def _author_login(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        login = value.get("login")
        return str(login) if login is not None else None
    if value is None:
        return None
    return str(value)


def _normalize_state(value: Optional[str]) -> str:
    return (value or "").lower()


def issue_snapshot_from_gh_json(payload: Dict[str, Any]) -> IssueSnapshot:
    comments: List[IssueComment] = []
    for comment in payload.get("comments") or []:
        comment_id = comment.get("id") or comment.get("databaseId") or comment.get("node_id")
        comments.append(
            IssueComment(
                comment_id=str(comment_id),
                author=_author_login(comment.get("author")),
                body=str(comment.get("body") or ""),
                created_at=str(comment.get("createdAt") or comment.get("created_at") or ""),
                updated_at=comment.get("updatedAt") or comment.get("updated_at"),
                url=comment.get("url"),
            )
        )
    return IssueSnapshot(
        issue_number=int(payload["number"]),
        issue_state=_normalize_state(payload.get("state")),
        issue_url=str(payload.get("url") or ""),
        title=str(payload.get("title") or ""),
        body=str(payload.get("body") or ""),
        created_at=payload.get("createdAt") or payload.get("created_at"),
        updated_at=payload.get("updatedAt") or payload.get("updated_at"),
        comments=tuple(comments),
    )


def _issue_snapshot_from_any_json(payload: Dict[str, Any]) -> IssueSnapshot:
    if "issue_number" not in payload:
        return issue_snapshot_from_gh_json(payload)
    comments = tuple(
        IssueComment(
            comment_id=str(comment.get("comment_id") or comment.get("id")),
            author=comment.get("author"),
            body=str(comment.get("body") or ""),
            created_at=str(comment.get("created_at") or comment.get("createdAt") or ""),
            updated_at=comment.get("updated_at") or comment.get("updatedAt"),
            url=comment.get("url"),
        )
        for comment in payload.get("comments") or []
    )
    return IssueSnapshot(
        issue_number=int(payload["issue_number"]),
        issue_state=str(payload.get("issue_state") or "").lower(),
        issue_url=str(payload.get("issue_url") or ""),
        title=str(payload.get("title") or ""),
        body=str(payload.get("body") or ""),
        created_at=payload.get("created_at") or payload.get("createdAt"),
        updated_at=payload.get("updated_at") or payload.get("updatedAt"),
        comments=comments,
    )


def fetch_open_issues_with_gh(
    repo: str,
    *,
    limit: int = 100,
    gh_bin: str = "gh",
    runner: RunCommand = _default_runner,
) -> Tuple[IssueSnapshot, ...]:
    validate_repo_name(repo)
    list_result = runner(
        [
            gh_bin,
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "number",
        ]
    )
    if list_result.returncode != 0:
        raise GitHubFetchError(list_result.stderr.strip() or list_result.stdout.strip())
    try:
        issue_refs = json.loads(list_result.stdout)
    except json.JSONDecodeError as exc:
        raise GitHubFetchError(f"failed to parse gh issue list JSON: {exc}") from exc

    snapshots: List[IssueSnapshot] = []
    for issue_ref in issue_refs:
        number = int(issue_ref["number"])
        view_result = runner(
            [
                gh_bin,
                "issue",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "number,state,title,url,body,createdAt,updatedAt,comments",
            ]
        )
        if view_result.returncode != 0:
            raise GitHubFetchError(view_result.stderr.strip() or view_result.stdout.strip())
        try:
            payload = json.loads(view_result.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubFetchError(
                f"failed to parse gh issue view JSON for #{number}: {exc}"
            ) from exc
        snapshot = issue_snapshot_from_gh_json(payload)
        if snapshot.issue_state == "open":
            snapshots.append(snapshot)
    return tuple(snapshots)


def fetch_open_issues(
    repo: str,
    *,
    limit: int = 100,
    gh_bin: str = "gh",
    runner: RunCommand = _default_runner,
) -> Tuple[IssueSnapshot, ...]:
    return fetch_open_issues_with_gh(
        repo,
        limit=limit,
        gh_bin=gh_bin,
        runner=runner,
    )


def read_issue_snapshots(path: str | Path) -> Tuple[IssueSnapshot, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        values = payload.get("issues", [])
    else:
        values = payload
    if not isinstance(values, list):
        raise ValueError("issue snapshot file must be a list or an object with an issues list")
    return tuple(_issue_snapshot_from_any_json(value) for value in values)


def load_open_issues_snapshot(path: str | Path) -> Tuple[IssueSnapshot, ...]:
    return read_issue_snapshots(path)


def write_issue_snapshots(
    path: str | Path,
    issues: Iterable[IssueSnapshot],
    *,
    repo: str,
    fetched_at: Optional[str] = None,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    issue_list = tuple(issues)
    payload = {
        "schema_version": 1,
        "repo": repo,
        "fetched_at": fetched_at or _utc_now_iso(),
        "issues": [asdict(issue) for issue in issue_list],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_open_issues_snapshot(
    issues: Iterable[IssueSnapshot],
    *,
    repo: str,
    path: str | Path,
    fetched_at: Optional[str] = None,
) -> Path:
    return write_issue_snapshots(path, issues, repo=repo, fetched_at=fetched_at)
