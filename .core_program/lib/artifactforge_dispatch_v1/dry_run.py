"""Dry-run issue dispatch flow for ArtifactForge.

This module intentionally does not call GitHub, start Codex, post comments,
move queue files, or create sub_artifact directories. It reads fixture/state
JSON and reports the queue, routing, pending, archive, and sub_artifact actions
that would happen in a real run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CORE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CORE_DIR.parent
FIXTURE_DIR = CORE_DIR / "fixtures" / "dry_run"
DEFAULT_ISSUES_PATH = FIXTURE_DIR / "issues.json"
DEFAULT_PENDING_PATH = FIXTURE_DIR / "pending.json"
DEFAULT_ASSIGNMENT_STATE_PATH = FIXTURE_DIR / "assignment_state.json"

MARKER_RE = re.compile(r"<!--\s*codex-agent-v1:\s*(\{.*?\})\s*-->", re.DOTALL)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
VALID_MARKER_STATUSES = frozenset(
    {"done", "reassign_required", "authentication_blocked"}
)
ARCHIVE_STATUSES = frozenset({"done"})
BLOCKED_STATUSES = frozenset({"authentication_blocked"})
REASSIGN_STATUSES = frozenset({"reassign_required"})
SUB_ARTIFACT_NUMBER_RE = re.compile(r"(?:^|/)sub_artifact/(\d{3})_[^/]+")


@dataclass(frozen=True)
class IssueEvent:
    issue_number: int
    issue_url: str
    issue_title: str
    event_type: str
    trigger_fingerprint: str
    body: str
    source_id: str | None = None


@dataclass(frozen=True)
class AgentMarker:
    thread_id: str
    trigger_fingerprint: str
    status: str
    issue_number: int


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_filename_part(value: str) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", value).strip("._")
    return cleaned or "EMPTY"


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.lower()).strip("_")
    return cleaned or "artifact"


def issue_body_fingerprint(issue_number: int, body: str) -> str:
    return f"issue-{issue_number}-body-sha256-{sha256_text(body)}"


def comment_fingerprint(issue_number: int, comment_id: str, body: str) -> str:
    return f"issue-{issue_number}-comment-{comment_id}-sha256-{sha256_text(body)}"


def queue_path(session_id: str, trigger_fingerprint: str) -> str:
    return str(
        Path(".core_program")
        / "queue"
        / f"{safe_filename_part(session_id)}_{safe_filename_part(trigger_fingerprint)}.md"
    )


def pending_path(session_id: str, trigger_fingerprint: str) -> str:
    return str(
        Path(".core_program")
        / "pending"
        / f"{safe_filename_part(session_id)}_{safe_filename_part(trigger_fingerprint)}.md"
    )


def archive_path(session_id: str, trigger_fingerprint: str) -> str:
    return str(
        Path(".core_program")
        / "archive"
        / f"{safe_filename_part(session_id)}_{safe_filename_part(trigger_fingerprint)}.md"
    )


def issue_number_from_fingerprint(trigger_fingerprint: str) -> int | None:
    match = re.match(r"^issue-(\d+)-", trigger_fingerprint)
    if match is None:
        return None
    return int(match.group(1))


def parse_markers(text: str, *, fallback_issue_number: int | None = None) -> tuple[AgentMarker, ...]:
    markers: list[AgentMarker] = []
    for match in MARKER_RE.finditer(text or ""):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        status = str(payload.get("status", ""))
        if status not in VALID_MARKER_STATUSES:
            continue
        trigger_fingerprint = str(payload.get("trigger_fingerprint", ""))
        issue_number = issue_number_from_fingerprint(trigger_fingerprint)
        if issue_number is None and fallback_issue_number is not None:
            issue_number = fallback_issue_number
        if issue_number is None:
            continue
        markers.append(
            AgentMarker(
                thread_id=str(payload.get("thread_id", "")),
                trigger_fingerprint=trigger_fingerprint,
                status=status,
                issue_number=issue_number,
            )
        )
    return tuple(markers)


def load_issues(path: str | Path) -> tuple[dict[str, Any], ...]:
    payload = read_json(path)
    if isinstance(payload, dict):
        issues = payload.get("issues", [])
    else:
        issues = payload
    if not isinstance(issues, list):
        raise ValueError("issues fixture must be a list or an object with an issues list")
    return tuple(issue for issue in issues if str(issue.get("state", "OPEN")).upper() == "OPEN")


def load_pending(path: str | Path) -> tuple[dict[str, Any], ...]:
    payload = read_json(path)
    pending = payload.get("pending", payload) if isinstance(payload, dict) else payload
    if not isinstance(pending, list):
        raise ValueError("pending fixture must be a list or an object with a pending list")
    return tuple(pending)


def load_assignment_state(path: str | Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("assignment state fixture must be an object")
    payload.setdefault("assignments", [])
    payload.setdefault("router_session_id", "11111111-1111-4111-8111-111111111111")
    payload.setdefault("next_sub_artifact_number", 1)
    return payload


def collect_events(issues: Iterable[dict[str, Any]]) -> tuple[IssueEvent, ...]:
    events: list[IssueEvent] = []
    for issue in issues:
        issue_number = int(issue["number"])
        issue_url = str(issue.get("url", ""))
        issue_title = str(issue.get("title", f"issue-{issue_number}"))
        body = str(issue.get("body") or "")
        if body.strip():
            events.append(
                IssueEvent(
                    issue_number=issue_number,
                    issue_url=issue_url,
                    issue_title=issue_title,
                    event_type="issue_body",
                    trigger_fingerprint=issue_body_fingerprint(issue_number, body),
                    body=body,
                )
            )
        for comment in issue.get("comments", []) or []:
            comment_body = str(comment.get("body") or "")
            if "codex-agent-v1" in comment_body:
                continue
            comment_id = str(comment.get("id") or comment.get("databaseId") or "comment")
            events.append(
                IssueEvent(
                    issue_number=issue_number,
                    issue_url=issue_url,
                    issue_title=issue_title,
                    event_type="comment",
                    trigger_fingerprint=comment_fingerprint(issue_number, comment_id, comment_body),
                    body=comment_body,
                    source_id=comment_id,
                )
            )
    return tuple(events)


def collect_markers(issues: Iterable[dict[str, Any]]) -> tuple[AgentMarker, ...]:
    markers: list[AgentMarker] = []
    for issue in issues:
        issue_number = int(issue["number"])
        if "codex-agent-v1" in str(issue.get("body") or ""):
            markers.extend(parse_markers(str(issue.get("body") or ""), fallback_issue_number=issue_number))
        for comment in issue.get("comments", []) or []:
            body = str(comment.get("body") or "")
            if "codex-agent-v1" in body:
                markers.extend(parse_markers(body, fallback_issue_number=issue_number))
    return tuple(markers)


def marker_by_fingerprint(markers: Iterable[AgentMarker]) -> dict[str, AgentMarker]:
    result: dict[str, AgentMarker] = {}
    for marker in markers:
        result[marker.trigger_fingerprint] = marker
    return result


def active_assignment_for_issue(
    assignment_state: dict[str, Any],
    issue_number: int,
) -> dict[str, Any] | None:
    for assignment in assignment_state.get("assignments", []):
        if int(assignment.get("issue_number", -1)) != issue_number:
            continue
        if str(assignment.get("status", "active")) == "active" and assignment.get("session_id"):
            return assignment
    return None


def planned_new_session_id(issue_number: int) -> str:
    suffix = f"{issue_number:012d}"
    return f"00000000-0000-4000-8000-{suffix}"


def sub_artifact_number(path: str) -> int | None:
    match = SUB_ARTIFACT_NUMBER_RE.search(path)
    if match is None:
        return None
    return int(match.group(1))


def next_sub_artifact_number(assignment_state: dict[str, Any]) -> int:
    configured_next = int(assignment_state.get("next_sub_artifact_number", 1))
    used_numbers = [
        number
        for assignment in assignment_state.get("assignments", [])
        for number in [sub_artifact_number(str(assignment.get("sub_artifact_path", "")))]
        if number is not None
    ]
    if not used_numbers:
        return configured_next
    return max(configured_next, max(used_numbers) + 1)


def planned_sub_artifact_path(
    issue: IssueEvent,
    next_number: int,
) -> str:
    return f"sub_artifact/{next_number:03d}_{slugify(issue.issue_title)}"


def planned_sub_artifact_files(sub_artifact_path: str) -> tuple[str, ...]:
    return tuple(
        str(Path(sub_artifact_path) / filename)
        for filename in ("sub_goal.md", "plan.md", "work_log.md", "artifact.md")
    )


def pending_lifecycle(
    pending_entries: Iterable[dict[str, Any]],
    markers: Iterable[AgentMarker],
) -> list[dict[str, Any]]:
    markers_by_fingerprint = marker_by_fingerprint(markers)
    lifecycle: list[dict[str, Any]] = []
    for entry in pending_entries:
        fingerprint = str(entry["trigger_fingerprint"])
        session_id = str(entry["session_id"])
        marker = markers_by_fingerprint.get(fingerprint)
        if marker is None:
            lifecycle.append(
                {
                    "trigger_fingerprint": fingerprint,
                    "session_id": session_id,
                    "current_path": entry.get("path"),
                    "marker_status": None,
                    "planned_state": "pending",
                    "reason": "no_marker",
                }
            )
            continue
        if marker.status in ARCHIVE_STATUSES:
            lifecycle.append(
                {
                    "trigger_fingerprint": fingerprint,
                    "session_id": session_id,
                    "current_path": entry.get("path"),
                    "marker_status": marker.status,
                    "planned_state": "archive",
                    "planned_archive_path": archive_path(session_id, fingerprint),
                }
            )
            continue
        if marker.status in BLOCKED_STATUSES:
            planned_state = "pending_authentication_blocked"
        elif marker.status in REASSIGN_STATUSES:
            planned_state = "pending_reassign_required"
        else:
            planned_state = "pending"
        lifecycle.append(
            {
                "trigger_fingerprint": fingerprint,
                "session_id": session_id,
                "current_path": entry.get("path"),
                "marker_status": marker.status,
                "planned_state": planned_state,
                "reason": "marker_not_complete",
            }
        )
    return lifecycle


def queue_plan(
    events: Iterable[IssueEvent],
    pending_entries: Iterable[dict[str, Any]],
    markers: Iterable[AgentMarker],
    assignment_state: dict[str, Any],
) -> list[dict[str, Any]]:
    pending_fingerprints = {str(entry["trigger_fingerprint"]) for entry in pending_entries}
    markers_by_fingerprint = marker_by_fingerprint(markers)
    router_session_id = str(assignment_state["router_session_id"])
    planned_new_sub_artifacts: dict[int, str] = {}
    next_number = next_sub_artifact_number(assignment_state)
    plan: list[dict[str, Any]] = []
    for event in events:
        marker = markers_by_fingerprint.get(event.trigger_fingerprint)
        if marker is not None and marker.status in ARCHIVE_STATUSES:
            plan.append(
                {
                    "issue_number": event.issue_number,
                    "event_type": event.event_type,
                    "trigger_fingerprint": event.trigger_fingerprint,
                    "planned_action": "skip_done",
                    "marker_status": marker.status,
                }
            )
            continue
        if event.trigger_fingerprint in pending_fingerprints:
            plan.append(
                {
                    "issue_number": event.issue_number,
                    "event_type": event.event_type,
                    "trigger_fingerprint": event.trigger_fingerprint,
                    "planned_action": "skip_pending",
                }
            )
            continue
        assignment = active_assignment_for_issue(assignment_state, event.issue_number)
        if assignment is None:
            target_session_id = router_session_id
            prompt_kind = "session_router"
            planned_worker_session = planned_new_session_id(event.issue_number)
            sub_artifact_path = planned_new_sub_artifacts.get(event.issue_number)
            if sub_artifact_path is None:
                sub_artifact_path = planned_sub_artifact_path(event, next_number)
                planned_new_sub_artifacts[event.issue_number] = sub_artifact_path
                next_number += 1
        else:
            target_session_id = str(assignment["session_id"])
            prompt_kind = "worker"
            planned_worker_session = target_session_id
            sub_artifact_path = str(assignment.get("sub_artifact_path", ""))
        plan.append(
            {
                "issue_number": event.issue_number,
                "issue_title": event.issue_title,
                "event_type": event.event_type,
                "trigger_fingerprint": event.trigger_fingerprint,
                "planned_action": "queue",
                "prompt_kind": prompt_kind,
                "queue_target_session_id": target_session_id,
                "planned_queue_path": queue_path(target_session_id, event.trigger_fingerprint),
                "planned_worker_session_id": planned_worker_session,
                "sub_artifact_path": sub_artifact_path,
            }
        )
    return plan


def dispatch_plan(queue_entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    dispatches: list[dict[str, Any]] = []
    for entry in queue_entries:
        if entry.get("planned_action") != "queue":
            continue
        fingerprint = str(entry["trigger_fingerprint"])
        worker_session_id = str(entry["planned_worker_session_id"])
        prompt_kind = str(entry["prompt_kind"])
        dispatch: dict[str, Any] = {
            "trigger_fingerprint": fingerprint,
            "prompt_kind": prompt_kind,
            "queue_path": entry["planned_queue_path"],
            "dry_run_effect": "no files moved, no Codex session started, no GitHub comment posted",
        }
        if prompt_kind == "session_router":
            dispatch.update(
                {
                    "router_session_id": entry["queue_target_session_id"],
                    "router_output_contract": "exactly one session ID line",
                    "dry_run_router_would_return": worker_session_id,
                    "worker_prompt_target_session_id": worker_session_id,
                    "planned_assignment_state_update": {
                        "issue_number": entry["issue_number"],
                        "session_id": worker_session_id,
                        "sub_artifact_path": entry["sub_artifact_path"],
                    },
                }
            )
        else:
            dispatch["worker_prompt_target_session_id"] = worker_session_id
        dispatch["planned_pending_path"] = pending_path(worker_session_id, fingerprint)
        if entry.get("sub_artifact_path"):
            dispatch["sub_artifact_initialization"] = {
                "mode": "planned_only",
                "path": entry["sub_artifact_path"],
                "files": list(planned_sub_artifact_files(str(entry["sub_artifact_path"]))),
            }
        dispatches.append(dispatch)
    return dispatches


def build_summary(
    *,
    stage: str,
    issues_path: str | Path,
    pending_path_value: str | Path,
    assignment_state_path: str | Path,
) -> dict[str, Any]:
    issues = load_issues(issues_path)
    pending_entries = load_pending(pending_path_value)
    assignment_state = load_assignment_state(assignment_state_path)
    events = collect_events(issues)
    markers = collect_markers(issues)
    lifecycle = pending_lifecycle(pending_entries, markers)
    queue_entries = queue_plan(events, pending_entries, markers, assignment_state)
    summary: dict[str, Any] = {
        "schema_version": 1,
        "mode": "dry-run",
        "stage": stage,
        "source": "fixture",
        "effects": {
            "github_fetch": "not called",
            "github_comment": "not posted",
            "codex_session": "not started",
            "queue_pending_archive_files": "not created_or_moved",
            "sub_artifact_files": "not created",
        },
        "inputs": {
            "issues": str(Path(issues_path)),
            "pending": str(Path(pending_path_value)),
            "assignment_state": str(Path(assignment_state_path)),
        },
        "router_session_id": assignment_state["router_session_id"],
        "contracts": {
            "assignment_state": {
                "path": ".core_program/assignment_state.json",
                "dry_run_fixture": str(Path(assignment_state_path)),
                "role": "canonical issue/session/sub_artifact assignment state for ArtifactForge",
                "required_fields": [
                    "schema_version",
                    "router_session_id",
                    "next_sub_artifact_number",
                    "assignments",
                ],
            },
            "marker_statuses": sorted(VALID_MARKER_STATUSES),
            "router_output": "exactly one session ID line",
            "sub_artifact_initialization": {
                "mode": "planned_only_in_dry_run",
                "files": ["sub_goal.md", "plan.md", "work_log.md", "artifact.md"],
            },
        },
        "counts": {
            "issues": len(issues),
            "events": len(events),
            "markers": len(markers),
            "pending": len(pending_entries),
        },
        "pending_lifecycle": lifecycle,
        "queue_plan": queue_entries,
    }
    if stage == "dispatch":
        summary["dispatch_plan"] = dispatch_plan(queue_entries)
    return summary


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dry-run", action="store_true", help="required; real execution is not implemented")
    parser.add_argument("--issues", default=str(DEFAULT_ISSUES_PATH))
    parser.add_argument("--pending", default=str(DEFAULT_PENDING_PATH))
    parser.add_argument("--assignment-state", default=str(DEFAULT_ASSIGNMENT_STATE_PATH))
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    return parser


def run_cli(stage: str, description: str) -> int:
    parser = build_parser(description)
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("only --dry-run is implemented in ArtifactForge at this stage")
    summary = build_summary(
        stage=stage,
        issues_path=args.issues,
        pending_path_value=args.pending,
        assignment_state_path=args.assignment_state,
    )
    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli("dispatch", "ArtifactForge dry-run dispatch"))
