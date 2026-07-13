"""Worker session resume-by-index helpers for ArtifactForge."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dispatch import _default_runner
from .session_resume import (
    DEFAULT_CODEX_BIN,
    REPO_ROOT,
    SessionResumePlan,
    resume_session,
)
from .worker_list import (
    WorkerSessionCatalog,
    WorkerSessionEntry,
    collect_worker_session_catalog,
    worker_session_catalog_to_dict,
    worker_session_entry_at_index,
)


@dataclass(frozen=True)
class WorkerResumePlan:
    catalog: WorkerSessionCatalog
    selected_index: int
    selected_entry: WorkerSessionEntry
    session_plan: SessionResumePlan
    command: tuple[str, ...] | None

    @property
    def selected_session_id(self) -> str:
        return self.selected_entry.session_id


def build_worker_resume_prompt(
    *,
    repo_dir: str | Path,
    catalog: WorkerSessionCatalog,
    selected_index: int,
    selected_entry: WorkerSessionEntry,
) -> str:
    payload = {
        "schema_version": 1,
        "repository": str(repo_dir),
        "recipient_role": "worker",
        "target_session_id": selected_entry.session_id,
        "selected_worker_index": selected_index,
        "router_session_id": catalog.router_session_id,
        "worker_count": len(catalog.entries),
        "worker_session_ids": list(catalog.worker_session_ids),
        "selected_worker": {
            "session_id": selected_entry.session_id,
            "source_kinds": list(selected_entry.source_kinds),
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
                for source in selected_entry.sources
            ],
        },
        "resume_contract": {
            "current_session_must_match_target_session_id": True,
            "continue_existing_session_only": True,
            "do_not_start_new_session": True,
        },
    }
    return (
        "ArtifactForge Worker Resume Prompt v1\n\n"
        "You are being resumed from the managed worker list.\n"
        "Expected recipient:\n"
        f"- recipient_role: worker\n"
        f"- target_session_id: {selected_entry.session_id}\n"
        f"- selected_worker_index: {selected_index}\n\n"
        "If your current session ID is not target_session_id, do not perform the work.\n"
        "Resume the existing worker session and continue the current thread context only.\n"
        "Do not switch to another worker session or start a new worker session.\n"
        "The selected index and catalog below are advisory context for resumption.\n\n"
        "WORKER_RESUME_V1_INPUT\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def plan_worker_resume_by_index(
    *,
    index: int,
    repo_dir: str | Path = REPO_ROOT,
    assignment_state_path: str | Path | None = None,
    pending_dir: str | Path | None = None,
    request_for_human_dir: str | Path | None = None,
    human_waiting_dir: str | Path | None = None,
    pending_state_path: str | Path | None = None,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    catalog: WorkerSessionCatalog | None = None,
) -> WorkerResumePlan:
    repo_root = Path(repo_dir)
    if catalog is None:
        catalog = collect_worker_session_catalog(
            repo_dir=repo_root,
            assignment_state_path=assignment_state_path,
            pending_dir=pending_dir,
            request_for_human_dir=request_for_human_dir,
            human_waiting_dir=human_waiting_dir,
            pending_state_path=pending_state_path,
        )
    selected_entry = worker_session_entry_at_index(catalog, index)
    if selected_entry is None:
        raise IndexError(
            f"worker index {index} is out of range for {len(catalog.entries)} workers"
        )

    prompt = build_worker_resume_prompt(
        repo_dir=repo_root,
        catalog=catalog,
        selected_index=index,
        selected_entry=selected_entry,
    )
    session_plan = SessionResumePlan(
        session_id=selected_entry.session_id,
        recipient_role="worker",
        session_visibility="non_visible",
        prompt=prompt,
        command=None,
        source_kind="worker_list",
        reason="selected_worker_session_by_index",
        router_session_id=catalog.router_session_id,
        request_for_human_memos=(),
        human_waiting_records=(),
        pending_records=(),
        worker_session_ids=catalog.worker_session_ids,
    )
    command = (
        str(codex_bin),
        "resume",
        "--cd",
        str(repo_root),
        "--include-non-interactive",
        selected_entry.session_id,
        prompt,
    )
    return WorkerResumePlan(
        catalog=catalog,
        selected_index=index,
        selected_entry=selected_entry,
        session_plan=session_plan,
        command=command,
    )


def resume_worker_session(
    plan: WorkerResumePlan,
    *,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    runner: Any = _default_runner,
) -> Any:
    return resume_session(
        plan.session_plan,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
        runner=runner,
    )


def worker_resume_plan_to_dict(plan: WorkerResumePlan) -> dict[str, object]:
    catalog_summary = worker_session_catalog_to_dict(plan.catalog)
    summary = {
        "schema_version": 1,
        "source_kind": plan.session_plan.source_kind,
        "reason": plan.session_plan.reason,
        "recipient_role": plan.session_plan.recipient_role,
        "selected_index": plan.selected_index,
        "selected_session_id": plan.selected_session_id,
        "session_visibility": plan.session_plan.session_visibility,
        "router_session_id": plan.session_plan.router_session_id,
        "worker_count": catalog_summary["worker_count"],
        "worker_session_ids": catalog_summary["worker_session_ids"],
        "selected_worker": {
            "index": plan.selected_index,
            "session_id": plan.selected_session_id,
            "source_kinds": list(plan.selected_entry.source_kinds),
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
                for source in plan.selected_entry.sources
            ],
        },
        "command": list(plan.command[:-1]) + ["<prompt>"] if plan.command else None,
        "prompt_preview": _prompt_preview(plan.session_plan.prompt),
    }
    return summary


def human_summary(plan: WorkerResumePlan) -> str:
    summary = worker_resume_plan_to_dict(plan)
    lines = [
        "ArtifactForge worker resume",
        f"selected_index: {summary['selected_index']}",
        f"selected_session_id: {summary['selected_session_id']}",
        f"worker_count: {summary['worker_count']}",
        f"router_session_id: {summary['router_session_id'] or '(none)'}",
        f"source_kind: {summary['source_kind']}",
        f"reason: {summary['reason']}",
    ]
    if summary.get("worker_session_ids"):
        lines.append(
            "worker_session_ids: " + ", ".join(summary["worker_session_ids"])
        )
    if summary.get("command"):
        lines.append("command: " + " ".join(summary["command"]))
    if summary.get("prompt_preview"):
        lines.append("")
        lines.append("prompt_preview:")
        lines.append(str(summary["prompt_preview"]))
    return "\n".join(lines)


def _prompt_preview(prompt: str | None, *, limit: int = 800) -> str | None:
    if prompt is None:
        return None
    if len(prompt) <= limit:
        return prompt
    return prompt[: limit - 1] + "…"
