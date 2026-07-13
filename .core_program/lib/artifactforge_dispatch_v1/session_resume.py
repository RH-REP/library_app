"""Session resume planning helpers for ArtifactForge."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .dispatch import (
    DEFAULT_CODEX_BIN,
    DEFAULT_PENDING_DIR,
    REPO_ROOT,
    _default_runner,
    _run_resume_session,
    build_session_router_prompt,
    build_worker_prompt,
    parse_queue_file,
)
from .human_waiting import (
    human_waiting_records_to_dict,
    summarize_human_waiting_records,
)
from .lifecycle import iter_pending_records
from .queueing import human_waiting_dir_for


REQUEST_FIELD_RE = re.compile(r"^\s*([A-Za-z\u3040-\u30ff\u4e00-\u9fff_ -]+)\s*:\s*(.*?)\s*$")
REQUEST_FIELD_ALIASES = {
    "datetime": ("日時", "date", "timestamp"),
    "pending_fingerprints": ("Pending fingerprints", "pending fingerprints"),
    "worker_session_id": ("Worker session ID", "worker_session_id", "session_id"),
    "query": ("問い合わせ内容", "inquiry", "question", "query"),
}


@dataclass(frozen=True)
class RequestForHumanMemo:
    path: str
    datetime_text: str | None
    pending_fingerprints: tuple[str, ...]
    worker_session_id: str | None
    query: str | None
    raw_text: str


@dataclass(frozen=True)
class SessionResumePlan:
    session_id: str | None
    recipient_role: str | None
    session_visibility: str | None
    prompt: str | None
    command: tuple[str, ...] | None
    source_kind: str
    reason: str
    router_session_id: str | None = None
    selected_pending_path: str | None = None
    selected_trigger_fingerprint: str | None = None
    selected_issue_number: int | None = None
    selected_record: Any | None = None
    request_for_human_memos: tuple[RequestForHumanMemo, ...] = ()
    human_waiting_records: tuple[Any, ...] = ()
    pending_records: tuple[Any, ...] = ()
    worker_session_ids: tuple[str, ...] = ()


def read_request_for_human_memos(
    request_for_human_dir: str | Path,
) -> tuple[RequestForHumanMemo, ...]:
    target_dir = Path(request_for_human_dir)
    if not target_dir.exists():
        return ()
    memos = [
        parse_request_for_human_memo(path)
        for path in sorted(target_dir.glob("*.md"))
        if path.name != ".gitkeep"
    ]
    return tuple(memo for memo in memos if memo.raw_text.strip())


def parse_request_for_human_memo(path: str | Path) -> RequestForHumanMemo:
    target = Path(path)
    raw_text = target.read_text(encoding="utf-8")
    fields = _parse_request_fields(raw_text)
    pending_fingerprints = _split_pending_fingerprints(
        _field_text(fields, REQUEST_FIELD_ALIASES["pending_fingerprints"])
    )
    return RequestForHumanMemo(
        path=str(target),
        datetime_text=_field_text(fields, REQUEST_FIELD_ALIASES["datetime"]),
        pending_fingerprints=pending_fingerprints,
        worker_session_id=_field_text(
            fields,
            REQUEST_FIELD_ALIASES["worker_session_id"],
        ),
        query=_field_text(fields, REQUEST_FIELD_ALIASES["query"]),
        raw_text=raw_text,
    )


def plan_session_resume(
    *,
    repo_dir: str | Path = REPO_ROOT,
    assignment_state_path: str | Path | None = None,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    request_for_human_dir: str | Path | None = None,
    human_waiting_dir: str | Path | None = None,
    pending_state_path: str | Path | None = None,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
) -> SessionResumePlan:
    repo_root = Path(repo_dir)
    state = _read_assignment_state(assignment_state_path, repo_dir=repo_root)
    router_session_id = _router_session_id(state)
    target_human_waiting_dir = (
        Path(human_waiting_dir)
        if human_waiting_dir is not None
        else human_waiting_dir_for(pending_dir)
    )
    target_request_for_human_dir = (
        Path(request_for_human_dir)
        if request_for_human_dir is not None
        else repo_root / ".core_program" / "request_for_human"
    )

    request_memos = read_request_for_human_memos(target_request_for_human_dir)
    human_waiting_records = summarize_human_waiting_records(
        target_human_waiting_dir,
        pending_state_path=pending_state_path,
    )
    pending_records = tuple(sorted(iter_pending_records(pending_dir), key=lambda item: item.path))

    worker_session_ids = _unique_session_ids(
        memo.worker_session_id
        for memo in request_memos
        if memo.worker_session_id
    )
    worker_session_ids = _unique_session_ids(
        worker_session_ids
        + tuple(
            record.pending.session_id
            for record in human_waiting_records
            if getattr(record, "pending", None) is not None
        )
        + tuple(record.session_id for record in pending_records)
    )

    if request_memos or human_waiting_records:
        return _build_router_resume_plan(
            repo_dir=repo_root,
            codex_bin=codex_bin,
            router_session_id=router_session_id,
            request_memos=request_memos,
            human_waiting_records=human_waiting_records,
            pending_records=pending_records,
            worker_session_ids=worker_session_ids,
            source_kind="request_for_human"
            if request_memos
            else "human_wating",
        )

    if not pending_records:
        return SessionResumePlan(
            session_id=None,
            recipient_role=None,
            session_visibility=None,
            prompt=None,
            command=None,
            source_kind="idle",
            reason="no_resume_candidates",
            router_session_id=router_session_id,
            request_for_human_memos=request_memos,
            human_waiting_records=human_waiting_records,
            pending_records=pending_records,
            worker_session_ids=worker_session_ids,
        )

    selected_pending = pending_records[0]
    selected_record = parse_queue_file(selected_pending.path)
    if selected_record.recipient_role == "router":
        session_id = router_session_id or selected_record.target_session_id
        prompt = build_session_router_prompt(
            selected_record,
            router_session_id=session_id,
            repo_dir=repo_root,
            pending_dir=pending_dir,
            pending_path=selected_pending.path,
        )
        return SessionResumePlan(
            session_id=session_id,
            recipient_role="router",
            session_visibility="visible",
            prompt=prompt,
            command=_resume_command(codex_bin, repo_root, session_id, prompt),
            source_kind="pending",
            reason="selected_router_pending_record",
            router_session_id=router_session_id,
            selected_pending_path=selected_pending.path,
            selected_trigger_fingerprint=selected_record.trigger_fingerprint,
            selected_issue_number=selected_record.issue_number,
            selected_record=selected_record,
            request_for_human_memos=request_memos,
            human_waiting_records=human_waiting_records,
            pending_records=pending_records,
            worker_session_ids=worker_session_ids,
        )

    session_id = selected_record.target_session_id
    prompt = build_worker_prompt(
        selected_record,
        session_id=session_id,
        repo_dir=repo_root,
    )
    return SessionResumePlan(
        session_id=session_id,
        recipient_role="worker",
        session_visibility="non_visible",
        prompt=prompt,
        command=_resume_command(codex_bin, repo_root, session_id, prompt),
        source_kind="pending",
        reason="selected_worker_pending_record",
        router_session_id=router_session_id,
        selected_pending_path=selected_pending.path,
        selected_trigger_fingerprint=selected_record.trigger_fingerprint,
        selected_issue_number=selected_record.issue_number,
        selected_record=selected_record,
        request_for_human_memos=request_memos,
        human_waiting_records=human_waiting_records,
        pending_records=pending_records,
        worker_session_ids=worker_session_ids,
    )


def resume_session(
    plan: SessionResumePlan,
    *,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    runner: Any = _default_runner,
) -> Any:
    if plan.session_id is None or plan.prompt is None:
        return None
    return _run_resume_session(
        runner,
        plan.session_id,
        plan.prompt,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
        visible=plan.session_visibility != "non_visible",
    )


def session_resume_plan_to_dict(plan: SessionResumePlan) -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_kind": plan.source_kind,
        "reason": plan.reason,
        "recipient_role": plan.recipient_role,
        "selected_session_id": plan.session_id,
        "session_visibility": plan.session_visibility,
        "router_session_id": plan.router_session_id,
        "selected_pending_path": plan.selected_pending_path,
        "selected_trigger_fingerprint": plan.selected_trigger_fingerprint,
        "selected_issue_number": plan.selected_issue_number,
        "worker_session_ids": list(plan.worker_session_ids),
        "request_for_human_count": len(plan.request_for_human_memos),
        "human_waiting_count": len(plan.human_waiting_records),
        "pending_count": len(plan.pending_records),
        "request_for_human_paths": [memo.path for memo in plan.request_for_human_memos],
        "human_waiting_paths": [
            getattr(record.pending, "path", "")
            for record in plan.human_waiting_records
            if getattr(record, "pending", None) is not None
        ],
        "pending_paths": [record.path for record in plan.pending_records],
        "command": list(plan.command[:-1]) + ["<prompt>"] if plan.command else None,
        "prompt_preview": _prompt_preview(plan.prompt),
    }


def _build_router_resume_plan(
    *,
    repo_dir: Path,
    codex_bin: str | Path,
    router_session_id: str | None,
    request_memos: tuple[RequestForHumanMemo, ...],
    human_waiting_records: tuple[Any, ...],
    pending_records: tuple[Any, ...],
    worker_session_ids: tuple[str, ...],
    source_kind: str,
) -> SessionResumePlan:
    prompt = _build_router_resume_prompt(
        repo_dir=repo_dir,
        router_session_id=router_session_id,
        request_memos=request_memos,
        human_waiting_records=human_waiting_records,
        pending_records=pending_records,
        worker_session_ids=worker_session_ids,
    )
    command = (
        _resume_command(codex_bin, repo_dir, router_session_id or "<router-session-id>", prompt)
        if router_session_id
        else None
    )
    return SessionResumePlan(
        session_id=router_session_id,
        recipient_role="router",
        session_visibility="visible",
        prompt=prompt,
        command=command,
        source_kind=source_kind,
        reason=(
            "request_for_human_present"
            if request_memos
            else "human_wating_present"
        ),
        router_session_id=router_session_id,
        request_for_human_memos=request_memos,
        human_waiting_records=human_waiting_records,
        pending_records=pending_records,
        worker_session_ids=worker_session_ids,
    )


def _build_router_resume_prompt(
    *,
    repo_dir: Path,
    router_session_id: str | None,
    request_memos: tuple[RequestForHumanMemo, ...],
    human_waiting_records: tuple[Any, ...],
    pending_records: tuple[Any, ...],
    worker_session_ids: tuple[str, ...],
) -> str:
    payload = {
        "schema_version": 1,
        "repository": str(repo_dir),
        "recipient_role": "router",
        "target_session_id": router_session_id or "<router-session-id>",
        "candidate_worker_session_ids": list(worker_session_ids),
        "request_for_human_memos": [
            {
                "path": memo.path,
                "datetime": memo.datetime_text,
                "pending_fingerprints": list(memo.pending_fingerprints),
                "worker_session_id": memo.worker_session_id,
                "query": memo.query,
            }
            for memo in request_memos
        ],
        "human_waiting_records": human_waiting_records_to_dict(human_waiting_records),
        "pending_records": [
            {
                "path": record.path,
                "session_id": record.session_id,
                "trigger_fingerprint": record.trigger_fingerprint,
            }
            for record in pending_records
        ],
        "routing_contract": {
            "router_is_visible": True,
            "router_reads_request_for_human_first": True,
            "router_reads_human_wating_second": True,
            "router_may_resume_worker_sessions_after_review": True,
            "worker_sessions_default_visibility": "non_visible",
            "subagent_sessions_default_visibility": "non_visible",
            "do_not_do_worker_work_directly": True,
        },
    }
    return (
        "ArtifactForge Session Resume Prompt v1\n\n"
        "You are the visible Session_router.\n"
        "Python selected this router session because unresolved human requests or "
        "human_wating records were found.\n\n"
        "Task:\n"
        "- Read `.core_program/request_for_human/` first.\n"
        "- Then inspect the human_wating and pending records below.\n"
        "- Use the listed worker session IDs as context.\n"
        "- Decide whether to ask the user, resume a worker, or continue routing.\n"
        "- Do not do worker implementation work yourself.\n"
        "- If you need human input, write a resumption memo before asking.\n"
        "- Leave pending/archive movement to Python fetch/reconcile.\n\n"
        "SESSION_RESUME_V1_INPUT\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def _resume_command(
    codex_bin: str | Path,
    repo_dir: str | Path,
    session_id: str,
    prompt: str,
) -> tuple[str, ...]:
    return (
        str(codex_bin),
        "resume",
        "--cd",
        str(repo_dir),
        "--include-non-interactive",
        session_id,
        prompt,
    )


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


def _parse_request_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        match = REQUEST_FIELD_RE.match(line)
        if match is not None:
            key = match.group(1).strip()
            value = match.group(2).strip()
            if current_key is not None:
                fields[current_key] = "\n".join(current_lines).strip()
            current_key = key
            current_lines = [value] if value else []
            continue
        if current_key is not None:
            current_lines.append(line)
    if current_key is not None:
        fields[current_key] = "\n".join(current_lines).strip()
    for key, value in tuple(fields.items()):
        normalized = _normalize_field_name(key)
        if normalized not in fields and value:
            fields[normalized] = value
    return fields


def _field_text(fields: dict[str, str], names: Sequence[str]) -> str | None:
    for name in names:
        value = fields.get(name)
        if value is None:
            value = fields.get(_normalize_field_name(name))
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _split_pending_fingerprints(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    parts = [
        part.strip()
        for part in re.split(r"[\s,]+", text)
        if part.strip()
    ]
    return tuple(parts)


def _normalize_field_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _unique_session_ids(values: Iterable[str | None]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return tuple(ordered)


def _prompt_preview(prompt: str | None, *, limit: int = 800) -> str | None:
    if prompt is None:
        return None
    if len(prompt) <= limit:
        return prompt
    return prompt[: limit - 1] + "…"
