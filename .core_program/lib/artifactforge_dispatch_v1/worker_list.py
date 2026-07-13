"""Worker session listing helpers for ArtifactForge."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .human_waiting import summarize_human_waiting_records
from .lifecycle import iter_pending_records
from .queueing import human_waiting_dir_for
from .session_resume import read_request_for_human_memos


CORE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CORE_DIR.parent


@dataclass(frozen=True)
class WorkerSessionSource:
    kind: str
    path: str | None = None
    issue_number: int | None = None
    status: str | None = None
    sub_artifact_path: str | None = None
    trigger_fingerprint: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class WorkerSessionEntry:
    session_id: str
    sources: tuple[WorkerSessionSource, ...]

    @property
    def source_kinds(self) -> tuple[str, ...]:
        return tuple(source.kind for source in self.sources)


@dataclass(frozen=True)
class WorkerSessionCatalog:
    router_session_id: str | None
    entries: tuple[WorkerSessionEntry, ...]

    @property
    def worker_session_ids(self) -> tuple[str, ...]:
        return tuple(entry.session_id for entry in self.entries)


def worker_session_entry_at_index(
    catalog: WorkerSessionCatalog,
    index: int,
) -> WorkerSessionEntry | None:
    if index < 1 or index > len(catalog.entries):
        return None
    return catalog.entries[index - 1]


@dataclass
class _WorkerSessionEntryBuilder:
    session_id: str
    sources: list[WorkerSessionSource] = field(default_factory=list)

    def add(self, source: WorkerSessionSource) -> None:
        self.sources.append(source)

    def build(self) -> WorkerSessionEntry:
        return WorkerSessionEntry(
            session_id=self.session_id,
            sources=tuple(self.sources),
        )


def collect_worker_session_catalog(
    *,
    repo_dir: str | Path = REPO_ROOT,
    assignment_state_path: str | Path | None = None,
    pending_dir: str | Path | None = None,
    request_for_human_dir: str | Path | None = None,
    human_waiting_dir: str | Path | None = None,
    pending_state_path: str | Path | None = None,
) -> WorkerSessionCatalog:
    repo_root = Path(repo_dir)
    state = _read_assignment_state(assignment_state_path, repo_dir=repo_root)
    router_session_id = _router_session_id(state)
    target_pending_dir = (
        Path(pending_dir) if pending_dir is not None else repo_root / ".core_program" / "pending"
    )
    target_human_waiting_dir = (
        Path(human_waiting_dir)
        if human_waiting_dir is not None
        else human_waiting_dir_for(target_pending_dir)
    )
    target_request_for_human_dir = (
        Path(request_for_human_dir)
        if request_for_human_dir is not None
        else repo_root / ".core_program" / "request_for_human"
    )

    builders: dict[str, _WorkerSessionEntryBuilder] = {}

    def builder_for(session_id: str | None) -> _WorkerSessionEntryBuilder | None:
        resolved = str(session_id or "").strip()
        if not resolved or resolved == router_session_id:
            return None
        builder = builders.get(resolved)
        if builder is None:
            builder = _WorkerSessionEntryBuilder(session_id=resolved)
            builders[resolved] = builder
        return builder

    for assignment in state.get("assignments", []) or []:
        session_id = str(assignment.get("session_id") or "").strip()
        builder = builder_for(session_id)
        if builder is None:
            continue
        issue_number = _as_int(assignment.get("issue_number"))
        status = _normalized_status(assignment.get("status"))
        sub_artifact_path = _text(assignment.get("sub_artifact_path"))
        builder.add(
            WorkerSessionSource(
                kind="assignment_state",
                issue_number=issue_number,
                status=status,
                sub_artifact_path=sub_artifact_path,
                note=_assignment_note(issue_number=issue_number, status=status),
            )
        )

    for pending in sorted(iter_pending_records(target_pending_dir), key=lambda item: item.path):
        builder = builder_for(pending.session_id)
        if builder is None:
            continue
        builder.add(
            WorkerSessionSource(
                kind="pending",
                path=pending.path,
                trigger_fingerprint=pending.trigger_fingerprint,
                issue_number=_issue_number_from_fingerprint(pending.trigger_fingerprint),
                note=f"pending {Path(pending.path).name}",
            )
        )

    for waiting in summarize_human_waiting_records(
        target_human_waiting_dir,
        pending_state_path=pending_state_path,
    ):
        builder = builder_for(waiting.pending.session_id)
        if builder is None:
            continue
        builder.add(
            WorkerSessionSource(
                kind="human_wating",
                path=waiting.pending.path,
                trigger_fingerprint=waiting.pending.trigger_fingerprint,
                issue_number=waiting.issue_number,
                status=waiting.pending_state_status,
                note=_summarize_waiting_status(
                    waiting.pending_state_status,
                    waiting.pending_state_reason,
                    waiting.pending_state_session_id,
                ),
            )
        )

    for memo in read_request_for_human_memos(target_request_for_human_dir):
        builder = builder_for(memo.worker_session_id)
        if builder is None:
            continue
        builder.add(
            WorkerSessionSource(
                kind="request_for_human",
                path=memo.path,
                note=_summarize_request_memo(memo.query, memo.pending_fingerprints),
            )
        )

    entries = tuple(builder.build() for builder in builders.values())
    return WorkerSessionCatalog(router_session_id=router_session_id, entries=entries)


def worker_session_catalog_to_dict(
    catalog: WorkerSessionCatalog,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "router_session_id": catalog.router_session_id,
        "worker_count": len(catalog.entries),
        "worker_session_ids": list(catalog.worker_session_ids),
        "items": [
            {
                "index": index,
                "session_id": entry.session_id,
                "source_kinds": list(entry.source_kinds),
                "sources": [
                    {
                        "kind": source.kind,
                        "path": source.path,
                        "issue_number": source.issue_number,
                        "status": source.status,
                        "sub_artifact_path": source.sub_artifact_path,
                        "trigger_fingerprint": source.trigger_fingerprint,
                        "note": source.note,
                    }
                    for source in entry.sources
                ],
            }
            for index, entry in enumerate(catalog.entries, start=1)
        ],
    }


def human_summary(catalog: WorkerSessionCatalog) -> str:
    lines = [
        "ArtifactForge worker list",
        f"router_session_id: {catalog.router_session_id or '(none)'}",
        f"worker_count: {len(catalog.entries)}",
    ]
    if catalog.entries:
        lines.append("")
    for index, entry in enumerate(catalog.entries, start=1):
        lines.append(f"{index}. {entry.session_id} [{', '.join(entry.source_kinds)}]")
        for source in entry.sources:
            detail = _source_detail(source)
            if detail:
                lines.append(f"   - {detail}")
    return "\n".join(lines)


def _source_detail(source: WorkerSessionSource) -> str:
    parts = [source.kind]
    if source.issue_number is not None:
        parts.append(f"issue #{source.issue_number}")
    if source.status:
        parts.append(f"status={source.status}")
    if source.sub_artifact_path:
        parts.append(f"sub_artifact={source.sub_artifact_path}")
    if source.path:
        parts.append(f"path={source.path}")
    if source.note:
        parts.append(source.note)
    return " ".join(part for part in parts if part)


def _assignment_note(*, issue_number: int | None, status: str | None) -> str | None:
    note_parts = []
    if issue_number is not None:
        note_parts.append(f"issue #{issue_number}")
    if status:
        note_parts.append(status)
    return " ".join(note_parts) or None


def _summarize_waiting_status(
    status: str | None,
    reason: str | None,
    worker_session_id: str | None,
) -> str | None:
    parts = []
    if status:
        parts.append(status)
    if reason:
        parts.append(reason)
    if worker_session_id:
        parts.append(f"worker={worker_session_id}")
    return " ".join(parts) or None


def _summarize_request_memo(query: str | None, pending_fingerprints: Iterable[str]) -> str | None:
    parts = []
    if query:
        parts.append(query)
    fingerprints = tuple(value for value in pending_fingerprints if value)
    if fingerprints:
        parts.append("pending=" + ", ".join(fingerprints))
    return " | ".join(parts) or None


def _read_assignment_state(
    path: str | Path | None,
    *,
    repo_dir: Path,
) -> dict[str, Any]:
    if path is None:
        target = repo_dir / ".core_program" / "assignment_state.json"
    else:
        target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _router_session_id(state: dict[str, Any]) -> str | None:
    value = state.get("router_session_id")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _issue_number_from_fingerprint(trigger_fingerprint: str) -> int | None:
    if not trigger_fingerprint:
        return None
    parts = trigger_fingerprint.split("-", 3)
    if len(parts) < 3 or parts[0] != "issue":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _as_int(value: object) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _normalized_status(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    return text.lower().replace("-", "_")


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
