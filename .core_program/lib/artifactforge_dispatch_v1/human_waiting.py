"""Human-waiting summary helpers for ArtifactForge."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .lifecycle import iter_pending_records
from .models import PendingRecord


ISSUE_NUMBER_RE = re.compile(r"^issue-(\d+)-")
STATE_TEXT_KEYS = (
    "reason",
    "skip_reason",
    "message",
    "detail",
    "notes",
    "description",
)
SESSION_ID_KEYS = (
    "session_id",
    "worker_session_id",
    "target_session_id",
    "router_session_id",
)


@dataclass(frozen=True)
class HumanWaitingRecordSummary:
    pending: PendingRecord
    issue_number: int | None
    pending_state_path: str | None = None
    pending_state_status: str | None = None
    pending_state_reason: str | None = None
    pending_state_session_id: str | None = None


def summarize_human_waiting_records(
    human_waiting_dir: str | Path,
    *,
    pending_state_path: str | Path | None = None,
) -> tuple[HumanWaitingRecordSummary, ...]:
    """Summarize human-waiting records with optional pending-state details."""

    records = tuple(sorted(iter_pending_records(human_waiting_dir), key=lambda item: item.path))
    state_records = _read_pending_state_records(pending_state_path)
    summaries: list[HumanWaitingRecordSummary] = []
    for record in records:
        state_record = _matching_pending_state_record(
            state_records,
            pending_path=Path(record.path),
            trigger_fingerprint=record.trigger_fingerprint,
        )
        summaries.append(
            HumanWaitingRecordSummary(
                pending=record,
                issue_number=_issue_number_from_fingerprint(record.trigger_fingerprint),
                pending_state_path=_pending_state_text(
                    state_record,
                    ("pending_path", "path", "file", "pending_file"),
                ),
                pending_state_status=_pending_state_status(state_record),
                pending_state_reason=_pending_state_reason(state_record),
                pending_state_session_id=_pending_state_text(
                    state_record,
                    SESSION_ID_KEYS,
                ),
            )
        )
    return tuple(summaries)


def human_waiting_records_to_dict(
    records: Iterable[HumanWaitingRecordSummary],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "pending": {
                "session_id": record.pending.session_id,
                "trigger_fingerprint": record.pending.trigger_fingerprint,
                "path": record.pending.path,
            },
            "issue_number": record.issue_number,
            "pending_state_path": record.pending_state_path,
            "pending_state_status": record.pending_state_status,
            "pending_state_reason": record.pending_state_reason,
            "pending_state_session_id": record.pending_state_session_id,
        }
        for record in records
    )


def _issue_number_from_fingerprint(trigger_fingerprint: str) -> int | None:
    match = ISSUE_NUMBER_RE.match(trigger_fingerprint)
    if match is None:
        return None
    return int(match.group(1))


def _read_pending_state_records(path: str | Path | None) -> tuple[dict[str, object], ...]:
    if path is None:
        return ()

    state_path = Path(path)
    if not state_path.exists():
        return ()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return _pending_state_records_from_node(payload)


def _pending_state_records_from_node(payload: object) -> tuple[dict[str, object], ...]:
    if isinstance(payload, list):
        return tuple(item for item in payload if isinstance(item, dict))
    if not isinstance(payload, dict):
        return ()
    if _looks_like_pending_state_record(payload):
        return (payload,)
    for key in ("records", "pending_records", "pending", "items"):
        if key in payload:
            records = _pending_state_records_from_node(payload[key])
            if records:
                return records
    records = []
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        record = dict(value)
        record.setdefault("pending_path", key)
        records.append(record)
    return tuple(records)


def _looks_like_pending_state_record(payload: dict[str, object]) -> bool:
    if "status" not in payload and "state" not in payload:
        return False
    return any(
        key in payload
        for key in (
            "pending_path",
            "path",
            "file",
            "pending_file",
            "trigger_fingerprint",
            "fingerprint",
        )
    )


def _matching_pending_state_record(
    records: Iterable[dict[str, object]],
    *,
    pending_path: Path,
    trigger_fingerprint: str,
) -> dict[str, object] | None:
    for record in records:
        if _pending_state_record_matches(
            record,
            pending_path=pending_path,
            trigger_fingerprint=trigger_fingerprint,
        ):
            return record
    return None


def _pending_state_record_matches(
    record: dict[str, object],
    *,
    pending_path: Path,
    trigger_fingerprint: str,
) -> bool:
    state_pending_path = _pending_state_text(
        record,
        ("pending_path", "path", "file", "pending_file"),
    )
    if state_pending_path and _pending_paths_match(state_pending_path, pending_path):
        return True
    state_fingerprint = _pending_state_text(
        record,
        ("trigger_fingerprint", "fingerprint"),
    )
    return bool(
        state_fingerprint
        and trigger_fingerprint
        and _fingerprints_match(state_fingerprint, trigger_fingerprint)
    )


def _pending_paths_match(state_path: str, pending_path: Path) -> bool:
    state_text = state_path.strip().replace("\\", "/")
    pending_text = str(pending_path).replace("\\", "/")
    if not state_text:
        return False
    if state_text == pending_text:
        return True
    if Path(state_text).name == pending_path.name:
        return True
    return pending_text.endswith("/" + state_text.lstrip("./"))


def _fingerprints_match(left: str, right: str) -> bool:
    return left == right or _safe_filename_part(left) == _safe_filename_part(right)


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "EMPTY"


def _pending_state_text(
    record: dict[str, object] | None,
    keys: tuple[str, ...],
) -> str | None:
    if record is None:
        return None
    for key in keys:
        value = record.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _pending_state_status(record: dict[str, object] | None) -> str | None:
    if record is None:
        return None
    text = _pending_state_text(record, ("status", "state"))
    if not text:
        return None
    return text.lower().replace("-", "_")


def _pending_state_reason(record: dict[str, object] | None) -> str | None:
    if record is None:
        return None
    return _pending_state_text(record, STATE_TEXT_KEYS)
