"""GitHub issue comment posting support for ArtifactForge."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


VALID_MARKER_STATUSES = frozenset(
    {"done", "reassign_required", "authentication_blocked"}
)


@dataclass(frozen=True)
class CommentPostResult:
    repo: str
    issue_number: int
    body: str
    args: Tuple[str, ...]
    posted: bool
    skipped: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and (self.posted or self.skipped)


class SubprocessGitHubCommentRunner:
    def __init__(self, *, gh_bin: str = "gh") -> None:
        self.gh_bin = gh_bin

    def issue_comment(
        self,
        *,
        repo: str,
        issue_number: int,
        body: str,
    ) -> CommentPostResult:
        args = issue_comment_args(repo=repo, issue_number=issue_number, gh_bin=self.gh_bin)
        completed = subprocess.run(
            list(args),
            input=body,
            text=True,
            capture_output=True,
            check=False,
        )
        return CommentPostResult(
            repo=repo,
            issue_number=issue_number,
            body=body,
            args=args,
            posted=completed.returncode == 0,
            skipped=False,
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            error=None if completed.returncode == 0 else completed.stderr.strip() or None,
        )


def issue_comment_args(
    *,
    repo: str,
    issue_number: int,
    gh_bin: str = "gh",
) -> Tuple[str, ...]:
    return (
        gh_bin,
        "issue",
        "comment",
        str(issue_number),
        "--repo",
        repo,
        "--body-file",
        "-",
    )


def marker_footer(
    *,
    session_id: str,
    trigger_fingerprint: str,
    status: str,
) -> str:
    if status not in VALID_MARKER_STATUSES:
        raise ValueError(f"invalid marker status: {status}")
    payload = {
        "thread_id": session_id,
        "trigger_fingerprint": trigger_fingerprint,
        "status": status,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"<!-- codex-agent-v1: {encoded} -->"


def append_marker_footer(
    body: str,
    *,
    session_id: str,
    trigger_fingerprint: str,
    status: str,
) -> str:
    return f"{body.rstrip()}\n\n{marker_footer(session_id=session_id, trigger_fingerprint=trigger_fingerprint, status=status)}\n"


def post_issue_comment(
    *,
    repo: str,
    issue_number: int,
    body: str,
    post_comments: bool = False,
    runner: Any = None,
    gh_bin: str = "gh",
) -> CommentPostResult:
    args = issue_comment_args(repo=repo, issue_number=issue_number, gh_bin=gh_bin)
    if not post_comments:
        return CommentPostResult(
            repo=repo,
            issue_number=issue_number,
            body=body,
            args=args,
            posted=False,
            skipped=True,
        )
    resolved_runner = runner or SubprocessGitHubCommentRunner(gh_bin=gh_bin)
    return resolved_runner.issue_comment(repo=repo, issue_number=issue_number, body=body)


def planned_comment_payloads(results: Sequence[CommentPostResult]) -> List[Dict[str, object]]:
    return [
        {
            "repo": result.repo,
            "issue_number": result.issue_number,
            "body": result.body,
            "command": list(result.args),
            "posted": result.posted,
            "skipped": result.skipped,
            "error": result.error,
        }
        for result in results
    ]
