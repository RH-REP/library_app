"""Codex dispatch helpers for ArtifactForge issue queues."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple, Union

from .models import QueueRecord
from .queueing import build_queue_markdown, safe_filename_part


CORE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CORE_DIR.parent
DEFAULT_QUEUE_DIR = CORE_DIR / "queue"
DEFAULT_PENDING_DIR = CORE_DIR / "pending"
DEFAULT_ASSIGNMENT_STATE_PATH = CORE_DIR / "assignment_state.json"
DEFAULT_SESSION_ROUTER_PROMPT = CORE_DIR / "prompts" / "session_router_v1.md"
DEFAULT_WORKER_PROMPT = CORE_DIR / "prompts" / "worker_v1.md"
DEFAULT_CODEX_BIN = "codex"

SESSION_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
FIELD_RE = re.compile(r"^\s*-\s*([A-Za-z_][A-Za-z0-9_ -]*)\s*:\s*(.*?)\s*$")
FINGERPRINT_START_RE = re.compile(r"_(?=issue-\d+-(?:body|comment)-)")
SUB_ARTIFACT_NUMBER_RE = re.compile(r"(?:^|/)sub_artifact/(\d{3})_[^/]+")


Runner = Callable[[Sequence[str], Any], Any]


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    args: Tuple[str, ...]
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


@dataclass(frozen=True)
class RouterOutputValidation:
    valid: bool
    session_id: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class DispatchPlan:
    queue_path: Path
    record: QueueRecord
    prompt: str
    command: Tuple[str, ...]
    pending_path: Path


@dataclass(frozen=True)
class DispatchResult:
    plan: DispatchPlan
    sent: bool
    moved_to_pending: bool
    session_id: str
    router_session_id: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and (self.sent or self.dry_run)

    @property
    def worker_session_id(self) -> str:
        return self.session_id

    @property
    def queue_moved(self) -> bool:
        return self.moved_to_pending

    @property
    def status(self) -> str:
        if self.error:
            return "failed"
        if self.dry_run:
            return "planned"
        return "sent" if self.sent else "not_sent"


class DispatchError(RuntimeError):
    pass


def _default_runner(
    args: Sequence[str],
    input_text: Optional[str],
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )


def _read_prompt(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def parse_session_router_output(output: str) -> str:
    validation = validate_session_router_output(output)
    if not validation.valid or validation.session_id is None:
        raise DispatchError(validation.error or "invalid Session_router output")
    return validation.session_id


def validate_session_router_output(output: str) -> RouterOutputValidation:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        return RouterOutputValidation(valid=False, error="output must be one line")
    if not SESSION_ID_RE.fullmatch(lines[0]):
        return RouterOutputValidation(valid=False, error="output must be a session ID")
    return RouterOutputValidation(valid=True, session_id=lines[0])


def parse_queue_file(path: str | Path) -> QueueRecord:
    queue_path = Path(path)
    text = queue_path.read_text(encoding="utf-8")
    fields = _metadata_fields(text)
    if not fields:
        return _record_from_filename(queue_path, text)

    body = _body_from_queue_text(text)
    return QueueRecord(
        issue_number=int(fields.get("issue_number", "0")),
        issue_url=fields.get("issue_url", ""),
        issue_title=fields.get("issue_title", ""),
        event_type=fields.get("event_type", ""),
        trigger_fingerprint=fields["trigger_fingerprint"],
        target_session_id=fields["target_session_id"],
        prompt_kind=fields.get("prompt_kind", "worker"),
        body=body,
        source_id=fields.get("source_id") or None,
        sub_artifact_path=fields.get("sub_artifact_path") or None,
        previous_thread_id=fields.get("previous_thread_id") or None,
        reassign_required=fields.get("reassign_required", "").lower() == "true",
    )


def read_queue_record(path: str | Path) -> QueueRecord:
    return parse_queue_file(path)


def write_queue_record(path: str | Path, record: QueueRecord) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_queue_markdown(record), encoding="utf-8")
    return target


def iter_queue_paths(queue_dir: str | Path = DEFAULT_QUEUE_DIR) -> Tuple[Path, ...]:
    target = Path(queue_dir)
    if not target.exists():
        return ()
    return tuple(path for path in sorted(target.glob("*.md")) if not path.name.startswith("."))


def build_session_router_prompt(
    record: QueueRecord,
    *,
    repo_dir: str | Path = REPO_ROOT,
    template_path: str | Path = DEFAULT_SESSION_ROUTER_PROMPT,
) -> str:
    payload = {
        "schema_version": 1,
        "repository": str(repo_dir),
        "issue_number": record.issue_number,
        "issue_url": record.issue_url,
        "target_events": [asdict(record)],
        "reassign_required": record.reassign_required,
        "previous_thread_id": record.previous_thread_id,
        "constraints": {
            "session_router_must_not_do_worker_work": True,
            "session_router_output": "one session id line only",
        },
    }
    return (
        f"{_read_prompt(template_path)}\n\n"
        "SESSION_ROUTER_V1_INPUT\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def build_worker_prompt(
    record: QueueRecord,
    *,
    session_id: Optional[str] = None,
    repo_dir: str | Path = REPO_ROOT,
    template_path: str | Path = DEFAULT_WORKER_PROMPT,
) -> str:
    payload = {
        "schema_version": 1,
        "repository": str(repo_dir),
        "assigned_session_id": session_id or record.target_session_id,
        "issue_number": record.issue_number,
        "issue_url": record.issue_url,
        "target_events": [asdict(record)],
        "github_comment_contract": {
            "visible_comment_required": True,
            "marker_required": True,
            "marker_statuses": [
                "done",
                "reassign_required",
                "authentication_blocked",
            ],
        },
    }
    return (
        f"{_read_prompt(template_path)}\n\n"
        "WORKER_V1_INPUT\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def pending_destination(path: str | Path, pending_dir: str | Path, session_id: str) -> Path:
    source = Path(path)
    target_dir = Path(pending_dir)
    candidate = target_dir / source.name
    if not candidate.exists():
        return candidate
    for index in range(2, 10_000):
        candidate = target_dir / f"{candidate.stem}.{index}{candidate.suffix}"
        if not candidate.exists():
            return candidate
    raise DispatchError(f"could not allocate pending path for {source.name}")


def plan_dispatch(
    queue_path: str | Path,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
) -> DispatchPlan:
    path = Path(queue_path)
    record = parse_queue_file(path)
    if record.prompt_kind == "session_router":
        prompt = build_session_router_prompt(record, repo_dir=repo_dir)
        command = (
            str(codex_bin),
            "resume",
            "--include-non-interactive",
            record.target_session_id,
            prompt,
        )
    else:
        prompt = build_worker_prompt(record, repo_dir=repo_dir)
        command = (
            str(codex_bin),
            "resume",
            "--include-non-interactive",
            record.target_session_id,
            prompt,
        )
    pending_path = pending_destination(path, pending_dir, record.target_session_id)
    return DispatchPlan(
        queue_path=path,
        record=record,
        prompt=prompt,
        command=command,
        pending_path=pending_path,
    )


def dispatch_queue_file(
    queue_path: str | Path,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    dry_run: bool = False,
    move_to_pending: bool = True,
    runner: Runner = _default_runner,
    assignment_state_path: Optional[Union[str, Path]] = None,
) -> DispatchResult:
    plan = plan_dispatch(
        queue_path,
        pending_dir=pending_dir,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
    )
    if dry_run:
        return DispatchResult(
            plan=plan,
            sent=False,
            moved_to_pending=False,
            session_id=plan.record.target_session_id,
            dry_run=True,
        )

    try:
        if plan.record.prompt_kind == "session_router":
            result = _run_session_router(
                runner,
                plan.prompt,
                router_session_id=plan.record.target_session_id,
                codex_bin=codex_bin,
            )
            if not result.ok:
                raise DispatchError(result.stderr.strip() or result.stdout.strip())
            session_id = parse_session_router_output(result.stdout)
            worker_prompt = build_worker_prompt(
                plan.record,
                session_id=session_id,
                repo_dir=repo_dir,
            )
            worker_result = _run_resume_session(
                runner,
                session_id,
                worker_prompt,
                codex_bin=codex_bin,
            )
            if not worker_result.ok:
                raise DispatchError(worker_result.stderr.strip() or worker_result.stdout.strip())
            if assignment_state_path is not None:
                update_assignment_state(
                    assignment_state_path,
                    plan.record,
                    session_id=session_id,
                )
        else:
            result = _run_resume_session(
                runner,
                plan.record.target_session_id,
                plan.prompt,
                codex_bin=codex_bin,
            )
            if not result.ok:
                raise DispatchError(result.stderr.strip() or result.stdout.strip())
            session_id = plan.record.target_session_id
    except Exception as exc:
        return DispatchResult(
            plan=plan,
            sent=False,
            moved_to_pending=False,
            session_id=plan.record.target_session_id,
            error=str(exc),
        )

    moved = False
    pending_path = pending_destination(queue_path, pending_dir, session_id)
    final_plan = DispatchPlan(
        queue_path=plan.queue_path,
        record=plan.record,
        prompt=plan.prompt,
        command=plan.command,
        pending_path=pending_path,
    )
    if move_to_pending:
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        Path(queue_path).rename(pending_path)
        moved = True
    return DispatchResult(
        plan=final_plan,
        sent=True,
        moved_to_pending=moved,
        session_id=session_id,
        router_session_id=(
            plan.record.target_session_id if plan.record.prompt_kind == "session_router" else None
        ),
    )


def dispatch_queue(
    queue_dir: str | Path = DEFAULT_QUEUE_DIR,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    dry_run: bool = False,
    move_to_pending: bool = True,
    runner: Runner = _default_runner,
    assignment_state_path: Optional[Union[str, Path]] = None,
) -> Tuple[DispatchResult, ...]:
    return tuple(
        dispatch_queue_file(
            path,
            pending_dir=pending_dir,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
            dry_run=dry_run,
            move_to_pending=move_to_pending,
            runner=runner,
            assignment_state_path=assignment_state_path,
        )
        for path in iter_queue_paths(queue_dir)
    )


def dispatch_queue_dir(
    queue_dir: str | Path = DEFAULT_QUEUE_DIR,
    **kwargs: Any,
) -> Tuple[DispatchResult, ...]:
    return dispatch_queue(queue_dir, **kwargs)


def dispatch_results_to_dict(results: Iterable[DispatchResult]) -> Dict[str, object]:
    result_tuple = tuple(results)
    return {
        "schema_version": 1,
        "entry_count": len(result_tuple),
        "sent_count": sum(1 for result in result_tuple if result.sent),
        "moved_to_pending_count": sum(
            1 for result in result_tuple if result.moved_to_pending
        ),
        "dry_run_count": sum(1 for result in result_tuple if result.dry_run),
        "failed_count": sum(1 for result in result_tuple if result.error),
        "items": [
            {
                "queue_path": str(result.plan.queue_path),
                "pending_path": str(result.plan.pending_path),
                "issue_number": result.plan.record.issue_number,
                "prompt_kind": result.plan.record.prompt_kind,
                "target_session_id": result.plan.record.target_session_id,
                "session_id": result.session_id,
                "command": list(result.plan.command[:-1]) + ["<prompt>"],
                "sent": result.sent,
                "moved_to_pending": result.moved_to_pending,
                "dry_run": result.dry_run,
                "error": result.error,
            }
            for result in result_tuple
        ],
    }


def _metadata_fields(text: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for line in text.splitlines():
        match = FIELD_RE.match(line)
        if match is None:
            continue
        key = match.group(1).strip().lower().replace("-", "_").replace(" ", "_")
        fields[key] = match.group(2).strip().strip("\"'`")
    return fields


def _completed_to_command_result(
    result: subprocess.CompletedProcess,
) -> CommandResult:
    return CommandResult(
        ok=result.returncode == 0,
        args=tuple(str(arg) for arg in result.args),
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        returncode=result.returncode,
    )


def _call_runner(
    runner: Any,
    args: Sequence[str],
    input_text: Optional[str] = None,
) -> CommandResult:
    result = runner(args, input_text)
    if isinstance(result, CommandResult):
        return result
    return _completed_to_command_result(result)


def _run_resume_session(
    runner: Any,
    session_id: str,
    prompt: str,
    *,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
) -> CommandResult:
    if hasattr(runner, "resume_session"):
        return runner.resume_session(session_id, prompt)
    args = (
        str(codex_bin),
        "resume",
        "--include-non-interactive",
        session_id,
        prompt,
    )
    return _call_runner(runner, args, None)


def _run_session_router(
    runner: Any,
    prompt: str,
    *,
    router_session_id: Optional[str],
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
) -> CommandResult:
    if hasattr(runner, "run_session_router"):
        return runner.run_session_router(prompt, router_session_id=router_session_id)
    if router_session_id:
        return _run_resume_session(
            runner,
            router_session_id,
            prompt,
            codex_bin=codex_bin,
        )
    if hasattr(runner, "start_session"):
        return runner.start_session(prompt)
    return _call_runner(runner, (str(codex_bin), prompt), None)


def update_assignment_state(
    path: str | Path,
    record: QueueRecord,
    *,
    session_id: str,
) -> Path:
    target = Path(path)
    if target.exists():
        payload = json.loads(target.read_text(encoding="utf-8"))
    else:
        payload = {
            "schema_version": 1,
            "router_session_id": None,
            "next_sub_artifact_number": 1,
            "assignments": [],
        }
    assignments = payload.setdefault("assignments", [])
    for assignment in assignments:
        if int(assignment.get("issue_number", -1)) != record.issue_number:
            continue
        assignment["session_id"] = session_id
        assignment["status"] = "active"
        if record.sub_artifact_path:
            assignment["sub_artifact_path"] = record.sub_artifact_path
        break
    else:
        assignments.append(
            {
                "issue_number": record.issue_number,
                "session_id": session_id,
                "sub_artifact_path": record.sub_artifact_path,
                "status": "active",
                "summary": record.issue_title,
            }
        )
    number_match = (
        SUB_ARTIFACT_NUMBER_RE.search(record.sub_artifact_path)
        if record.sub_artifact_path
        else None
    )
    if number_match is not None:
        payload["next_sub_artifact_number"] = max(
            int(payload.get("next_sub_artifact_number", 1) or 1),
            int(number_match.group(1)) + 1,
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _body_from_queue_text(text: str) -> str:
    marker = "## Body"
    if marker not in text:
        return text.rstrip()
    return text.split(marker, 1)[1].strip()


def _record_from_filename(path: Path, text: str) -> QueueRecord:
    match = FINGERPRINT_START_RE.search(path.stem)
    if match is None:
        raise DispatchError(
            "queue filename must be <session_id>_<issue-fingerprint>.md"
        )
    return QueueRecord(
        issue_number=0,
        issue_url="",
        issue_title="",
        event_type="unknown",
        trigger_fingerprint=path.stem[match.start() + 1 :],
        target_session_id=path.stem[: match.start()],
        prompt_kind="worker",
        body=text.rstrip(),
        source_id=None,
    )
