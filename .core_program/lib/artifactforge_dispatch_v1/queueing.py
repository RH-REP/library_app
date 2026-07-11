"""Queue file creation helpers for ArtifactForge issue dispatch."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .lifecycle import iter_pending_records
from .models import AgentMarker, IssueComment, IssueEvent, IssueSnapshot, QueueRecord


CORE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CORE_DIR.parent
INITIALIZATION_ISSUE_NUMBER = 1
INITIALIZATION_GOAL_PATH = Path("main_artifact") / "goal.md"
INITIALIZATION_PROCESS_PATH = Path("main_artifact") / "development_process.md"


AI_MARKER_TOKEN = "codex-agent-v1:"
VALID_MARKER_STATUSES = frozenset(
    {"done", "reassign_required", "authentication_blocked"}
)
ARCHIVE_STATUSES = frozenset({"done"})
PENDING_HOLD_STATUSES = frozenset({"authentication_blocked"})
REASSIGN_STATUSES = frozenset({"reassign_required"})

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
SLUG_RE = re.compile(r"[^A-Za-z0-9]+")
MARKER_RE = re.compile(r"<!--\s*codex-agent-v1:\s*(\{.*?\})\s*-->", re.DOTALL)
ISSUE_NUMBER_RE = re.compile(r"^issue-(\d+)-")
SUB_ARTIFACT_NUMBER_RE = re.compile(r"(?:^|/)sub_artifact/(\d{3})_[^/]+")
FINGERPRINT_IN_FILENAME_RE = re.compile(r"_(issue-\d+-(?:body|comment|thread)-.+)$")
FINGERPRINT_IN_TEXT_RE = re.compile(
    r"^\s*-?\s*trigger_fingerprint:\s*`?([^`\s]+)`?\s*$",
    re.MULTILINE,
)
THREAD_FINGERPRINT_RE = re.compile(
    r"^issue-(?P<issue_number>\d+)-thread-"
    r"(?P<first_source_id>[^-]+)-(?P<last_source_id>[^-]+)-sha256-(?P<digest>.+)$"
)


@dataclass(frozen=True)
class QueueFilePlan:
    record: QueueRecord
    path: Path
    content: str
    action: str
    reason: str | None = None


@dataclass(frozen=True)
class ThreadFingerprintMetadata:
    issue_number: int
    first_source_id: str
    last_source_id: str


@dataclass(frozen=True)
class PendingSupersedePlan:
    path: Path
    trigger_fingerprint: str
    replacement_trigger_fingerprint: str
    issue_number: int
    first_source_id: str
    queue_path: Path


@dataclass(frozen=True)
class QueueFileResult:
    plan: QueueFilePlan
    written: bool
    reason: str | None = None
    superseded_pending: tuple[PendingSupersedePlan, ...] = ()


@dataclass(frozen=True)
class PendingSupersedeResult:
    plan: PendingSupersedePlan
    deleted: bool
    reason: str | None = None


@dataclass(frozen=True)
class ThreadSource:
    source_id: str
    heading: str
    body: str
    created_at: str | None = None
    author: str | None = None
    url: str | None = None


class RouterSessionRequired(ValueError):
    pass


def reserved_initialization_issue_numbers(
    repo_dir: str | Path | None = None,
) -> frozenset[int]:
    root = Path(repo_dir) if repo_dir is not None else REPO_ROOT
    if (
        (root / INITIALIZATION_GOAL_PATH).exists()
        and (root / INITIALIZATION_PROCESS_PATH).exists()
    ):
        return frozenset({INITIALIZATION_ISSUE_NUMBER})
    return frozenset()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def issue_body_fingerprint(issue_number: int, body: str) -> str:
    return f"issue-{issue_number}-body-sha256-{sha256_text(body)}"


def comment_fingerprint(issue_number: int, comment_id: str, body: str) -> str:
    return f"issue-{issue_number}-comment-{comment_id}-sha256-{sha256_text(body)}"


def thread_update_fingerprint(
    issue_number: int,
    first_source_id: str,
    last_source_id: str,
    body: str,
) -> str:
    return (
        f"issue-{issue_number}-thread-"
        f"{safe_filename_part(first_source_id)}-"
        f"{safe_filename_part(last_source_id)}-sha256-{sha256_text(body)}"
    )


def parse_thread_fingerprint_metadata(
    trigger_fingerprint: str,
) -> ThreadFingerprintMetadata | None:
    match = THREAD_FINGERPRINT_RE.match(trigger_fingerprint)
    if match is None:
        return None
    return ThreadFingerprintMetadata(
        issue_number=int(match.group("issue_number")),
        first_source_id=match.group("first_source_id"),
        last_source_id=match.group("last_source_id"),
    )


def safe_filename_part(value: str) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", value).strip("._")
    return cleaned or "EMPTY"


def is_ai_marker_comment(comment: IssueComment) -> bool:
    return AI_MARKER_TOKEN in comment.body


def collect_issue_events(issues: Iterable[IssueSnapshot]) -> tuple[IssueEvent, ...]:
    events: list[IssueEvent] = []
    for issue in sorted(issues, key=lambda value: value.issue_number):
        if issue.issue_state.lower() != "open":
            continue
        event = _thread_update_event(issue)
        if event is not None:
            events.append(event)
    return tuple(events)


def _thread_update_event(issue: IssueSnapshot) -> IssueEvent | None:
    comments = _sorted_comments(issue.comments)
    marker_index = _latest_valid_marker_comment_index(issue.issue_number, comments)
    sources: list[ThreadSource] = []

    if marker_index is None and issue.body.strip():
        sources.append(
            ThreadSource(
                source_id="body",
                heading="Issue body",
                body=issue.body,
                created_at=issue.created_at,
                url=issue.issue_url,
            )
        )

    candidate_comments = (
        comments if marker_index is None else comments[marker_index + 1 :]
    )
    for comment in candidate_comments:
        if is_ai_marker_comment(comment) or not comment.body.strip():
            continue
        sources.append(
            ThreadSource(
                source_id=comment.comment_id,
                heading=f"Comment {comment.comment_id}",
                body=comment.body,
                created_at=comment.created_at,
                author=comment.author,
                url=comment.url or issue.issue_url,
            )
        )

    if not sources:
        return None

    body = _combined_thread_body(sources)
    first_source_id = sources[0].source_id
    last_source_id = sources[-1].source_id
    source_id = (
        first_source_id
        if first_source_id == last_source_id
        else f"{first_source_id}..{last_source_id}"
    )
    source_url = sources[-1].url or issue.issue_url
    created_at = sources[-1].created_at or issue.updated_at or issue.created_at
    return IssueEvent(
        issue_number=issue.issue_number,
        issue_url=issue.issue_url,
        issue_title=issue.title,
        event_type="thread_update",
        trigger_fingerprint=thread_update_fingerprint(
            issue.issue_number,
            first_source_id,
            last_source_id,
            body,
        ),
        body=body,
        source_id=source_id,
        source_url=source_url,
        created_at=created_at,
    )


def _sorted_comments(comments: Iterable[IssueComment]) -> tuple[IssueComment, ...]:
    return tuple(
        sorted(
            comments,
            key=lambda value: (_datetime_sort_key(value.created_at), value.comment_id),
        )
    )


def _latest_valid_marker_comment_index(
    issue_number: int,
    comments: tuple[IssueComment, ...],
) -> int | None:
    latest_index = None
    latest_key = None
    for index, comment in enumerate(comments):
        markers = parse_agent_markers(
            comment.body,
            fallback_issue_number=issue_number,
            comment_id=comment.comment_id,
            created_at=comment.created_at,
        )
        if not markers:
            continue
        key = (_datetime_sort_key(comment.created_at), comment.comment_id)
        if latest_key is None or key >= latest_key:
            latest_key = key
            latest_index = index
    return latest_index


def _combined_thread_body(sources: Iterable[ThreadSource]) -> str:
    return "\n\n".join(_thread_source_block(source) for source in sources)


def _thread_source_block(source: ThreadSource) -> str:
    lines = [
        f"## {source.heading}",
        f"- source_id: {source.source_id}",
    ]
    if source.created_at:
        lines.append(f"- created_at: {source.created_at}")
    if source.author:
        lines.append(f"- author: {source.author}")
    if source.url:
        lines.append(f"- url: {source.url}")
    lines.extend(["", source.body.strip()])
    return "\n".join(lines)


def parse_agent_markers(
    text: str,
    *,
    fallback_issue_number: int | None = None,
    comment_id: str | None = None,
    created_at: str | None = None,
) -> tuple[AgentMarker, ...]:
    markers: list[AgentMarker] = []
    for match in MARKER_RE.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        status = str(payload.get("status", ""))
        if status not in VALID_MARKER_STATUSES:
            continue

        trigger_fingerprint = str(payload.get("trigger_fingerprint", ""))
        issue_number = _issue_number_from_fingerprint(trigger_fingerprint)
        if issue_number is None:
            issue_number = fallback_issue_number
        if issue_number is None:
            continue

        thread_id = payload.get("thread_id")
        markers.append(
            AgentMarker(
                thread_id=str(thread_id) if thread_id is not None else None,
                trigger_fingerprint=trigger_fingerprint,
                status=status,
                issue_number=issue_number,
                created_at=created_at,
                comment_id=comment_id,
            )
        )
    return tuple(markers)


def collect_agent_markers(issues: Iterable[IssueSnapshot]) -> tuple[AgentMarker, ...]:
    markers: list[AgentMarker] = []
    for issue in issues:
        if AI_MARKER_TOKEN in issue.body:
            markers.extend(
                parse_agent_markers(
                    issue.body,
                    fallback_issue_number=issue.issue_number,
                    created_at=issue.updated_at or issue.created_at,
                )
            )
        for comment in issue.comments:
            if AI_MARKER_TOKEN not in comment.body:
                continue
            markers.extend(
                parse_agent_markers(
                    comment.body,
                    fallback_issue_number=issue.issue_number,
                    comment_id=comment.comment_id,
                    created_at=comment.created_at,
                )
            )
    return tuple(markers)


def build_queue_records(
    issues: Iterable[IssueSnapshot],
    assignment_state: dict[str, Any],
    *,
    markers: Iterable[AgentMarker] | None = None,
    pending_fingerprints: Iterable[str] = (),
    archive_fingerprints: Iterable[str] = (),
    pending_dir: str | Path | None = None,
    archive_dir: str | Path | None = None,
) -> tuple[QueueRecord, ...]:
    issue_tuple = tuple(issues)
    events = collect_issue_events(issue_tuple)
    marker_lookup = latest_marker_by_fingerprint(
        collect_agent_markers(issue_tuple) if markers is None else markers
    )
    pending_index = _fingerprint_index(
        pending_fingerprints,
        collect_existing_fingerprints(pending_dir) if pending_dir is not None else (),
    )
    pending_sessions = _pending_sessions_by_fingerprint(pending_dir)
    archive_index = _fingerprint_index(
        archive_fingerprints,
        collect_existing_fingerprints(archive_dir) if archive_dir is not None else (),
    )
    planned_sub_artifacts: dict[int, str] = {}
    next_number = next_sub_artifact_number(assignment_state)

    records: list[QueueRecord] = []
    for event in events:
        marker = marker_lookup.get(event.trigger_fingerprint)
        if marker is not None and marker.status in ARCHIVE_STATUSES:
            continue
        if _fingerprint_present(archive_index, event.trigger_fingerprint):
            continue

        reassign_required = marker is not None and marker.status in REASSIGN_STATUSES
        previous_thread_id = marker.thread_id if marker is not None else None
        if reassign_required and _reassign_handoff_pending_exists(
            pending_sessions,
            event.trigger_fingerprint,
            previous_thread_id,
        ):
            continue
        if not reassign_required and _fingerprint_present(
            pending_index,
            event.trigger_fingerprint,
        ):
            continue
        if marker is not None and marker.status in PENDING_HOLD_STATUSES:
            continue

        assignment = active_assignment_for_issue(assignment_state, event.issue_number)
        target_session_id = _router_session_id(assignment_state)
        prompt_kind = "session_router"
        sub_artifact_path = (
            _optional_str(assignment.get("sub_artifact_path"))
            if assignment is not None
            else planned_sub_artifacts.get(event.issue_number)
        )
        if sub_artifact_path is None:
            sub_artifact_path = planned_sub_artifact_path(event, next_number)
            planned_sub_artifacts[event.issue_number] = sub_artifact_path
            next_number += 1

        records.append(
            QueueRecord(
                issue_number=event.issue_number,
                issue_url=event.issue_url,
                issue_title=event.issue_title,
                event_type=event.event_type,
                trigger_fingerprint=event.trigger_fingerprint,
                target_session_id=target_session_id,
                prompt_kind=prompt_kind,
                body=event.body,
                source_id=event.source_id,
                sub_artifact_path=sub_artifact_path,
                previous_thread_id=previous_thread_id,
                reassign_required=reassign_required,
            )
        )
    return tuple(records)


def active_assignment_for_issue(
    assignment_state: dict[str, Any],
    issue_number: int,
) -> dict[str, Any] | None:
    for assignment in assignment_state.get("assignments", []) or []:
        try:
            assigned_issue_number = int(assignment.get("issue_number", -1))
        except (TypeError, ValueError):
            continue
        if assigned_issue_number != issue_number:
            continue
        if str(assignment.get("status", "active")) != "active":
            continue
        return assignment
    return None


def slugify(value: str) -> str:
    return SLUG_RE.sub("_", value.lower()).strip("_") or "artifact"


def sub_artifact_number(path: str) -> int | None:
    match = SUB_ARTIFACT_NUMBER_RE.search(path)
    if match is None:
        return None
    return int(match.group(1))


def next_sub_artifact_number(assignment_state: dict[str, Any]) -> int:
    configured = int(assignment_state.get("next_sub_artifact_number", 1) or 1)
    used = [
        number
        for assignment in assignment_state.get("assignments", []) or []
        for number in [sub_artifact_number(str(assignment.get("sub_artifact_path", "")))]
        if number is not None
    ]
    if not used:
        return configured
    return max(configured, max(used) + 1)


def planned_sub_artifact_path(event: IssueEvent, number: int) -> str:
    return f"sub_artifact/{number:03d}_{slugify(event.issue_title)}"


def queue_filename(record: QueueRecord) -> str:
    return (
        f"{safe_filename_part(record.target_session_id)}_"
        f"{safe_filename_part(record.trigger_fingerprint)}.md"
    )


def queue_path(record: QueueRecord, queue_dir: str | Path) -> Path:
    return Path(queue_dir) / queue_filename(record)


def build_queue_markdown(record: QueueRecord) -> str:
    lines = [
        "# ArtifactForge Issue Event",
        "",
        "## Routing",
        f"- prompt_kind: {record.prompt_kind}",
        f"- recipient_role: {record.recipient_role}",
        f"- target_session_id: {record.target_session_id}",
        f"- reassign_required: {_bool_text(record.reassign_required)}",
    ]
    if record.previous_thread_id:
        lines.append(f"- previous_thread_id: {record.previous_thread_id}")
    if record.sub_artifact_path:
        lines.append(f"- sub_artifact_path: {record.sub_artifact_path}")

    lines.extend(
        [
            "",
            "## Issue Event",
            f"- issue_number: {record.issue_number}",
            f"- issue_title: {record.issue_title}",
            f"- issue_url: {record.issue_url}",
            f"- event_type: {record.event_type}",
            f"- source_id: {record.source_id or ''}",
            f"- trigger_fingerprint: {record.trigger_fingerprint}",
            "",
            "## Body",
            "",
            record.body,
            "",
        ]
    )
    return "\n".join(lines)


def plan_queue_files(
    records: Iterable[QueueRecord],
    *,
    queue_dir: str | Path,
    overwrite: bool = False,
) -> tuple[QueueFilePlan, ...]:
    plans: list[QueueFilePlan] = []
    for record in records:
        path = queue_path(record, queue_dir)
        content = build_queue_markdown(record)
        if path.exists() and not overwrite:
            plans.append(
                QueueFilePlan(
                    record=record,
                    path=path,
                    content=content,
                    action="skip",
                    reason="queue_exists",
                )
            )
            continue
        plans.append(
            QueueFilePlan(
                record=record,
                path=path,
                content=content,
                action="create",
            )
        )
    return tuple(plans)


def write_queue_files(
    records: Iterable[QueueRecord],
    *,
    queue_dir: str | Path,
    pending_dir: str | Path | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
) -> tuple[QueueFileResult, ...]:
    plans = plan_queue_files(records, queue_dir=queue_dir, overwrite=overwrite)
    results: list[QueueFileResult] = []
    if dry_run:
        return tuple(
            QueueFileResult(
                plan=plan,
                written=False,
                reason=plan.reason or "dry_run",
                superseded_pending=_superseded_pending_for_plan(
                    plan,
                    pending_dir=pending_dir,
                ),
            )
            for plan in plans
        )

    for plan in plans:
        if plan.action != "create":
            results.append(
                QueueFileResult(plan=plan, written=False, reason=plan.reason)
            )
            continue
        plan.path.parent.mkdir(parents=True, exist_ok=True)
        plan.path.write_text(plan.content, encoding="utf-8")
        results.append(
            QueueFileResult(
                plan=plan,
                written=True,
                superseded_pending=_superseded_pending_for_plan(
                    plan,
                    pending_dir=pending_dir,
                ),
            )
        )
    return tuple(results)


def delete_superseded_pending_files(
    results: Iterable[QueueFileResult],
    *,
    dry_run: bool = False,
) -> tuple[PendingSupersedeResult, ...]:
    supersede_results: list[PendingSupersedeResult] = []
    seen_paths: set[Path] = set()
    for result in results:
        for supersede_plan in result.superseded_pending:
            path = supersede_plan.path
            if path in seen_paths:
                continue
            seen_paths.add(path)
            if dry_run:
                supersede_results.append(
                    PendingSupersedeResult(
                        plan=supersede_plan,
                        deleted=False,
                        reason="dry_run",
                    )
                )
                continue
            if not result.written:
                supersede_results.append(
                    PendingSupersedeResult(
                        plan=supersede_plan,
                        deleted=False,
                        reason="queue_not_written",
                    )
                )
                continue
            try:
                path.unlink()
            except FileNotFoundError:
                supersede_results.append(
                    PendingSupersedeResult(
                        plan=supersede_plan,
                        deleted=False,
                        reason="missing",
                    )
                )
            else:
                supersede_results.append(
                    PendingSupersedeResult(plan=supersede_plan, deleted=True)
                )
    return tuple(supersede_results)


def collect_existing_fingerprints(path: str | Path | None) -> frozenset[str]:
    if path is None:
        return frozenset()

    target = Path(path)
    if not target.exists():
        return frozenset()

    paths = sorted(target.glob("*.md")) if target.is_dir() else [target]
    fingerprints: set[str] = set()
    for item in paths:
        if item.name.startswith("."):
            continue
        fingerprints.update(_fingerprints_from_file(item))
    return frozenset(fingerprints)


def latest_marker_by_fingerprint(
    markers: Iterable[AgentMarker],
) -> dict[str, AgentMarker]:
    result: dict[str, AgentMarker] = {}
    for marker in markers:
        existing = result.get(marker.trigger_fingerprint)
        if existing is None or _marker_sort_key(marker) >= _marker_sort_key(existing):
            result[marker.trigger_fingerprint] = marker
    return result


def _router_session_id(assignment_state: dict[str, Any]) -> str:
    value = str(assignment_state.get("router_session_id", "")).strip()
    if not value:
        raise RouterSessionRequired("assignment_state must include router_session_id")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _fingerprint_index(*groups: Iterable[str]) -> frozenset[str]:
    values: set[str] = set()
    for group in groups:
        for fingerprint in group:
            if not fingerprint:
                continue
            values.add(str(fingerprint))
            values.add(safe_filename_part(str(fingerprint)))
    return frozenset(values)


def _fingerprint_present(index: frozenset[str], fingerprint: str) -> bool:
    return fingerprint in index or safe_filename_part(fingerprint) in index


def _pending_sessions_by_fingerprint(path: str | Path | None) -> dict[str, set[str]]:
    if path is None:
        return {}

    sessions: dict[str, set[str]] = {}
    for record in iter_pending_records(path):
        for fingerprint in (
            record.trigger_fingerprint,
            safe_filename_part(record.trigger_fingerprint),
        ):
            sessions.setdefault(fingerprint, set()).add(record.session_id)
    return sessions


def _pending_sessions_for(
    sessions_by_fingerprint: dict[str, set[str]],
    fingerprint: str,
) -> set[str]:
    sessions = set(sessions_by_fingerprint.get(fingerprint, set()))
    sessions.update(sessions_by_fingerprint.get(safe_filename_part(fingerprint), set()))
    return sessions


def _reassign_handoff_pending_exists(
    sessions_by_fingerprint: dict[str, set[str]],
    fingerprint: str,
    previous_thread_id: str | None,
) -> bool:
    sessions = _pending_sessions_for(sessions_by_fingerprint, fingerprint)
    if not sessions:
        return False
    if not previous_thread_id:
        return True
    return any(session_id != previous_thread_id for session_id in sessions)


def _superseded_pending_for_plan(
    plan: QueueFilePlan,
    *,
    pending_dir: str | Path | None,
) -> tuple[PendingSupersedePlan, ...]:
    if pending_dir is None or plan.action != "create" or plan.record.reassign_required:
        return ()

    replacement = parse_thread_fingerprint_metadata(
        plan.record.trigger_fingerprint
    )
    if replacement is None:
        return ()

    superseded: list[PendingSupersedePlan] = []
    replacement_fingerprint = plan.record.trigger_fingerprint
    replacement_safe = safe_filename_part(replacement_fingerprint)
    for pending in iter_pending_records(pending_dir):
        pending_fingerprint = pending.trigger_fingerprint
        if pending_fingerprint == replacement_fingerprint:
            continue
        if safe_filename_part(pending_fingerprint) == replacement_safe:
            continue
        pending_metadata = parse_thread_fingerprint_metadata(pending_fingerprint)
        if pending_metadata is None:
            continue
        if pending_metadata.issue_number != replacement.issue_number:
            continue
        if pending_metadata.first_source_id != replacement.first_source_id:
            continue
        superseded.append(
            PendingSupersedePlan(
                path=Path(pending.path),
                trigger_fingerprint=pending_fingerprint,
                replacement_trigger_fingerprint=replacement_fingerprint,
                issue_number=replacement.issue_number,
                first_source_id=replacement.first_source_id,
                queue_path=plan.path,
            )
        )
    return tuple(superseded)


def _fingerprints_from_file(path: Path) -> set[str]:
    fingerprints: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = ""
    for match in FINGERPRINT_IN_TEXT_RE.finditer(text):
        fingerprints.add(match.group(1))

    filename_match = FINGERPRINT_IN_FILENAME_RE.search(path.stem)
    if filename_match is not None:
        fingerprints.add(filename_match.group(1))
    return fingerprints


def _issue_number_from_fingerprint(trigger_fingerprint: str) -> int | None:
    match = ISSUE_NUMBER_RE.match(trigger_fingerprint)
    if match is None:
        return None
    return int(match.group(1))


def _datetime_sort_key(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _marker_sort_key(marker: AgentMarker) -> tuple[datetime, str]:
    return (_datetime_sort_key(marker.created_at), marker.comment_id or "")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
