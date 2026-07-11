#!/usr/bin/env python3
"""Fetch GitHub issues, reconcile pending work, and build queue files."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any, Iterable


CORE_DIR = Path(__file__).resolve().parents[2]
LIB_DIR = CORE_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.github_client import (  # noqa: E402
    GitHubFetchError,
    GitHubRepoInferenceError,
    fetch_issues_by_number,
    fetch_open_issues,
    infer_repo_from_origin_remote,
    read_issue_snapshots,
    write_issue_snapshots,
)
from artifactforge_dispatch_v1.lifecycle import (  # noqa: E402
    lifecycle_summary_to_dict,
    reconcile_pending_from_issues,
    reconcile_pending_with_issue_snapshots,
    unresolved_pending_issue_numbers,
)
from artifactforge_dispatch_v1.queueing import (  # noqa: E402
    ARCHIVE_STATUSES,
    PENDING_HOLD_STATUSES,
    REASSIGN_STATUSES,
    active_assignment_for_issue,
    build_queue_records,
    collect_agent_markers,
    collect_existing_fingerprints,
    collect_issue_events,
    delete_superseded_pending_files,
    latest_marker_by_fingerprint,
    reserved_initialization_issue_numbers,
    safe_filename_part,
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
    router_required: bool = True,
) -> str:
    if router_session_id_from_state(assignment_state):
        if router_session_id and not dry_run:
            write_assignment_state(assignment_state_path, assignment_state)
        return "not_started"

    if not router_required:
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


def router_bootstrap_required(
    issues: Iterable[Any],
    assignment_state: dict[str, Any],
    *,
    pending_dir: str | Path,
    archive_dir: str | Path,
    reserved_issue_numbers: Iterable[int] = (),
) -> bool:
    issue_tuple = tuple(issues)
    marker_lookup = latest_marker_by_fingerprint(collect_agent_markers(issue_tuple))
    pending_index = fingerprint_index(collect_existing_fingerprints(pending_dir))
    archive_index = fingerprint_index(collect_existing_fingerprints(archive_dir))
    reserved_index = {int(value) for value in reserved_issue_numbers}

    for event in collect_issue_events(issue_tuple):
        if event.issue_number in reserved_index:
            continue
        marker = marker_lookup.get(event.trigger_fingerprint)
        if marker is not None and marker.status in ARCHIVE_STATUSES:
            continue
        if fingerprint_present(archive_index, event.trigger_fingerprint):
            continue

        reassign_required = marker is not None and marker.status in REASSIGN_STATUSES
        if not reassign_required and fingerprint_present(
            pending_index,
            event.trigger_fingerprint,
        ):
            continue
        if marker is not None and marker.status in PENDING_HOLD_STATUSES:
            continue

        return True
    return False


def fingerprint_index(*groups: Iterable[str]) -> frozenset[str]:
    values = set()
    for group in groups:
        for fingerprint in group:
            if not fingerprint:
                continue
            fingerprint_text = str(fingerprint)
            values.add(fingerprint_text)
            values.add(safe_filename_part(fingerprint_text))
    return frozenset(values)


def fingerprint_present(index: frozenset[str], fingerprint: str) -> bool:
    return fingerprint in index or safe_filename_part(fingerprint) in index


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
                "issue_title": result.plan.record.issue_title,
                "event_type": result.plan.record.event_type,
                "prompt_kind": result.plan.record.prompt_kind,
                "recipient_role": result.plan.record.recipient_role,
                "target_session_id": result.plan.record.target_session_id,
                "source_id": result.plan.record.source_id,
                "trigger_fingerprint": result.plan.record.trigger_fingerprint,
                "sub_artifact_path": result.plan.record.sub_artifact_path,
                "reassign_required": result.plan.record.reassign_required,
                "superseded_pending": [
                    {
                        "path": str(supersede.path),
                        "trigger_fingerprint": supersede.trigger_fingerprint,
                        "replacement_trigger_fingerprint": (
                            supersede.replacement_trigger_fingerprint
                        ),
                        "issue_number": supersede.issue_number,
                        "first_source_id": supersede.first_source_id,
                        "queue_path": str(supersede.queue_path),
                    }
                    for supersede in result.superseded_pending
                ],
            }
            for result in result_tuple
        ],
    }


def superseded_pending_results_to_dict(results: Iterable[Any]) -> dict[str, object]:
    result_tuple = tuple(results)
    return {
        "planned_count": len(result_tuple),
        "deleted_count": sum(1 for result in result_tuple if result.deleted),
        "items": [
            {
                "path": str(result.plan.path),
                "trigger_fingerprint": result.plan.trigger_fingerprint,
                "replacement_trigger_fingerprint": (
                    result.plan.replacement_trigger_fingerprint
                ),
                "issue_number": result.plan.issue_number,
                "first_source_id": result.plan.first_source_id,
                "queue_path": str(result.plan.queue_path),
                "deleted": result.deleted,
                "reason": result.reason,
                "status": (
                    "deleted"
                    if result.deleted
                    else "planned"
                    if result.reason == "dry_run"
                    else result.reason
                    or "not_deleted"
                ),
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


def pending_issue_check_to_dict(
    *,
    issue_numbers: Iterable[int],
    fetched_count: int = 0,
    error: str | None = None,
) -> dict[str, object]:
    number_tuple = tuple(issue_numbers)
    if error:
        status = "failed"
    elif not number_tuple:
        status = "not_needed"
    else:
        status = "checked"
    return {
        "status": status,
        "issue_numbers": list(number_tuple),
        "fetched_count": fetched_count,
        "error": error,
    }


def _divider() -> str:
    return "-------"


def _short(value: object, *, limit: int = 80) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _queue_item_line(item: dict[str, object]) -> str:
    event_type = str(item.get("event_type") or "")
    if event_type == "issue_body":
        label = "body"
    elif event_type == "thread_update":
        label = "thread"
    else:
        label = "comment"
    title = _short(item.get("issue_title") or "(no title)")
    recipient_role = str(item.get("recipient_role") or "")
    prompt_kind = str(item.get("prompt_kind") or "")
    route = recipient_role or ("router" if prompt_kind == "session_router" else "worker")
    extra = []
    if item.get("reassign_required"):
        extra.append("reassign")
    sub_artifact_path = str(item.get("sub_artifact_path") or "").strip()
    if sub_artifact_path:
        extra.append(sub_artifact_path)
    suffix = f" ({', '.join(extra)})" if extra else ""
    return f"#{item.get('issue_number')} {label}: {title} -> {route}{suffix}"


def _pending_item_line(item: dict[str, object]) -> str:
    pending = item.get("pending") if isinstance(item.get("pending"), dict) else {}
    assert isinstance(pending, dict)
    fingerprint = str(pending.get("trigger_fingerprint") or "")
    session_id = _short(pending.get("session_id") or "", limit=36)
    action = str(item.get("action") or "pending")
    status = str(item.get("status") or item.get("reason") or "").strip()
    detail = f" [{status}]" if status else ""
    return f"{fingerprint} -> {action}{detail} ({session_id})"


def _pending_requeue_command(item: dict[str, object], *, queue_dir: str | Path) -> str:
    pending = item.get("pending") if isinstance(item.get("pending"), dict) else {}
    assert isinstance(pending, dict)
    source = str(pending.get("path") or "").strip()
    if not source:
        return ""
    destination = Path(queue_dir) / Path(source).name
    return f"mv {shlex.quote(source)} {shlex.quote(str(destination))}"


def _superseded_item_line(item: dict[str, object]) -> str:
    old_fingerprint = _short(item.get("trigger_fingerprint") or "")
    new_fingerprint = _short(item.get("replacement_trigger_fingerprint") or "")
    status = str(item.get("status") or "").strip()
    detail = f" [{status}]" if status else ""
    return f"{old_fingerprint} -> {new_fingerprint}{detail}"


def _numbered_block(title: str, lines: Iterable[str], *, limit: int = 5) -> list[str]:
    line_tuple = tuple(line for line in lines if line)
    rendered = [f"{title} ({len(line_tuple)})", _divider()]
    if line_tuple:
        visible_lines = line_tuple[:limit]
        rendered.extend(
            f"{index}. {line}" for index, line in enumerate(visible_lines, start=1)
        )
        remaining_count = len(line_tuple) - len(visible_lines)
        if remaining_count > 0:
            rendered.append(f"... and {remaining_count} more")
    else:
        rendered.append("(none)")
    rendered.append(_divider())
    return rendered


def human_summary(
    summary: dict[str, object],
    *,
    queue_dir: str | Path = DEFAULT_QUEUE_DIR,
) -> str:
    effects = summary.get("effects") if isinstance(summary.get("effects"), dict) else {}
    queue = summary.get("queue") if isinstance(summary.get("queue"), dict) else {}
    archive = summary.get("archive") if isinstance(summary.get("archive"), dict) else {}
    assert isinstance(effects, dict)
    assert isinstance(queue, dict)
    assert isinstance(archive, dict)

    lines = [
        "ArtifactForge issue fetch",
        f"repo: {summary.get('repo')}",
        f"mode: {summary.get('mode')}",
        f"router: {effects.get('codex_sessions')}",
        "",
    ]
    queue_items = queue.get("items") if isinstance(queue.get("items"), list) else []
    pending_items = archive.get("items") if isinstance(archive.get("items"), list) else []
    superseded_pending = (
        summary.get("superseded_pending")
        if isinstance(summary.get("superseded_pending"), dict)
        else {}
    )
    assert isinstance(superseded_pending, dict)
    superseded_items = (
        superseded_pending.get("items")
        if isinstance(superseded_pending.get("items"), list)
        else []
    )
    archived_lines = [
        _pending_item_line(item)
        for item in pending_items
        if isinstance(item, dict) and item.get("action") == "archive"
    ]
    human_waiting_lines = [
        _pending_item_line(item)
        for item in pending_items
        if isinstance(item, dict) and item.get("action") == "human_waiting"
    ]
    kept_pending_lines = [
        _pending_item_line(item)
        for item in pending_items
        if isinstance(item, dict) and item.get("action") != "archive"
        and item.get("action") != "human_waiting"
    ]
    requeue_commands = [
        _pending_requeue_command(item, queue_dir=queue_dir)
        for item in pending_items
        if isinstance(item, dict) and item.get("action") != "archive"
        and item.get("action") != "human_waiting"
    ]
    queued_lines = [
        _queue_item_line(item)
        for item in queue_items
        if isinstance(item, dict) and item.get("action") == "skip"
    ]

    lines.extend(
        _numbered_block(
            "Found new issue thread update",
            (
                _queue_item_line(item)
                for item in queue_items
                if isinstance(item, dict) and item.get("action") == "create"
            ),
        )
    )
    lines.append("")
    lines.extend(_numbered_block("already queued", queued_lines))
    lines.append("")
    lines.extend(_numbered_block("pending", kept_pending_lines))
    if requeue_commands:
        lines.append("")
        lines.extend(_numbered_block("pending -> queue commands", requeue_commands))
    lines.append("")
    lines.extend(_numbered_block("human_wating", human_waiting_lines))
    lines.append("")
    lines.extend(
        _numbered_block(
            "superseded pending",
            (
                _superseded_item_line(item)
                for item in superseded_items
                if isinstance(item, dict)
            ),
        )
    )
    lines.append("")
    lines.extend(_numbered_block("archived", archived_lines))
    return "\n".join(lines)


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
    reserved_issue_numbers = reserved_initialization_issue_numbers(REPO_ROOT)
    issue_tuple = tuple(issues)
    work_issues = tuple(
        issue for issue in issue_tuple if issue.issue_number not in reserved_issue_numbers
    )
    router_required = router_bootstrap_required(
        work_issues,
        assignment_state,
        pending_dir=args.pending_dir,
        archive_dir=args.archive_dir,
        reserved_issue_numbers=reserved_issue_numbers,
    )
    codex_sessions_effect = ensure_router_session_id(
        assignment_state,
        args.assignment_state,
        router_session_id=args.router_session_id,
        dry_run=args.dry_run,
        repo_is_fixture=repo_is_fixture,
        router_required=router_required,
    )
    lifecycle = reconcile_pending_from_issues(
        issue_tuple,
        pending_dir=args.pending_dir,
        archive_dir=args.archive_dir,
        dry_run=args.dry_run,
    )
    pending_issue_numbers = unresolved_pending_issue_numbers(lifecycle.results)
    pending_issue_check = pending_issue_check_to_dict(issue_numbers=pending_issue_numbers)
    if pending_issue_numbers and issue_source == "github":
        try:
            pending_issues = fetch_issues_by_number(
                repo,
                pending_issue_numbers,
                gh_bin=args.gh_bin,
            )
            lifecycle = reconcile_pending_with_issue_snapshots(
                lifecycle,
                pending_issues,
                archive_dir=args.archive_dir,
                dry_run=args.dry_run,
            )
            pending_issue_check = pending_issue_check_to_dict(
                issue_numbers=pending_issue_numbers,
                fetched_count=len(pending_issues),
            )
        except GitHubFetchError as exc:
            pending_issue_check = pending_issue_check_to_dict(
                issue_numbers=pending_issue_numbers,
                error=str(exc),
            )
    records = build_queue_records(
        work_issues,
        assignment_state,
        markers=collect_agent_markers(issue_tuple),
        pending_dir=args.pending_dir,
        archive_dir=args.archive_dir,
    )
    queue_results = write_queue_files(
        records,
        queue_dir=args.queue_dir,
        pending_dir=args.pending_dir,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    )
    superseded_pending_results = delete_superseded_pending_files(
        queue_results,
        dry_run=args.dry_run,
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
        "pending_issue_check": pending_issue_check,
        "queue": queue_results_to_dict(queue_results),
        "superseded_pending": superseded_pending_results_to_dict(
            superseded_pending_results
        ),
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
        print(human_summary(summary, queue_dir=args.queue_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
