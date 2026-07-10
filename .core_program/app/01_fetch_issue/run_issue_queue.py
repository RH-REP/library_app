#!/usr/bin/env python3
"""Fetch GitHub issues, reconcile pending work, and build queue files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


CORE_DIR = Path(__file__).resolve().parents[2]
LIB_DIR = CORE_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.github_client import (  # noqa: E402
    GitHubRepoInferenceError,
    fetch_open_issues,
    infer_repo_from_origin_remote,
    read_issue_snapshots,
    write_issue_snapshots,
)
from artifactforge_dispatch_v1.lifecycle import (  # noqa: E402
    lifecycle_summary_to_dict,
    reconcile_pending_from_issues,
)
from artifactforge_dispatch_v1.queueing import (  # noqa: E402
    build_queue_records,
    write_queue_files,
)
from artifactforge_dispatch_v1.dispatch import (  # noqa: E402
    bootstrap_session_router as _dispatch_bootstrap_session_router,
)


REPO_ROOT = CORE_DIR.parent
DEFAULT_DATA_PATH = CORE_DIR / "app" / "01_fetch_issue" / "data" / "open_issues.json"
DEFAULT_QUEUE_DIR = CORE_DIR / "queue"
DEFAULT_PENDING_DIR = CORE_DIR / "pending"
DEFAULT_ARCHIVE_DIR = CORE_DIR / "archive"
DEFAULT_ASSIGNMENT_STATE_PATH = CORE_DIR / "assignment_state.json"
DEFAULT_FIXTURE_ISSUES_PATH = CORE_DIR / "fixtures" / "dry_run" / "issues.json"
DEFAULT_FIXTURE_ASSIGNMENT_STATE_PATH = (
    CORE_DIR / "fixtures" / "dry_run" / "assignment_state.json"
)
PLANNED_ROUTER_SESSION_ID = "ROUTER_BOOTSTRAP_PLANNED"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub issues and create ArtifactForge queue files."
    )
    parser.add_argument("--repo", help="GitHub repository, e.g. OWNER/REPO")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--gh-bin", default="gh")
    parser.add_argument("--issues", help="Read issue snapshots from JSON instead of GitHub")
    parser.add_argument("--output", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--queue-dir", default=str(DEFAULT_QUEUE_DIR))
    parser.add_argument("--pending-dir", default=str(DEFAULT_PENDING_DIR))
    parser.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR))
    parser.add_argument(
        "--assignment-state",
        default=str(DEFAULT_ASSIGNMENT_STATE_PATH),
        help="ArtifactForge assignment_state.json path",
    )
    parser.add_argument(
        "--router-session-id",
        help="Router session ID to use when assignment_state is missing or unset",
    )
    parser.add_argument("--dry-run", action="store_true", help="plan without writing or moving files")
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing queue files")
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    return parser


def load_assignment_state(
    path: str | Path,
    *,
    router_session_id: str | None,
    dry_run: bool,
    repo_is_fixture: bool,
) -> dict[str, Any]:
    target = Path(path)
    if target.exists():
        payload = json.loads(target.read_text(encoding="utf-8"))
    elif dry_run and repo_is_fixture and DEFAULT_FIXTURE_ASSIGNMENT_STATE_PATH.exists():
        payload = json.loads(DEFAULT_FIXTURE_ASSIGNMENT_STATE_PATH.read_text(encoding="utf-8"))
    else:
        payload = {
            "schema_version": 1,
            "router_session_id": router_session_id,
            "next_sub_artifact_number": 1,
            "assignments": [],
        }
    payload.setdefault("schema_version", 1)
    payload.setdefault("next_sub_artifact_number", 1)
    payload.setdefault("assignments", [])
    if router_session_id:
        payload["router_session_id"] = router_session_id
    return payload


def write_assignment_state(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def router_session_id_from_state(assignment_state: dict[str, Any]) -> str | None:
    value = assignment_state.get("router_session_id")
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def router_session_id_from_bootstrap_result(result: Any) -> str:
    if isinstance(result, str):
        value = result
    elif isinstance(result, dict):
        value = result.get("router_session_id") or result.get("session_id")
    else:
        value = (
            getattr(result, "router_session_id", None)
            or getattr(result, "session_id", None)
        )
    session_id = str(value or "").strip()
    if not session_id:
        raise RuntimeError("router bootstrap did not return a router session ID")
    return session_id


def bootstrap_session_router(*, assignment_state_path: str | Path, repo_dir: str | Path) -> Any:
    return _dispatch_bootstrap_session_router(
        assignment_state_path=assignment_state_path,
        repo_dir=repo_dir,
    )


def router_bootstrap_failed_message(
    exc: Exception,
    *,
    assignment_state_path: str | Path,
) -> str:
    return "\n".join(
        [
            "router bootstrap failed: {0}".format(exc),
            "Start or resume the Session_router manually, then rerun with:",
            "  --router-session-id SESSION_ID",
            "The provided SESSION_ID will be saved to assignment_state at {0}.".format(
                assignment_state_path
            ),
        ]
    )


def ensure_router_session_id(
    assignment_state: dict[str, Any],
    assignment_state_path: str | Path,
    *,
    router_session_id: str | None,
    dry_run: bool,
    repo_is_fixture: bool,
) -> str:
    if router_session_id_from_state(assignment_state):
        if router_session_id and not dry_run:
            write_assignment_state(assignment_state_path, assignment_state)
        return "not_started"

    if dry_run:
        assignment_state["router_session_id"] = PLANNED_ROUTER_SESSION_ID
        return "not_started" if repo_is_fixture else "router_bootstrap_planned"

    try:
        bootstrap_result = bootstrap_session_router(
            assignment_state_path=assignment_state_path,
            repo_dir=REPO_ROOT,
        )
        assignment_state["router_session_id"] = router_session_id_from_bootstrap_result(
            bootstrap_result
        )
    except Exception as exc:
        raise SystemExit(
            router_bootstrap_failed_message(
                exc,
                assignment_state_path=assignment_state_path,
            )
        )
    write_assignment_state(assignment_state_path, assignment_state)
    return "router_bootstrap_started"


def queue_results_to_dict(results: Iterable[Any]) -> dict[str, object]:
    result_tuple = tuple(results)
    return {
        "queue_result_count": len(result_tuple),
        "written_count": sum(1 for result in result_tuple if result.written),
        "planned_count": sum(1 for result in result_tuple if not result.written),
        "items": [
            {
                "path": str(result.plan.path),
                "action": result.plan.action,
                "written": result.written,
                "reason": result.reason,
                "issue_number": result.plan.record.issue_number,
                "prompt_kind": result.plan.record.prompt_kind,
                "target_session_id": result.plan.record.target_session_id,
                "trigger_fingerprint": result.plan.record.trigger_fingerprint,
                "sub_artifact_path": result.plan.record.sub_artifact_path,
                "reassign_required": result.plan.record.reassign_required,
            }
            for result in result_tuple
        ],
    }


def issue_count_summary(issues: Iterable[Any]) -> dict[str, int]:
    issue_tuple = tuple(issues)
    return {
        "issues": len(issue_tuple),
        "comments": sum(len(issue.comments) for issue in issue_tuple),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_is_fixture = False
    snapshot_written = False
    if args.issues:
        issues = read_issue_snapshots(args.issues)
        issue_source = args.issues
        repo = args.repo or "fixture"
    elif args.dry_run and not args.repo:
        issues = read_issue_snapshots(DEFAULT_FIXTURE_ISSUES_PATH)
        issue_source = str(DEFAULT_FIXTURE_ISSUES_PATH)
        repo = "fixture"
        repo_is_fixture = True
    else:
        if args.repo:
            repo = args.repo
        else:
            try:
                repo = infer_repo_from_origin_remote(REPO_ROOT)
            except GitHubRepoInferenceError as exc:
                raise SystemExit(str(exc))
        issues = fetch_open_issues(repo, limit=args.limit, gh_bin=args.gh_bin)
        issue_source = "github"
        if not args.dry_run:
            write_issue_snapshots(args.output, issues, repo=repo)
            snapshot_written = True

    assignment_state = load_assignment_state(
        args.assignment_state,
        router_session_id=args.router_session_id,
        dry_run=args.dry_run,
        repo_is_fixture=repo_is_fixture,
    )
    codex_sessions_effect = ensure_router_session_id(
        assignment_state,
        args.assignment_state,
        router_session_id=args.router_session_id,
        dry_run=args.dry_run,
        repo_is_fixture=repo_is_fixture,
    )
    lifecycle = reconcile_pending_from_issues(
        issues,
        pending_dir=args.pending_dir,
        archive_dir=args.archive_dir,
        dry_run=args.dry_run,
    )
    records = build_queue_records(
        issues,
        assignment_state,
        pending_dir=args.pending_dir,
        archive_dir=args.archive_dir,
    )
    queue_results = write_queue_files(
        records,
        queue_dir=args.queue_dir,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    )
    summary = {
        "schema_version": 1,
        "step": "fetch_issue_queue",
        "mode": "dry-run" if args.dry_run else "real",
        "repo": repo,
        "issue_source": issue_source,
        "snapshot_output": str(Path(args.output)) if snapshot_written else None,
        "counts": issue_count_summary(issues),
        "archive": lifecycle_summary_to_dict(lifecycle),
        "queue": queue_results_to_dict(queue_results),
        "effects": {
            "github_fetch": "called" if issue_source == "github" else "not_called",
            "snapshot_file": "written" if snapshot_written else "not_written",
            "queue_files": "not_written" if args.dry_run else "written",
            "pending_archive_files": "not_moved" if args.dry_run else "moved_when_done",
            "github_comments": "not_posted",
            "codex_sessions": codex_sessions_effect,
        },
    }
    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
