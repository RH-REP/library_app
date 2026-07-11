"""Pending/archive lifecycle helpers for ArtifactForge issue dispatch."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import AgentMarker, IssueSnapshot, PendingRecord


MARKER_RE = re.compile(r"<!--\s*codex-agent-v1:\s*(\{.*?\})\s*-->", re.DOTALL)
ISSUE_NUMBER_RE = re.compile(r"^issue-(\d+)-")
PENDING_FILENAME_RE = re.compile(r"_(?=(?:issue|step2|test)-)")
FIELD_RE = re.compile(r"^\s*-?\s*([A-Za-z_][A-Za-z0-9_ -]*)\s*:\s*(.*?)\s*$")
HUMAN_WAITING_DIR_NAME = "human_wating"

VALID_MARKER_STATUSES = frozenset(
    {"done", "reassign_required", "authentication_blocked"}
)
ARCHIVE_STATUSES = frozenset({"done"})
HUMAN_WAITING_STATUSES = frozenset({"reassign_required", "authentication_blocked"})


@dataclass(frozen=True)
class PendingLifecycleResult:
    pending: PendingRecord
    marker: AgentMarker | None
    action: str
    status: str | None = None
    moved: bool = False
    archive_path: str | None = None
    human_waiting_path: str | None = None
    reassign_required: bool = False
    authentication_blocked: bool = False
    human_waiting: bool = False
    reason: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class PendingLifecycleSummary:
    results: tuple[PendingLifecycleResult, ...]
    pending_dir: str
    human_waiting_dir: str
    archive_dir: str
    dry_run: bool

    @property
    def reassign_required(self) -> tuple[PendingLifecycleResult, ...]:
        return tuple(result for result in self.results if result.reassign_required)

    @property
    def reassign_required_fingerprints(self) -> tuple[str, ...]:
        return tuple(
            result.pending.trigger_fingerprint
            for result in self.results
            if result.reassign_required
        )

    @property
    def human_waiting(self) -> tuple[PendingLifecycleResult, ...]:
        return tuple(result for result in self.results if result.human_waiting)

    @property
    def human_waiting_fingerprints(self) -> tuple[str, ...]:
        return tuple(
            result.pending.trigger_fingerprint
            for result in self.results
            if result.human_waiting
        )


class MarkerParseError(ValueError):
    """Raised when a codex-agent-v1 marker is malformed and strict parsing is on."""


def _issue_number_from_fingerprint(trigger_fingerprint: str) -> int | None:
    match = ISSUE_NUMBER_RE.match(trigger_fingerprint)
    if match is None:
        return None
    return int(match.group(1))


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _path_text(path: str | Path) -> str:
    return str(Path(path)).replace("\\", "/")


def _is_under_directory(path: str | Path, directory: str | Path) -> bool:
    path_text = _path_text(path)
    directory_text = _path_text(directory).rstrip("/")
    return path_text == directory_text or path_text.startswith(directory_text + "/")


def _bucket_for_path(
    path: str | Path,
    *,
    pending_dir: str | Path,
    human_waiting_dir: str | Path,
) -> str:
    if _is_under_directory(path, human_waiting_dir):
        return "human_waiting"
    if _is_under_directory(path, pending_dir):
        return "pending"
    return "pending"


def parse_agent_markers(
    text: str,
    *,
    issue_number: int | None = None,
    comment_id: str | None = None,
    created_at: str | None = None,
    skip_invalid: bool = True,
) -> tuple[AgentMarker, ...]:
    """Parse valid codex-agent-v1 markers from one GitHub issue comment body."""

    markers: list[AgentMarker] = []
    for match in MARKER_RE.finditer(text or ""):
        try:
            payload = json.loads(match.group(1))
            trigger_fingerprint = str(payload["trigger_fingerprint"])
            status = str(payload["status"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            if skip_invalid:
                continue
            raise MarkerParseError(f"invalid codex-agent-v1 marker: {exc}") from exc

        if status not in VALID_MARKER_STATUSES:
            if skip_invalid:
                continue
            raise MarkerParseError(f"invalid marker status: {status}")

        marker_issue_number = issue_number
        if marker_issue_number is None:
            marker_issue_number = _issue_number_from_fingerprint(trigger_fingerprint)
        if marker_issue_number is None:
            if skip_invalid:
                continue
            raise MarkerParseError("marker issue_number could not be resolved")

        thread_id = payload.get("thread_id")
        markers.append(
            AgentMarker(
                thread_id=str(thread_id) if thread_id is not None else None,
                trigger_fingerprint=trigger_fingerprint,
                status=status,
                issue_number=marker_issue_number,
                created_at=created_at,
                comment_id=comment_id,
            )
        )
    return tuple(markers)


def collect_agent_markers_from_issues(
    issues: Iterable[IssueSnapshot],
) -> tuple[AgentMarker, ...]:
    """Collect valid worker markers from GitHub issue comments only."""

    markers: list[AgentMarker] = []
    for issue in issues:
        for comment in issue.comments:
            markers.extend(
                parse_agent_markers(
                    comment.body,
                    issue_number=issue.issue_number,
                    comment_id=comment.comment_id,
                    created_at=comment.created_at,
                    skip_invalid=True,
                )
            )
    return tuple(markers)


def latest_marker_by_fingerprint(
    markers: Iterable[AgentMarker],
) -> dict[str, AgentMarker]:
    latest: dict[str, AgentMarker] = {}
    for marker in markers:
        current = latest.get(marker.trigger_fingerprint)
        if current is None or (
            _parse_datetime(marker.created_at),
            marker.comment_id or "",
        ) >= (
            _parse_datetime(current.created_at),
            current.comment_id or "",
        ):
            latest[marker.trigger_fingerprint] = marker
    return latest


def _front_matter_fields(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = FIELD_RE.match(line)
        if match is None:
            continue
        key = match.group(1).strip().lower().replace("-", "_").replace(" ", "_")
        fields[key] = match.group(2).strip().strip("\"'")
    return fields


def _metadata_fields(text: str) -> dict[str, str]:
    fields = _front_matter_fields(text)
    for line in text.splitlines():
        match = FIELD_RE.match(line)
        if match is None:
            continue
        key = match.group(1).strip().lower().replace("-", "_").replace(" ", "_")
        if key in {
            "session_id",
            "target_session_id",
            "worker_session_id",
            "trigger_fingerprint",
            "source_trigger_fingerprint",
            "fingerprint",
        }:
            fields.setdefault(key, match.group(2).strip().strip("\"'`"))
    return fields


def _pending_identity_from_filename(path: str | Path) -> tuple[str, str]:
    target = Path(path)
    stem = target.stem
    match = PENDING_FILENAME_RE.search(stem)
    if match is None:
        raise ValueError(
            "pending filename must be <session_id>_<fingerprint>.md "
            "where fingerprint starts with issue-, step2-, or test-"
        )
    return stem[: match.start()], stem[match.start() + 1 :]


def read_pending_record(path: str | Path) -> PendingRecord:
    """Read session_id and trigger_fingerprint from a pending markdown file."""

    target = Path(path)
    text = target.read_text(encoding="utf-8")
    fields = _metadata_fields(text)
    session_id = (
        fields.get("session_id")
        or fields.get("target_session_id")
        or fields.get("worker_session_id")
    )
    trigger_fingerprint = (
        fields.get("trigger_fingerprint")
        or fields.get("source_trigger_fingerprint")
        or fields.get("fingerprint")
    )

    if not session_id or not trigger_fingerprint:
        filename_session_id, filename_fingerprint = _pending_identity_from_filename(target)
        session_id = session_id or filename_session_id
        trigger_fingerprint = trigger_fingerprint or filename_fingerprint

    return PendingRecord(
        session_id=session_id,
        trigger_fingerprint=trigger_fingerprint,
        path=str(target),
    )


def iter_pending_records(pending_dir: str | Path) -> tuple[PendingRecord, ...]:
    target_dir = Path(pending_dir)
    if not target_dir.exists():
        return ()

    records: list[PendingRecord] = []
    for path in sorted(target_dir.glob("*.md")):
        if path.name.startswith("."):
            continue
        records.append(read_pending_record(path))
    return tuple(records)


def archive_destination(source_path: str | Path, archive_dir: str | Path) -> Path:
    source = Path(source_path)
    target_dir = Path(archive_dir)
    candidate = target_dir / source.name
    if not candidate.exists():
        return candidate

    for index in range(2, 10_000):
        candidate = target_dir / f"{source.stem}.{index}{source.suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate archive path for {source.name}")


def human_waiting_destination(
    source_path: str | Path,
    human_waiting_dir: str | Path,
) -> Path:
    source = Path(source_path)
    target_dir = Path(human_waiting_dir)
    candidate = target_dir / source.name
    if not candidate.exists():
        return candidate

    for index in range(2, 10_000):
        candidate = target_dir / f"{source.stem}.{index}{source.suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate human_wating path for {source.name}")


def reconcile_pending_records(
    pending_records: Iterable[PendingRecord],
    markers: Iterable[AgentMarker],
    *,
    archive_dir: str | Path,
    pending_dir: str | Path,
    human_waiting_dir: str | Path | None = None,
    dry_run: bool = False,
) -> tuple[PendingLifecycleResult, ...]:
    markers_by_fingerprint = latest_marker_by_fingerprint(markers)
    target_human_waiting_dir = (
        Path(human_waiting_dir)
        if human_waiting_dir is not None
        else Path(pending_dir).parent / HUMAN_WAITING_DIR_NAME
    )
    results: list[PendingLifecycleResult] = []

    for pending in pending_records:
        marker = markers_by_fingerprint.get(pending.trigger_fingerprint)
        bucket = _bucket_for_path(
            pending.path,
            pending_dir=pending_dir,
            human_waiting_dir=target_human_waiting_dir,
        )
        if marker is None:
            if bucket == "human_waiting":
                results.append(
                    PendingLifecycleResult(
                        pending=pending,
                        marker=None,
                        action="human_waiting",
                        moved=False,
                        human_waiting_path=str(Path(pending.path)),
                        human_waiting=True,
                        reason="no_marker",
                    )
                )
                continue
            results.append(
                PendingLifecycleResult(
                    pending=pending,
                    marker=None,
                    action="keep_pending",
                    reason="no_marker",
                )
            )
            continue

        if marker.status in HUMAN_WAITING_STATUSES:
            destination = human_waiting_destination(
                pending.path,
                target_human_waiting_dir,
            )
            if bucket == "human_waiting" or dry_run:
                results.append(
                    PendingLifecycleResult(
                        pending=pending,
                        marker=marker,
                        action="human_waiting",
                        status=marker.status,
                        moved=False,
                        human_waiting_path=str(destination),
                        reassign_required=marker.status == "reassign_required",
                        authentication_blocked=marker.status == "authentication_blocked",
                        human_waiting=True,
                        reason=f"{marker.status}_marker",
                    )
                )
                continue

            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                Path(pending.path).rename(destination)
            except Exception as exc:
                results.append(
                    PendingLifecycleResult(
                        pending=pending,
                        marker=marker,
                        action="human_waiting",
                        status=marker.status,
                        moved=False,
                        human_waiting_path=str(destination),
                        reassign_required=marker.status == "reassign_required",
                        authentication_blocked=marker.status == "authentication_blocked",
                        human_waiting=True,
                        reason="human_waiting_failed",
                        error=str(exc),
                    )
                )
                continue

            results.append(
                PendingLifecycleResult(
                    pending=pending,
                    marker=marker,
                    action="human_waiting",
                    status=marker.status,
                    moved=True,
                    human_waiting_path=str(destination),
                    reassign_required=marker.status == "reassign_required",
                    authentication_blocked=marker.status == "authentication_blocked",
                    human_waiting=True,
                    reason=f"{marker.status}_marker",
                )
            )
            continue

        if marker.status not in ARCHIVE_STATUSES:
            if bucket == "human_waiting":
                results.append(
                    PendingLifecycleResult(
                        pending=pending,
                        marker=marker,
                        action="human_waiting",
                        status=marker.status,
                        human_waiting=True,
                        human_waiting_path=str(Path(pending.path)),
                        reason="unknown_marker_status",
                    )
                )
                continue
            results.append(
                PendingLifecycleResult(
                    pending=pending,
                    marker=marker,
                    action="keep_pending",
                    status=marker.status,
                    reason="unknown_marker_status",
                )
            )
            continue

        destination = archive_destination(pending.path, archive_dir)
        if dry_run:
            results.append(
                PendingLifecycleResult(
                    pending=pending,
                    marker=marker,
                    action="archive",
                    status=marker.status,
                    moved=False,
                    archive_path=str(destination),
                    reason="done_marker",
                )
            )
            continue

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            Path(pending.path).rename(destination)
        except Exception as exc:
            results.append(
                PendingLifecycleResult(
                    pending=pending,
                    marker=marker,
                    action="archive",
                    status=marker.status,
                    moved=False,
                    archive_path=str(destination),
                    reason="archive_failed",
                    error=str(exc),
                )
            )
            continue

        results.append(
            PendingLifecycleResult(
                pending=pending,
                marker=marker,
                action="archive",
                status=marker.status,
                moved=True,
                archive_path=str(destination),
                reason="done_marker",
            )
        )

    return tuple(results)


def unresolved_pending_issue_numbers(
    results: Iterable[PendingLifecycleResult],
) -> tuple[int, ...]:
    numbers: list[int] = []
    seen: set[int] = set()
    for result in results:
        if result.action != "keep_pending" or result.reason != "no_marker":
            continue
        issue_number = _issue_number_from_fingerprint(result.pending.trigger_fingerprint)
        if issue_number is None or issue_number in seen:
            continue
        seen.add(issue_number)
        numbers.append(issue_number)
    return tuple(sorted(numbers))


def reconcile_pending_with_issue_snapshots(
    summary: PendingLifecycleSummary,
    issues: Iterable[IssueSnapshot],
    *,
    archive_dir: str | Path | None = None,
    dry_run: bool | None = None,
) -> PendingLifecycleSummary:
    issue_by_number = {issue.issue_number: issue for issue in issues}
    if not issue_by_number:
        return summary

    marker_lookup = latest_marker_by_fingerprint(
        collect_agent_markers_from_issues(issue_by_number.values())
    )
    target_archive_dir = archive_dir if archive_dir is not None else summary.archive_dir
    target_dry_run = summary.dry_run if dry_run is None else dry_run
    results: list[PendingLifecycleResult] = []

    for result in summary.results:
        if result.reason != "no_marker" or result.action not in {
            "keep_pending",
            "human_waiting",
        }:
            results.append(result)
            continue

        issue_number = _issue_number_from_fingerprint(result.pending.trigger_fingerprint)
        issue = issue_by_number.get(issue_number) if issue_number is not None else None
        if issue is None:
            results.append(result)
            continue

        marker = marker_lookup.get(result.pending.trigger_fingerprint)
        issue_state = (issue.issue_state or "").lower()
        if marker is not None and marker.status in ARCHIVE_STATUSES:
            reason = (
                "done_marker_closed_issue"
                if issue_state == "closed"
                else "done_marker"
            )
            results.append(
                _archive_pending_result(
                    result.pending,
                    marker,
                    archive_dir=target_archive_dir,
                    dry_run=target_dry_run,
                    reason=reason,
                )
            )
            continue

        if issue_state == "closed":
            results.append(
                _archive_pending_result(
                    result.pending,
                    marker,
                    archive_dir=target_archive_dir,
                    dry_run=target_dry_run,
                    reason="issue_closed_without_marker",
                )
            )
            continue

        results.append(result)

    return PendingLifecycleSummary(
        results=tuple(results),
        pending_dir=summary.pending_dir,
        human_waiting_dir=summary.human_waiting_dir,
        archive_dir=str(Path(target_archive_dir)),
        dry_run=target_dry_run,
    )


def _archive_pending_result(
    pending: PendingRecord,
    marker: AgentMarker | None,
    *,
    archive_dir: str | Path,
    dry_run: bool,
    reason: str,
) -> PendingLifecycleResult:
    destination = archive_destination(pending.path, archive_dir)
    status = marker.status if marker is not None else None
    if dry_run:
        return PendingLifecycleResult(
            pending=pending,
            marker=marker,
            action="archive",
            status=status,
            moved=False,
            archive_path=str(destination),
            reason=reason,
        )

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        Path(pending.path).rename(destination)
    except Exception as exc:
        return PendingLifecycleResult(
            pending=pending,
            marker=marker,
            action="archive",
            status=status,
            moved=False,
            archive_path=str(destination),
            reason="archive_failed",
            error=str(exc),
        )

    return PendingLifecycleResult(
        pending=pending,
        marker=marker,
        action="archive",
        status=status,
        moved=True,
        archive_path=str(destination),
        reason=reason,
    )


def reconcile_pending_from_issues(
    issues: Iterable[IssueSnapshot],
    *,
    pending_dir: str | Path,
    archive_dir: str | Path,
    dry_run: bool = False,
) -> PendingLifecycleSummary:
    human_waiting_dir = Path(pending_dir).parent / HUMAN_WAITING_DIR_NAME
    records = tuple(
        sorted(
            tuple(iter_pending_records(pending_dir))
            + tuple(iter_pending_records(human_waiting_dir)),
            key=lambda record: record.path,
        )
    )
    markers = collect_agent_markers_from_issues(issues)
    results = reconcile_pending_records(
        records,
        markers,
        archive_dir=archive_dir,
        pending_dir=pending_dir,
        human_waiting_dir=human_waiting_dir,
        dry_run=dry_run,
    )
    return PendingLifecycleSummary(
        results=results,
        pending_dir=str(Path(pending_dir)),
        human_waiting_dir=str(human_waiting_dir),
        archive_dir=str(Path(archive_dir)),
        dry_run=dry_run,
    )


def lifecycle_result_to_dict(result: PendingLifecycleResult) -> dict[str, object]:
    payload = asdict(result)
    marker = result.marker
    payload["marker"] = asdict(marker) if marker is not None else None
    payload["pending"] = asdict(result.pending)
    return payload


def lifecycle_summary_to_dict(summary: PendingLifecycleSummary) -> dict[str, object]:
    result_tuple = summary.results
    return {
        "schema_version": 1,
        "pending_dir": summary.pending_dir,
        "human_waiting_dir": summary.human_waiting_dir,
        "archive_dir": summary.archive_dir,
        "dry_run": summary.dry_run,
        "pending_count": len(result_tuple),
        "matched_count": sum(1 for result in result_tuple if result.marker is not None),
        "archive_planned_count": sum(
            1 for result in result_tuple if result.action == "archive"
        ),
        "archived_count": sum(1 for result in result_tuple if result.moved),
        "kept_pending_count": sum(
            1 for result in result_tuple if result.action == "keep_pending"
        ),
        "human_waiting_planned_count": sum(
            1 for result in result_tuple if result.action == "human_waiting"
        ),
        "human_waiting_count": sum(1 for result in result_tuple if result.human_waiting),
        "authentication_blocked_fingerprints": [
            result.pending.trigger_fingerprint
            for result in result_tuple
            if result.authentication_blocked
        ],
        "reassign_required_fingerprints": list(
            summary.reassign_required_fingerprints
        ),
        "human_waiting_fingerprints": list(summary.human_waiting_fingerprints),
        "items": [lifecycle_result_to_dict(result) for result in result_tuple],
    }
