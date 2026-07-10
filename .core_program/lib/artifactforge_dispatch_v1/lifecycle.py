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

VALID_MARKER_STATUSES = frozenset(
    {"done", "reassign_required", "authentication_blocked"}
)
ARCHIVE_STATUSES = frozenset({"done"})
PENDING_STATUSES = frozenset({"reassign_required", "authentication_blocked"})


@dataclass(frozen=True)
class PendingLifecycleResult:
    pending: PendingRecord
    marker: AgentMarker | None
    action: str
    status: str | None = None
    moved: bool = False
    archive_path: str | None = None
    reassign_required: bool = False
    authentication_blocked: bool = False
    reason: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class PendingLifecycleSummary:
    results: tuple[PendingLifecycleResult, ...]
    pending_dir: str
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


def reconcile_pending_records(
    pending_records: Iterable[PendingRecord],
    markers: Iterable[AgentMarker],
    *,
    archive_dir: str | Path,
    dry_run: bool = False,
) -> tuple[PendingLifecycleResult, ...]:
    markers_by_fingerprint = latest_marker_by_fingerprint(markers)
    results: list[PendingLifecycleResult] = []

    for pending in pending_records:
        marker = markers_by_fingerprint.get(pending.trigger_fingerprint)
        if marker is None:
            results.append(
                PendingLifecycleResult(
                    pending=pending,
                    marker=None,
                    action="keep_pending",
                    reason="no_marker",
                )
            )
            continue

        if marker.status == "reassign_required":
            if marker.thread_id and pending.session_id == marker.thread_id:
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
                            reassign_required=True,
                            reason="reassign_required_marker",
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
                            reassign_required=True,
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
                        reassign_required=True,
                        reason="reassign_required_marker",
                    )
                )
                continue

            results.append(
                PendingLifecycleResult(
                    pending=pending,
                    marker=marker,
                    action="keep_pending",
                    status=marker.status,
                    reason="reassign_handoff_pending",
                )
            )
            continue

        if marker.status in PENDING_STATUSES:
            results.append(
                PendingLifecycleResult(
                    pending=pending,
                    marker=marker,
                    action="keep_pending",
                    status=marker.status,
                    reassign_required=marker.status == "reassign_required",
                    authentication_blocked=marker.status == "authentication_blocked",
                    reason=f"{marker.status}_marker",
                )
            )
            continue

        if marker.status not in ARCHIVE_STATUSES:
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


def reconcile_pending_from_issues(
    issues: Iterable[IssueSnapshot],
    *,
    pending_dir: str | Path,
    archive_dir: str | Path,
    dry_run: bool = False,
) -> PendingLifecycleSummary:
    records = iter_pending_records(pending_dir)
    markers = collect_agent_markers_from_issues(issues)
    results = reconcile_pending_records(
        records,
        markers,
        archive_dir=archive_dir,
        dry_run=dry_run,
    )
    return PendingLifecycleSummary(
        results=results,
        pending_dir=str(Path(pending_dir)),
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
        "authentication_blocked_fingerprints": [
            result.pending.trigger_fingerprint
            for result in result_tuple
            if result.authentication_blocked
        ],
        "reassign_required_fingerprints": list(
            summary.reassign_required_fingerprints
        ),
        "items": [lifecycle_result_to_dict(result) for result in result_tuple],
    }
