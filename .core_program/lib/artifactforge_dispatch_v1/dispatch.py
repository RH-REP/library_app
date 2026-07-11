"""Codex dispatch helpers for ArtifactForge issue queues."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple, Union

from .lifecycle import iter_pending_records
from .models import QueueRecord
from .queueing import (
    build_queue_markdown,
    collect_existing_fingerprints,
    safe_filename_part,
)


CORE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CORE_DIR.parent
DEFAULT_QUEUE_DIR = CORE_DIR / "queue"
DEFAULT_INFLIGHT_DIR = CORE_DIR / "inflight"
DEFAULT_PENDING_DIR = CORE_DIR / "pending"
DEFAULT_ARCHIVE_DIR = CORE_DIR / "archive"
DEFAULT_LOCKS_DIR = CORE_DIR / "locks"
DEFAULT_ASSIGNMENT_STATE_PATH = CORE_DIR / "assignment_state.json"
DEFAULT_SESSION_ROUTER_PROMPT = CORE_DIR / "prompts" / "session_router_v1.md"
DEFAULT_SESSION_ROUTER_BOOTSTRAP_PROMPT = (
    CORE_DIR / "prompts" / "session_router_bootstrap_v1.md"
)
DEFAULT_WORKER_PROMPT = CORE_DIR / "prompts" / "worker_v1.md"
DEFAULT_DISPATCH_PROMPT = CORE_DIR / "prompts" / "dispatch_v1.md"
DEFAULT_CODEX_BIN = "codex"
DEFAULT_VISIBLE_SESSION_RUN_DIR = (
    CORE_DIR / "app" / "02_dispatch_queue" / "data" / "visible_sessions"
)
DEFAULT_TERMINAL_APP = "Terminal"
DEFAULT_VISIBLE_SESSION_WAIT_SECONDS = 60
DEFAULT_ROUTER_ASSIGNMENT_WAIT_SECONDS = 300
SESSION_DEFER_REASONS = frozenset(
    {
        "session_has_unresolved_pending",
        "target_session_already_dispatched_this_run",
    }
)

SESSION_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
SESSION_ID_SEARCH_RE = re.compile(
    r"(?<![0-9a-fA-F])"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"(?![0-9a-fA-F])"
)
FIELD_RE = re.compile(r"^\s*-\s*([A-Za-z_][A-Za-z0-9_ -]*)\s*:\s*(.*?)\s*$")
FINGERPRINT_START_RE = re.compile(r"_(?=issue-\d+-(?:body|comment|thread)-)")
SUB_ARTIFACT_NUMBER_RE = re.compile(r"(?:^|/)sub_artifact/(\d{3})_[^/]+")
BOOTSTRAP_SESSION_ID_FIELDS = ("session_id", "router_session_id")
_MISSING = object()


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
    session_visibility: str = "visible"
    router_session_id: Optional[str] = None


@dataclass(frozen=True)
class QueueClaim:
    original_path: Path
    claimed_path: Path


@dataclass(frozen=True)
class DispatchResult:
    plan: DispatchPlan
    sent: bool
    moved_to_pending: bool
    session_id: str
    router_session_id: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = False
    skipped: bool = False
    skip_reason: Optional[str] = None
    move_to_pending: bool = True

    @property
    def ok(self) -> bool:
        return self.error is None and (self.sent or self.dry_run or self.skipped)

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
        if self.skipped:
            return "skipped"
        if self.dry_run:
            return "planned"
        return "sent" if self.sent else "not_sent"

    @property
    def pending_movement(self) -> str:
        if self.skipped:
            return "not_moved_skipped"
        if self.dry_run:
            if self.move_to_pending:
                return "would_move_to_pending_before_router_send"
            return "would_keep_queue"
        if self.moved_to_pending:
            return "moved_to_pending_before_router_send"
        if self.sent and not self.move_to_pending:
            return "not_moved_keep_queue"
        if self.error:
            return "not_moved_or_restored"
        return "not_moved"


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


def parse_bootstrap_session_id(result: Any) -> str:
    for field_name in BOOTSTRAP_SESSION_ID_FIELDS:
        has_value, value = _result_attr(result, field_name)
        if has_value and _has_bootstrap_session_id_value(value):
            return _validate_bootstrap_session_id(value, f"result.{field_name}")

    for field_name in BOOTSTRAP_SESSION_ID_FIELDS:
        has_value, value = _result_mapping_value(result, field_name)
        if has_value and _has_bootstrap_session_id_value(value):
            return _validate_bootstrap_session_id(value, f"result[{field_name!r}]")

    stdout = _result_text(result, "stdout")
    stderr = _result_text(result, "stderr")
    return extract_bootstrap_session_id(stdout, stderr)


def extract_bootstrap_session_id(stdout: str = "", stderr: str = "") -> str:
    candidates = []
    seen = set()
    for stream in (stdout or "", stderr or ""):
        for match in SESSION_ID_SEARCH_RE.finditer(stream):
            session_id = match.group(0)
            if session_id not in seen:
                seen.add(session_id)
                candidates.append(session_id)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise DispatchError("bootstrap output did not include a session ID")
    raise DispatchError(
        "bootstrap output included multiple session ID candidates: "
        + ", ".join(candidates)
    )


def _validate_bootstrap_session_id(value: Any, source: str) -> str:
    session_id = str(value).strip() if value is not None else ""
    if not session_id:
        raise DispatchError(f"{source} is empty")
    if not SESSION_ID_RE.fullmatch(session_id):
        raise DispatchError(f"{source} is not a valid session ID")
    return session_id


def _has_bootstrap_session_id_value(value: Any) -> bool:
    return bool(str(value).strip()) if value is not None else False


def _result_attr(result: Any, field_name: str) -> Tuple[bool, Any]:
    if not hasattr(result, field_name):
        return False, None
    return True, getattr(result, field_name)


def _result_mapping_value(result: Any, field_name: str) -> Tuple[bool, Any]:
    if isinstance(result, Mapping):
        return field_name in result, result.get(field_name)
    getter = getattr(result, "get", None)
    if callable(getter):
        try:
            value = getter(field_name, _MISSING)
        except TypeError:
            try:
                value = getter(field_name)
            except Exception:
                return False, None
            if value is None:
                return False, None
        except Exception:
            return False, None
        if value is _MISSING:
            return False, None
        return True, value
    return False, None


def _result_text(result: Any, field_name: str) -> str:
    has_value, value = _result_attr(result, field_name)
    if not has_value:
        has_value, value = _result_mapping_value(result, field_name)
    if value is None:
        return ""
    return str(value)


def _result_ok(result: Any) -> bool:
    has_value, value = _result_attr(result, "ok")
    if not has_value:
        has_value, value = _result_mapping_value(result, "ok")
    if has_value:
        return bool(value)

    has_value, value = _result_attr(result, "returncode")
    if not has_value:
        has_value, value = _result_mapping_value(result, "returncode")
    if has_value and value is not None:
        return int(value) == 0

    return True


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _codex_home(codex_home: Optional[Union[str, Path]] = None) -> Path:
    if codex_home is not None:
        return Path(codex_home).expanduser()
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()


def _session_id_from_jsonl_line(line: str) -> Optional[str]:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None
    if event.get("type") != "session_meta":
        return None
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    value = payload.get("session_id") or payload.get("id")
    if value is None:
        return None
    session_id = str(value).strip()
    return session_id if SESSION_ID_RE.fullmatch(session_id) else None


def _session_id_from_path(path: Path) -> Optional[str]:
    match = SESSION_ID_SEARCH_RE.search(str(path))
    return match.group(0) if match else None


def _scan_recent_codex_sessions(
    *,
    marker: str,
    cutoff_time: float,
    codex_home: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    sessions_dir = _codex_home(codex_home) / "sessions"
    if not sessions_dir.exists():
        return None
    candidates = []
    for path in sessions_dir.glob("**/*.jsonl"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime < cutoff_time:
            continue
        candidates.append((stat.st_mtime, path))
    candidates.sort(reverse=True)

    for _, path in candidates:
        found_marker = False
        session_id = None
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if session_id is None:
                        session_id = _session_id_from_jsonl_line(line)
                    if marker and marker in line:
                        found_marker = True
                    if session_id and found_marker:
                        return session_id
        except OSError:
            continue
        if found_marker:
            return session_id or _session_id_from_path(path)
    return None


def discover_recent_codex_session_id(
    *,
    marker: str,
    cutoff_time: float,
    timeout_seconds: Optional[int] = None,
    poll_seconds: float = 0.5,
    codex_home: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    timeout = (
        DEFAULT_VISIBLE_SESSION_WAIT_SECONDS
        if timeout_seconds is None
        else max(0, timeout_seconds)
    )
    deadline = time.time() + timeout
    while True:
        session_id = _scan_recent_codex_sessions(
            marker=marker,
            cutoff_time=cutoff_time,
            codex_home=codex_home,
        )
        if session_id:
            return session_id
        if time.time() >= deadline:
            return None
        time.sleep(poll_seconds)


def _default_terminal_launcher(script_path: Path, terminal_app: str) -> Any:
    return subprocess.run(
        ["open", "-a", terminal_app, str(script_path)],
        text=True,
        capture_output=True,
        check=False,
    )


def _visible_session_command(
    *,
    codex_bin: str | Path,
    repo_dir: str | Path,
    prompt_path: Path,
    session_id: Optional[str],
) -> str:
    repo = shlex.quote(str(repo_dir))
    codex = shlex.quote(_resolve_executable(codex_bin))
    prompt = shlex.quote(str(prompt_path))
    if session_id:
        return (
            f"prompt_text=\"$(cat {prompt})\"\n"
            f"exec {codex} resume --cd {repo} --no-alt-screen "
            f"--include-non-interactive {shlex.quote(session_id)} \"$prompt_text\"\n"
        )
    return (
        f"prompt_text=\"$(cat {prompt})\"\n"
        f"exec {codex} --cd {repo} --no-alt-screen \"$prompt_text\"\n"
    )


def _resolve_executable(executable: str | Path) -> str:
    value = str(executable)
    if "/" in value:
        return value
    return shutil.which(value) or value


def _write_visible_launch_files(
    *,
    prompt: str,
    repo_dir: str | Path,
    codex_bin: str | Path,
    role: str,
    session_id: Optional[str],
    run_dir_base: str | Path = DEFAULT_VISIBLE_SESSION_RUN_DIR,
) -> Tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
    safe_role = safe_filename_part(role)
    run_dir = Path(run_dir_base) / f"{timestamp}_{os.getpid()}_{safe_role}"
    run_dir.mkdir(parents=True, exist_ok=False)
    prompt_path = run_dir / "prompt.md"
    script_path = run_dir / "launch.command"
    prompt_path.write_text(prompt, encoding="utf-8")
    script_text = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"cd {shlex.quote(str(repo_dir))}\n"
        "printf 'ArtifactForge visible Codex session\\n'\n"
        f"printf 'Prompt file: %s\\n' {shlex.quote(str(prompt_path))}\n"
        + _visible_session_command(
            codex_bin=codex_bin,
            repo_dir=repo_dir,
            prompt_path=prompt_path,
            session_id=session_id,
        )
    )
    script_path.write_text(script_text, encoding="utf-8")
    script_path.chmod(0o755)
    return prompt_path, script_path


def launch_visible_codex_session(
    prompt: str,
    *,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    role: str,
    session_id: Optional[str] = None,
    marker: str = "",
    terminal_app: Optional[str] = None,
    run_dir_base: str | Path = DEFAULT_VISIBLE_SESSION_RUN_DIR,
    launcher: Callable[[Path, str], Any] = _default_terminal_launcher,
    wait_seconds: Optional[int] = None,
    codex_home: Optional[Union[str, Path]] = None,
) -> CommandResult:
    app_name = terminal_app or os.environ.get("ARTIFACTFORGE_TERMINAL_APP") or DEFAULT_TERMINAL_APP
    cutoff_time = time.time() - 1.0
    _, script_path = _write_visible_launch_files(
        prompt=prompt,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
        role=role,
        session_id=session_id,
        run_dir_base=run_dir_base,
    )
    open_result = launcher(script_path, app_name)
    args = ("open", "-a", app_name, str(script_path))
    if not _result_ok(open_result):
        return CommandResult(
            ok=False,
            args=args,
            stdout=_result_text(open_result, "stdout"),
            stderr=_result_text(open_result, "stderr"),
            returncode=int(_result_text(open_result, "returncode") or 1),
        )
    if session_id:
        return CommandResult(ok=True, args=args, stdout="", stderr="", returncode=0)

    discovered_session_id = discover_recent_codex_session_id(
        marker=marker,
        cutoff_time=cutoff_time,
        timeout_seconds=(
            _env_int(
                "ARTIFACTFORGE_VISIBLE_SESSION_WAIT_SECONDS",
                DEFAULT_VISIBLE_SESSION_WAIT_SECONDS,
            )
            if wait_seconds is None
            else wait_seconds
        ),
        codex_home=codex_home,
    )
    if not discovered_session_id:
        return CommandResult(
            ok=False,
            args=args,
            stdout="",
            stderr=(
                "visible Codex session was launched, but its session ID could "
                f"not be discovered from {_codex_home(codex_home) / 'sessions'}"
            ),
            returncode=75,
        )
    return CommandResult(
        ok=True,
        args=args,
        stdout=f"{discovered_session_id}\n",
        stderr="",
        returncode=0,
    )


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
        prompt_kind=_prompt_kind_from_fields(fields),
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


def _router_orchestration_instructions(
    *,
    pending_dir: str | Path,
    pending_path: Optional[Union[str, Path]],
) -> str:
    pending_path_line = (
        f"- The dispatcher just moved this queue file to pending: `{pending_path}`."
        if pending_path is not None
        else "- The dispatcher is planning a pending move; verify pending files before acting."
    )
    return "\n".join(
        [
            "# Session_router orchestration contract",
            "",
            "You are the single visible ArtifactForge Session_router orchestrator.",
            "",
            "Task:",
            "- Before processing pending work, check `.core_program/request_for_human/`.",
            "- If unresolved request memo files exist there, handle or summarize those human requests first instead of starting new pending work.",
            "- Read `.core_program/pending` as the dispatch worklist before acting.",
            pending_path_line,
            f"- Treat `{pending_dir}` as the pending directory even if this prompt also includes a single source record.",
            "- Dispatch or delegate pending work to worker and subagent sessions yourself.",
            "- Do not ask the dispatcher to resume worker sessions.",
            "- Do not do the worker implementation work in the router session.",
            "- Keep the router as the only human-facing permission gateway.",
            "- Route login, approval, permission, TTY, and other interactive needs through this visible router session.",
            "- You may grant or broker permissions/capabilities this Session_router already has to subagents when the pending task needs them and the action stays within this repository/project scope.",
            "- Ask the user through this Session_router before obtaining any new permission or broader capability.",
            "- Worker and subagent sessions may be non-visible.",
            "- Preserve `.core_program/assignment_state.json` as the issue/session/sub-artifact routing state.",
            "- If `reassign_required` is true, avoid `previous_thread_id` when choosing a worker.",
            "- If you discover an ArtifactForge contract violation, post a concise bug report yourself as a GitHub issue comment on the relevant issue.",
            "- End a contract-violation bug report with a `codex-agent-v1` marker; prefer `authentication_blocked` unless the violation is specifically wrong-session assignment.",
            "- Do not archive pending work merely because a bug report was posted.",
            "- Before asking the user a question, write a resumption memo under `.core_program/request_for_human/` so the work can resume smoothly if the human is unavailable.",
            "- Request memo template: 日時: / Pending fingerprints: / Worker session ID: / 問い合わせ内容:",
            "- After a pending record is resolved and the final GitHub issue comment with the required marker is posted, move it from `.core_program/pending/` to `.core_program/archive/` with the same filename.",
            "- Example: `mv .core_program/pending/xxx.md .core_program/archive/xxx.md`.",
            "- Do not archive blocked, deferred, human-waiting, or in-progress pending records.",
            "",
            "Output:",
            "- Report concise routing progress in this visible router session.",
            "- Do not output a one-line worker session ID for the dispatcher; dispatcher worker delivery is disabled.",
        ]
    )


def build_dispatch_prompt(
    record: QueueRecord,
    *,
    repo_dir: str | Path = REPO_ROOT,
    template_path: str | Path = DEFAULT_DISPATCH_PROMPT,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    pending_path: Optional[Union[str, Path]] = None,
    router_session_id: Optional[str] = None,
    source_record: Optional[QueueRecord] = None,
) -> str:
    source = source_record or record
    target_thread_updates = [_record_payload(source)]
    session_visibility = dispatch_session_visibility(record)
    local_demo = is_local_demo_record(source)
    payload: Dict[str, object] = {
        "schema_version": 1,
        "repository": str(repo_dir),
        "recipient_role": record.recipient_role,
        "target_session_id": record.target_session_id,
        "target_session_visibility": session_visibility,
        "issue_number": source.issue_number,
        "issue_url": source.issue_url,
        "trigger_fingerprint": source.trigger_fingerprint,
        "target_thread_updates": target_thread_updates,
        "target_events": target_thread_updates,
        "sub_artifact_path": source.sub_artifact_path,
        "reassign_required": source.reassign_required,
        "previous_thread_id": source.previous_thread_id,
        "safety_contract": {
            "current_session_must_match_target_session_id": True,
            "wrong_session_must_not_perform_work": True,
        },
        "human_gateway_contract": {
            "user_interface_role": "router",
            "router_is_only_human_permission_surface": True,
            "subagents_may_be_non_visible": True,
            "permission_requests_must_go_through_router": True,
            "router_existing_capabilities_may_be_granted_to_subagents": True,
            "new_or_broader_capabilities_require_user_approval": True,
            "do_not_ask_user_to_open_child_worker_directly": True,
        },
    }
    if local_demo:
        payload["local_demo_contract"] = {
            "external_side_effects_forbidden": True,
            "github_api_must_not_be_called": True,
            "github_comments_must_not_be_posted": True,
            "git_commit_must_not_be_created": True,
            "git_push_must_not_run": True,
            "allowed_write_root": ".core_program/dry_run_output/",
            "report_planned_comment_in_session_only": True,
        }
    if record.recipient_role == "router":
        pending_path_text = str(pending_path) if pending_path is not None else None
        payload["routing_contract"] = {
            "prefer_existing_worker_check": True,
            "avoid_previous_thread_id": bool(source.previous_thread_id),
            "start_new_worker_only_if_no_existing_worker_accepts": True,
            "handoff_worker_prompt_once": True,
            "enqueue_worker_dispatch_task_once": False,
            "worker_task_queue_dir": None,
            "worker_prompt_sent_by_dispatcher": False,
            "dispatcher_will_not_resume_worker_sessions": True,
            "router_dispatches_or_delegates_workers_itself": True,
            "router_must_read_pending_dir": True,
            "request_for_human_dir": ".core_program/request_for_human",
            "check_request_for_human_empty_before_pending": True,
            "write_request_for_human_memo_before_user_question": True,
            "request_for_human_template": {
                "日時": "",
                "Pending fingerprints": "",
                "Worker session ID": "",
                "問い合わせ内容": "",
            },
            "pending_queue_dir": ".core_program/pending",
            "pending_path": pending_path_text,
            "output_worker_session_id_one_line": False,
            "router_may_request_human_permission": True,
            "router_may_grant_existing_capabilities_to_subagents": True,
            "new_or_broader_capabilities_require_user_approval": True,
            "router_posts_contract_violation_bug_report": True,
            "contract_violation_bug_report_issue_comment_required": True,
            "contract_violation_bug_report_marker_required": True,
            "contract_violation_bug_report_default_status": "authentication_blocked",
            "contract_violation_bug_report_wrong_session_status": "reassign_required",
            "contract_violation_bug_report_fields": [
                "observed_violation",
                "expected_contract",
                "impact_or_risk",
                "pending_fingerprints",
                "worker_or_session_ids",
                "recommended_next_action",
            ],
            "workers_may_be_non_visible": True,
            "subagents_may_be_non_visible": True,
        }
        payload["pending_contract"] = {
            "pending_dir": ".core_program/pending",
            "pending_path": pending_path_text,
            "queue_file_moved_to_pending_before_router_send": pending_path is not None,
            "router_should_scan_all_pending_records": True,
            "router_should_dispatch_selected_pending_records_itself": True,
            "archive_pending_after_final_comment": True,
            "archive_command_template": "mv .core_program/pending/xxx.md .core_program/archive/xxx.md",
            "do_not_archive_before_comment_marker": True,
        }
        payload["source_queue_record"] = _record_payload(source)
        payload["source_prompt_kind"] = source.prompt_kind
        payload["source_recipient_role"] = source.recipient_role
        payload["source_target_session_id"] = source.target_session_id
        payload["router_session_id"] = router_session_id or record.target_session_id
    else:
        payload["worker_contract"] = {
            "process_issue_thread_update": True,
            "process_issue_event": True,
            "post_github_comment": not local_demo,
            "commit_and_push_if_files_changed": not local_demo,
            "report_planned_comment_without_posting": local_demo,
            "may_spawn_subagents_for_minimal_implementation_and_verification_pairs": True,
            "subagents_do_not_post_github_markers": True,
            "permission_blocked_must_report_authentication_blocked_to_router": True,
            "archive_pending_after_final_comment": True,
            "archive_command_template": "mv .core_program/pending/xxx.md .core_program/archive/xxx.md",
            "do_not_archive_before_comment_marker": True,
        }
        payload["github_comment_contract"] = {
            "visible_comment_required": not local_demo,
            "post_comment_required": not local_demo,
            "planned_comment_report_required": local_demo,
            "marker_required": True,
            "marker_statuses": [
                "done",
                "reassign_required",
                "authentication_blocked",
            ],
        }
        payload["git_contract"] = {
            "commit_required_when_files_change": not local_demo,
            "push_required": not local_demo,
            "push_remote": "origin",
            "do_not_push_remote": "upstream",
        }

    demo_notice = (
        "This is a local ArtifactForge demo task. Do not call GitHub, post comments, commit, or push; "
        "report the planned comment and marker in the session only.\n\n"
        if local_demo
        else ""
    )
    if record.recipient_role == "router":
        template_text = _router_orchestration_instructions(
            pending_dir=pending_dir,
            pending_path=pending_path,
        )
        received_line = (
            "You are receiving this prompt because you are the visible "
            "Session_router orchestrator.\n\n"
        )
        recipient_notes = (
            "Expected recipient:\n"
            "- recipient_role: router\n"
            f"- target_session_id: {record.target_session_id}\n"
            f"- source_recipient_role: {source.recipient_role}\n"
            f"- source_target_session_id: {source.target_session_id}\n\n"
            "If your current session ID is not target_session_id, do not perform the work.\n"
            "Read `.core_program/pending` before dispatching or delegating work.\n"
            "The dispatcher will not resume worker sessions directly. Dispatch, delegate, "
            "and coordinate workers/subagents yourself from this visible Session_router.\n\n"
        )
    else:
        template_text = _read_prompt(template_path)
        received_line = (
            "You are receiving this prompt because your session ID is the dispatch target.\n\n"
        )
        recipient_notes = (
            "Expected recipient:\n"
            f"- recipient_role: {record.recipient_role}\n"
            f"- target_session_id: {record.target_session_id}\n\n"
            "If your current session ID is not target_session_id, do not perform the work.\n"
            "The user's human-facing interface is the Session_router; subagents may be non-visible.\n"
            "Any login, approval, permission, or TTY requirement must be routed through the Session_router.\n"
            "If recipient_role is worker, process the issue thread update as the assigned worker.\n"
            "If recipient_role is router, read `.core_program/pending` and dispatch/delegate from there; "
            "do not ask the dispatcher to send worker prompts.\n\n"
        )
    return (
        "ArtifactForge Dispatch Prompt v1\n\n"
        f"{received_line}"
        f"{recipient_notes}"
        f"{demo_notice}"
        f"{template_text}\n\n"
        "DISPATCH_V1_INPUT\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def build_session_router_prompt(
    record: QueueRecord,
    *,
    router_session_id: Optional[str] = None,
    repo_dir: str | Path = REPO_ROOT,
    template_path: str | Path = DEFAULT_DISPATCH_PROMPT,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    pending_path: Optional[Union[str, Path]] = None,
) -> str:
    target_session_id = (
        router_session_id
        or (record.target_session_id if record.recipient_role == "router" else "<router-session-id>")
    )
    router_record = replace(
        record,
        target_session_id=target_session_id,
        prompt_kind="session_router",
    )
    return build_dispatch_prompt(
        router_record,
        repo_dir=repo_dir,
        template_path=template_path,
        pending_dir=pending_dir,
        pending_path=pending_path,
        router_session_id=router_session_id,
        source_record=record,
    )


def build_session_router_bootstrap_prompt(
    *,
    repo_dir: str | Path = REPO_ROOT,
    template_path: str | Path = DEFAULT_SESSION_ROUTER_BOOTSTRAP_PROMPT,
) -> str:
    payload = {
        "schema_version": 1,
        "repository": str(repo_dir),
        "constraints": {
            "session_router_must_not_do_worker_work": True,
            "session_router_output": "one session id line only",
        },
    }
    return (
        f"{_read_prompt(template_path)}\n\n"
        "SESSION_ROUTER_BOOTSTRAP_V1_INPUT\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def build_worker_prompt(
    record: QueueRecord,
    *,
    session_id: Optional[str] = None,
    repo_dir: str | Path = REPO_ROOT,
    template_path: str | Path = DEFAULT_DISPATCH_PROMPT,
) -> str:
    worker_record = replace(
        record,
        target_session_id=session_id or record.target_session_id,
        prompt_kind="worker",
    )
    return build_dispatch_prompt(
        worker_record,
        repo_dir=repo_dir,
        template_path=template_path,
    )


def pending_destination(path: str | Path, pending_dir: str | Path, session_id: str) -> Path:
    source = Path(path)
    target_dir = Path(pending_dir)
    candidate = target_dir / source.name
    if not candidate.exists():
        return candidate
    for index in range(2, 10_000):
        candidate = target_dir / f"{source.stem}.{index}{source.suffix}"
        if not candidate.exists():
            return candidate
    raise DispatchError(f"could not allocate pending path for {source.name}")


def dispatch_session_visibility(record: QueueRecord) -> str:
    if record.recipient_role == "router":
        return "visible"
    return "non_visible"


def is_local_demo_record(record: QueueRecord) -> bool:
    event_type = (record.event_type or "").lower()
    issue_url = (record.issue_url or "").lower()
    return (
        "demo" in event_type
        or "agent_flow_demo" in event_type
        or "real_codex_demo" in event_type
        or issue_url.startswith("https://example.invalid/")
    )


def duplicate_dispatch_reason(
    record: QueueRecord,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    archive_dir: str | Path = DEFAULT_ARCHIVE_DIR,
) -> Optional[str]:
    if _fingerprint_in_index(
        collect_existing_fingerprints(archive_dir),
        record.trigger_fingerprint,
    ):
        return "fingerprint_already_archived"

    pending_sessions = _pending_sessions_for_fingerprint(
        pending_dir,
        record.trigger_fingerprint,
    )
    if not pending_sessions:
        return None

    if record.reassign_required and record.previous_thread_id:
        if all(session_id == record.previous_thread_id for session_id in pending_sessions):
            return None
        return "reassign_handoff_already_pending"

    return "fingerprint_already_pending"


def target_session_busy_reason(
    record: QueueRecord,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
) -> Optional[str]:
    if target_session_has_unresolved_pending(
        record.target_session_id,
        pending_dir=pending_dir,
    ):
        return "session_has_unresolved_pending"
    return None


def router_session_busy_reason(
    router_session_id: Optional[str],
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
) -> Optional[str]:
    if router_session_id and target_session_has_unresolved_pending(
        router_session_id,
        pending_dir=pending_dir,
    ):
        return "session_has_unresolved_pending"
    return None


def target_session_has_unresolved_pending(
    session_id: str,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
) -> bool:
    target_session_id = str(session_id).strip()
    if not target_session_id:
        return False
    for record in iter_pending_records(pending_dir):
        if record.session_id == target_session_id:
            return True
    return False


def _pending_sessions_for_fingerprint(
    pending_dir: str | Path,
    fingerprint: str,
) -> Tuple[str, ...]:
    sessions = []
    for record in iter_pending_records(pending_dir):
        if _fingerprints_match(record.trigger_fingerprint, fingerprint):
            sessions.append(record.session_id)
    return tuple(sessions)


def _fingerprint_in_index(fingerprints: Iterable[str], fingerprint: str) -> bool:
    return any(_fingerprints_match(value, fingerprint) for value in fingerprints)


def _fingerprints_match(left: str, right: str) -> bool:
    return left == right or safe_filename_part(left) == safe_filename_part(right)


def assignment_session_id(path: str | Path, *, issue_number: int) -> Optional[str]:
    payload = _read_assignment_state(path)
    for assignment in payload.get("assignments", []):
        if int(assignment.get("issue_number", -1)) != issue_number:
            continue
        session_id = str(assignment.get("session_id") or "").strip()
        if session_id:
            return session_id
    return None


def assignment_router_session_id(path: str | Path) -> Optional[str]:
    payload = _read_assignment_state(path)
    value = payload.get("router_session_id")
    if value is None:
        return None
    session_id = str(value).strip()
    return session_id or None


def wait_for_assignment_session_id(
    path: str | Path,
    *,
    issue_number: int,
    timeout_seconds: Optional[int] = None,
    poll_seconds: float = 1.0,
) -> str:
    timeout = (
        _env_int(
            "ARTIFACTFORGE_ROUTER_ASSIGNMENT_WAIT_SECONDS",
            DEFAULT_ROUTER_ASSIGNMENT_WAIT_SECONDS,
        )
        if timeout_seconds is None
        else max(0, timeout_seconds)
    )
    deadline = time.time() + timeout
    while True:
        session_id = assignment_session_id(path, issue_number=issue_number)
        if session_id:
            return session_id
        if time.time() >= deadline:
            raise DispatchError(
                "visible Session_router did not update assignment_state.json "
                f"for issue #{issue_number} within {timeout} seconds"
            )
        time.sleep(poll_seconds)


def _record_router_session_id(record: QueueRecord) -> Optional[str]:
    if record.recipient_role == "router":
        return record.target_session_id
    return None


def _planned_router_session_id(
    record: QueueRecord,
    *,
    assignment_state_path: Optional[Union[str, Path]],
) -> Optional[str]:
    if assignment_state_path is not None:
        state_session_id = assignment_router_session_id(assignment_state_path)
        if state_session_id:
            return state_session_id
    return _record_router_session_id(record)


def _resolve_router_session_id(
    record: QueueRecord,
    *,
    assignment_state_path: Optional[Union[str, Path]],
    repo_dir: str | Path,
    codex_bin: str | Path,
    runner: Runner,
    dry_run: bool,
) -> Optional[str]:
    planned = _planned_router_session_id(
        record,
        assignment_state_path=assignment_state_path,
    )
    if planned:
        return planned
    if dry_run:
        return None
    if assignment_state_path is None:
        raise DispatchError(
            "worker-targeted queue records must be routed through Session_router; "
            "provide assignment_state_path with router_session_id"
        )
    return bootstrap_session_router(
        assignment_state_path=assignment_state_path,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
        runner=runner,
    )


def _router_command(
    *,
    codex_bin: str | Path,
    repo_dir: str | Path,
    router_session_id: Optional[str],
    prompt: str,
) -> Tuple[str, ...]:
    return (
        str(codex_bin),
        "resume",
        "--cd",
        str(repo_dir),
        "--include-non-interactive",
        router_session_id or "<router-session-id>",
        prompt,
    )


def _build_dispatch_plan(
    path: Path,
    record: QueueRecord,
    *,
    pending_dir: str | Path,
    pending_path: Path,
    repo_dir: str | Path,
    codex_bin: str | Path,
    router_session_id: Optional[str],
) -> DispatchPlan:
    prompt = build_session_router_prompt(
        record,
        router_session_id=router_session_id,
        repo_dir=repo_dir,
        pending_dir=pending_dir,
        pending_path=pending_path,
    )
    return DispatchPlan(
        queue_path=path,
        record=record,
        prompt=prompt,
        command=_router_command(
            codex_bin=codex_bin,
            repo_dir=repo_dir,
            router_session_id=router_session_id,
            prompt=prompt,
        ),
        pending_path=pending_path,
        session_visibility="visible",
        router_session_id=router_session_id,
    )


def plan_dispatch(
    queue_path: str | Path,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    assignment_state_path: Optional[Union[str, Path]] = None,
    router_session_id: Optional[str] = None,
) -> DispatchPlan:
    path = Path(queue_path)
    record = parse_queue_file(path)
    pending_path = pending_destination(path, pending_dir, record.target_session_id)
    planned_router_session_id = router_session_id or _planned_router_session_id(
        record=record,
        assignment_state_path=assignment_state_path,
    )
    return _build_dispatch_plan(
        path,
        record,
        pending_dir=pending_dir,
        pending_path=pending_path,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
        router_session_id=planned_router_session_id,
    )


def dispatch_queue_file(
    queue_path: str | Path,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    archive_dir: str | Path = DEFAULT_ARCHIVE_DIR,
    dry_run: bool = False,
    move_to_pending: bool = True,
    runner: Runner = _default_runner,
    assignment_state_path: Optional[Union[str, Path]] = None,
    router_session_id: Optional[str] = None,
) -> DispatchResult:
    plan = plan_dispatch(
        queue_path,
        pending_dir=pending_dir,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
        assignment_state_path=assignment_state_path,
        router_session_id=router_session_id,
    )
    skip_reason = duplicate_dispatch_reason(
        plan.record,
        pending_dir=pending_dir,
        archive_dir=archive_dir,
    )
    if not skip_reason:
        skip_reason = router_session_busy_reason(
            plan.router_session_id,
            pending_dir=pending_dir,
        )
    if skip_reason:
        return DispatchResult(
            plan=plan,
            sent=False,
            moved_to_pending=False,
            session_id=plan.router_session_id or plan.record.target_session_id,
            router_session_id=plan.router_session_id,
            skipped=True,
            skip_reason=skip_reason,
            dry_run=dry_run,
            move_to_pending=move_to_pending,
        )
    if dry_run:
        return DispatchResult(
            plan=plan,
            sent=False,
            moved_to_pending=False,
            session_id=plan.router_session_id or plan.record.target_session_id,
            router_session_id=plan.router_session_id,
            dry_run=True,
            move_to_pending=move_to_pending,
        )

    moved = False
    pending_path = plan.pending_path
    try:
        resolved_router_session_id = _resolve_router_session_id(
            plan.record,
            assignment_state_path=assignment_state_path,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
            runner=runner,
            dry_run=False,
        )
        if not resolved_router_session_id:
            raise DispatchError("Session_router session ID could not be resolved")
        if resolved_router_session_id != plan.router_session_id:
            plan = plan_dispatch(
                queue_path,
                pending_dir=pending_dir,
                repo_dir=repo_dir,
                codex_bin=codex_bin,
                assignment_state_path=assignment_state_path,
                router_session_id=resolved_router_session_id,
            )
            skip_reason = router_session_busy_reason(
                resolved_router_session_id,
                pending_dir=pending_dir,
            )
            if skip_reason:
                return DispatchResult(
                    plan=plan,
                    sent=False,
                    moved_to_pending=False,
                    session_id=resolved_router_session_id,
                    router_session_id=resolved_router_session_id,
                    skipped=True,
                    skip_reason=skip_reason,
                    move_to_pending=move_to_pending,
                )

        pending_path = pending_destination(queue_path, pending_dir, plan.record.target_session_id)
        if pending_path != plan.pending_path:
            plan = _build_dispatch_plan(
                Path(queue_path),
                plan.record,
                pending_dir=pending_dir,
                pending_path=pending_path,
                repo_dir=repo_dir,
                codex_bin=codex_bin,
                router_session_id=resolved_router_session_id,
            )

        if move_to_pending:
            pending_path.parent.mkdir(parents=True, exist_ok=True)
            Path(queue_path).rename(pending_path)
            moved = True
            plan = _build_dispatch_plan(
                Path(queue_path),
                plan.record,
                pending_dir=pending_dir,
                pending_path=pending_path,
                repo_dir=repo_dir,
                codex_bin=codex_bin,
                router_session_id=resolved_router_session_id,
            )

        result = _run_session_router(
            runner,
            plan.prompt,
            router_session_id=resolved_router_session_id,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
        )
        if not result.ok:
            raise DispatchError(_dispatch_failure_message(result, plan.record))
        session_id = resolved_router_session_id
    except Exception as exc:
        restore_error = None
        if moved:
            try:
                _restore_pending_to_queue(pending_path, Path(queue_path))
                moved = False
            except Exception as restore_exc:
                restore_error = str(restore_exc)
        error_message = str(exc)
        if restore_error:
            error_message = f"{error_message}; pending restore failed: {restore_error}"
        return DispatchResult(
            plan=plan,
            sent=False,
            moved_to_pending=moved,
            session_id=plan.router_session_id or plan.record.target_session_id,
            router_session_id=plan.router_session_id,
            error=error_message,
            move_to_pending=move_to_pending,
        )

    return DispatchResult(
        plan=plan,
        sent=True,
        moved_to_pending=moved,
        session_id=session_id,
        router_session_id=session_id,
        move_to_pending=move_to_pending,
    )


def dispatch_queue(
    queue_dir: str | Path = DEFAULT_QUEUE_DIR,
    *,
    inflight_dir: str | Path = DEFAULT_INFLIGHT_DIR,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    archive_dir: str | Path = DEFAULT_ARCHIVE_DIR,
    locks_dir: str | Path = DEFAULT_LOCKS_DIR,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    dry_run: bool = False,
    move_to_pending: bool = True,
    runner: Runner = _default_runner,
    assignment_state_path: Optional[Union[str, Path]] = None,
    limit: Optional[int] = None,
    parallel: int = 1,
    claim_files: bool = True,
    session_lock_timeout_seconds: Optional[float] = None,
) -> Tuple[DispatchResult, ...]:
    paths = iter_queue_paths(queue_dir)
    if limit is not None:
        paths = paths[: max(0, limit)]
    prepared = _prepare_pending_batch_paths(
        paths,
        pending_dir=pending_dir,
        archive_dir=archive_dir,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
        assignment_state_path=assignment_state_path,
        dry_run=dry_run,
        move_to_pending=move_to_pending,
    )
    results_by_index = {
        index: result
        for index, _, result in prepared
        if result is not None
    }
    work_items = [(index, plan) for index, plan, result in prepared if result is None]

    if dry_run or not work_items:
        for index, plan in work_items:
            results_by_index[index] = DispatchResult(
                plan=plan,
                sent=False,
                moved_to_pending=False,
                session_id=plan.router_session_id or plan.record.target_session_id,
                router_session_id=plan.router_session_id,
                dry_run=dry_run,
                move_to_pending=move_to_pending,
            )
        return tuple(results_by_index[index] for index in sorted(results_by_index))

    router_session_id = work_items[0][1].router_session_id
    if not router_session_id:
        for index, plan in work_items:
            results_by_index[index] = DispatchResult(
                plan=plan,
                sent=False,
                moved_to_pending=False,
                session_id=plan.record.target_session_id,
                router_session_id=plan.router_session_id,
                error="Session_router session ID could not be resolved",
                move_to_pending=move_to_pending,
            )
        return tuple(results_by_index[index] for index in sorted(results_by_index))

    lock_path = None
    moved_results = []
    try:
        lock_path = acquire_session_lock(
            router_session_id,
            locks_dir=locks_dir,
            timeout_seconds=session_lock_timeout_seconds,
        )
        for index, plan in work_items:
            result = _move_plan_to_pending(
                plan,
                inflight_dir=inflight_dir,
                pending_dir=pending_dir,
                locks_dir=locks_dir,
                repo_dir=repo_dir,
                claim_files=claim_files,
                move_to_pending=move_to_pending,
            )
            moved_results.append((index, result))
            results_by_index[index] = result

        pending_plans = tuple(
            result.plan
            for _, result in moved_results
            if result.moved_to_pending
        )
        if pending_plans:
            prompt = build_session_router_batch_prompt(
                pending_plans,
                router_session_id=router_session_id,
                pending_dir=pending_dir,
                repo_dir=repo_dir,
            )
            run_result = _run_session_router(
                runner,
                prompt,
                router_session_id=router_session_id,
                repo_dir=repo_dir,
                codex_bin=codex_bin,
            )
            if not run_result.ok:
                error = _dispatch_failure_message(
                    run_result,
                    pending_plans[0].record,
                )
                for index, result in moved_results:
                    results_by_index[index] = DispatchResult(
                        plan=replace(result.plan, prompt=prompt),
                        sent=False,
                        moved_to_pending=result.moved_to_pending,
                        session_id=router_session_id,
                        router_session_id=router_session_id,
                        error=error,
                        move_to_pending=move_to_pending,
                    )
            else:
                for index, result in moved_results:
                    results_by_index[index] = DispatchResult(
                        plan=replace(result.plan, prompt=prompt),
                        sent=True,
                        moved_to_pending=result.moved_to_pending,
                        session_id=router_session_id,
                        router_session_id=router_session_id,
                        move_to_pending=move_to_pending,
                    )
    except Exception as exc:
        for index, plan in work_items:
            if index not in results_by_index or not results_by_index[index].moved_to_pending:
                results_by_index[index] = DispatchResult(
                    plan=plan,
                    sent=False,
                    moved_to_pending=False,
                    session_id=plan.router_session_id or plan.record.target_session_id,
                    router_session_id=plan.router_session_id,
                    error=str(exc),
                    move_to_pending=move_to_pending,
                )
    finally:
        if lock_path is not None:
            release_file_lock(lock_path)

    return tuple(results_by_index[index] for index in sorted(results_by_index))


def _prepare_pending_batch_paths(
    paths: Tuple[Path, ...],
    *,
    pending_dir: str | Path,
    archive_dir: str | Path,
    repo_dir: str | Path,
    codex_bin: str | Path,
    assignment_state_path: Optional[Union[str, Path]],
    dry_run: bool,
    move_to_pending: bool,
) -> Tuple[Tuple[int, DispatchPlan, Optional[DispatchResult]], ...]:
    prepared = []
    seen_fingerprints = set()
    for index, path in enumerate(paths):
        try:
            source_record = read_queue_record(path)
            router_session_id = _planned_router_session_id(
                source_record,
                assignment_state_path=assignment_state_path,
            )
            if not router_session_id:
                router_session_id = source_record.target_session_id
                if source_record.recipient_role != "router":
                    router_session_id = ""
            router_record = _router_pending_record(source_record, router_session_id)
            pending_path = pending_destination(path, pending_dir, router_session_id)
            plan = _build_dispatch_plan(
                path,
                router_record,
                pending_dir=pending_dir,
                pending_path=pending_path,
                repo_dir=repo_dir,
                codex_bin=codex_bin,
                router_session_id=router_session_id or None,
            )
        except FileNotFoundError:
            continue
        except Exception as exc:
            plan = _parse_error_plan(
                path,
                pending_dir=pending_dir,
                repo_dir=repo_dir,
                codex_bin=codex_bin,
            )
            prepared.append(
                (
                    index,
                    plan,
                    DispatchResult(
                        plan=plan,
                        sent=False,
                        moved_to_pending=False,
                        session_id=plan.record.target_session_id,
                        router_session_id=plan.router_session_id,
                        error=str(exc),
                        dry_run=dry_run,
                        move_to_pending=move_to_pending,
                    ),
                )
            )
            continue

        if not router_session_id:
            prepared.append(
                (
                    index,
                    plan,
                    DispatchResult(
                        plan=plan,
                        sent=False,
                        moved_to_pending=False,
                        session_id=plan.record.target_session_id,
                        router_session_id=plan.router_session_id,
                        error="assignment_state must include router_session_id",
                        dry_run=dry_run,
                        move_to_pending=move_to_pending,
                    ),
                )
            )
            continue

        skip_reason = duplicate_dispatch_reason(
            plan.record,
            pending_dir=pending_dir,
            archive_dir=archive_dir,
        )
        if not skip_reason and plan.record.trigger_fingerprint in seen_fingerprints:
            skip_reason = "fingerprint_already_selected"
        if skip_reason:
            prepared.append(
                (
                    index,
                    plan,
                    DispatchResult(
                        plan=plan,
                        sent=False,
                        moved_to_pending=False,
                        session_id=router_session_id,
                        router_session_id=router_session_id,
                        skipped=True,
                        skip_reason=skip_reason,
                        dry_run=dry_run,
                        move_to_pending=move_to_pending,
                    ),
                )
            )
            continue
        seen_fingerprints.add(plan.record.trigger_fingerprint)
        prepared.append((index, plan, None))
    return tuple(prepared)


def _router_pending_record(record: QueueRecord, router_session_id: str) -> QueueRecord:
    return replace(
        record,
        target_session_id=router_session_id,
        prompt_kind="session_router",
    )


def _parse_error_plan(
    path: Path,
    *,
    pending_dir: str | Path,
    repo_dir: str | Path,
    codex_bin: str | Path,
) -> DispatchPlan:
    record = QueueRecord(
        issue_number=0,
        issue_url="",
        issue_title=path.name,
        event_type="parse_error",
        trigger_fingerprint=f"parse-error-{safe_filename_part(path.stem)}",
        target_session_id="",
        prompt_kind="session_router",
        body="",
        source_id=None,
    )
    return _build_dispatch_plan(
        path,
        record,
        pending_dir=pending_dir,
        pending_path=pending_destination(path, pending_dir, "parse_error"),
        repo_dir=repo_dir,
        codex_bin=codex_bin,
        router_session_id=None,
    )


def _move_plan_to_pending(
    plan: DispatchPlan,
    *,
    inflight_dir: str | Path,
    pending_dir: str | Path,
    locks_dir: str | Path,
    repo_dir: str | Path,
    claim_files: bool,
    move_to_pending: bool,
) -> DispatchResult:
    if not move_to_pending:
        return DispatchResult(
            plan=plan,
            sent=False,
            moved_to_pending=False,
            session_id=plan.router_session_id or plan.record.target_session_id,
            router_session_id=plan.router_session_id,
            move_to_pending=move_to_pending,
        )

    queue_path = plan.queue_path
    claim = None
    if claim_files:
        claim = claim_queue_file(queue_path, inflight_dir=inflight_dir, locks_dir=locks_dir)
        if claim is None:
            return DispatchResult(
                plan=plan,
                sent=False,
                moved_to_pending=False,
                session_id=plan.router_session_id or plan.record.target_session_id,
                router_session_id=plan.router_session_id,
                skipped=True,
                skip_reason="queue_already_claimed",
                move_to_pending=move_to_pending,
            )
        queue_path = claim.claimed_path

    pending_path = pending_destination(
        queue_path,
        pending_dir,
        plan.router_session_id or plan.record.target_session_id,
    )
    final_plan = replace(
        plan,
        queue_path=queue_path,
        pending_path=pending_path,
        prompt=build_session_router_prompt(
            plan.record,
            router_session_id=plan.router_session_id,
            repo_dir=repo_dir,
            pending_dir=pending_dir,
            pending_path=pending_path,
        ),
    )
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(build_queue_markdown(final_plan.record), encoding="utf-8")
    try:
        queue_path.unlink()
    except FileNotFoundError:
        pass
    return DispatchResult(
        plan=final_plan,
        sent=False,
        moved_to_pending=True,
        session_id=final_plan.router_session_id or final_plan.record.target_session_id,
        router_session_id=final_plan.router_session_id,
        move_to_pending=move_to_pending,
    )


def build_session_router_batch_prompt(
    plans: Tuple[DispatchPlan, ...],
    *,
    router_session_id: str,
    pending_dir: str | Path,
    repo_dir: str | Path = REPO_ROOT,
) -> str:
    pending_items = [
        {
            "pending_path": str(plan.pending_path),
            "issue_number": plan.record.issue_number,
            "issue_title": plan.record.issue_title,
            "issue_url": plan.record.issue_url,
            "event_type": plan.record.event_type,
            "trigger_fingerprint": plan.record.trigger_fingerprint,
            "sub_artifact_path": plan.record.sub_artifact_path,
            "reassign_required": plan.record.reassign_required,
            "previous_thread_id": plan.record.previous_thread_id,
        }
        for plan in plans
    ]
    payload: Dict[str, object] = {
        "schema_version": 1,
        "repository": str(repo_dir),
        "recipient_role": "router",
        "target_session_id": router_session_id,
        "pending_dir": str(pending_dir),
        "pending_items": pending_items,
        "orchestrator_contract": {
            "python_scope": "fetch_dedupe_queue_to_pending_and_invoke_router",
            "dispatcher_will_not_resume_worker_sessions": True,
            "request_for_human_dir": ".core_program/request_for_human",
            "check_request_for_human_empty_before_pending": True,
            "write_request_for_human_memo_before_user_question": True,
            "request_for_human_template": {
                "日時": "",
                "Pending fingerprints": "",
                "Worker session ID": "",
                "問い合わせ内容": "",
            },
            "archive_pending_after_final_comment": True,
            "archive_command_template": "mv .core_program/pending/xxx.md .core_program/archive/xxx.md",
            "do_not_archive_before_comment_marker": True,
            "router_reads_pending_as_worklist": True,
            "assignment_state_is_advisory_routing_state": True,
            "router_is_only_user_permission_gateway": True,
            "router_existing_capabilities_may_be_granted_to_subagents": True,
            "new_or_broader_capabilities_require_user_approval": True,
            "router_posts_contract_violation_bug_report": True,
            "contract_violation_bug_report_issue_comment_required": True,
            "contract_violation_bug_report_marker_required": True,
            "contract_violation_bug_report_default_status": "authentication_blocked",
            "contract_violation_bug_report_wrong_session_status": "reassign_required",
            "workers_and_subagents_may_be_non_visible": True,
            "do_not_send_concurrent_prompts_to_same_child_session": True,
            "dispatch_minimal_feature_units_with_implementation_and_verification_pairs": True,
            "default_child_model": "GPT-5.4-high",
            "may_escalate_child_model_to": "GPT-5.5-high",
        },
    }
    return (
        "ArtifactForge Session_router Orchestrator Prompt v1\n\n"
        "You are receiving this prompt because queue files were moved to pending.\n\n"
        "Expected recipient:\n"
        "- recipient_role: router\n"
        f"- target_session_id: {router_session_id}\n\n"
        "If your current session ID is not target_session_id, do not perform the work.\n"
        "Read `.core_program/pending` before dispatching or delegating work.\n"
        "Python has already fetched issue updates, de-duplicated them, and moved the selected queue files to pending.\n"
        "Python will not resume worker sessions directly. You are the single visible orchestrator.\n\n"
        f"{_router_orchestration_instructions(pending_dir=pending_dir, pending_path=None)}\n\n"
        "SESSION_ROUTER_ORCHESTRATOR_V1_INPUT\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def dispatch_queue_dir(
    queue_dir: str | Path = DEFAULT_QUEUE_DIR,
    **kwargs: Any,
) -> Tuple[DispatchResult, ...]:
    return dispatch_queue(queue_dir, **kwargs)


def _prepare_dispatch_paths(
    paths: Tuple[Path, ...],
    *,
    pending_dir: str | Path,
    archive_dir: str | Path,
    repo_dir: str | Path,
    codex_bin: str | Path,
    assignment_state_path: Optional[Union[str, Path]],
    dry_run: bool,
    move_to_pending: bool,
) -> Tuple[Tuple[int, Path, Optional[DispatchResult]], ...]:
    prepared = []
    selected_router_invocation = False
    for index, path in enumerate(paths):
        try:
            plan = plan_dispatch(
                path,
                pending_dir=pending_dir,
                repo_dir=repo_dir,
                codex_bin=codex_bin,
                assignment_state_path=assignment_state_path,
            )
        except FileNotFoundError:
            continue
        skip_reason = duplicate_dispatch_reason(
            plan.record,
            pending_dir=pending_dir,
            archive_dir=archive_dir,
        )
        if not skip_reason:
            skip_reason = router_session_busy_reason(
                plan.router_session_id,
                pending_dir=pending_dir,
            )
        if not skip_reason and selected_router_invocation:
            skip_reason = "target_session_already_dispatched_this_run"
        if skip_reason:
            prepared.append(
                (
                    index,
                    path,
                    DispatchResult(
                        plan=plan,
                        sent=False,
                        moved_to_pending=False,
                        session_id=plan.router_session_id or plan.record.target_session_id,
                        router_session_id=plan.router_session_id,
                        skipped=True,
                        skip_reason=skip_reason,
                        dry_run=dry_run,
                        move_to_pending=move_to_pending,
                    ),
                )
            )
            continue
        selected_router_invocation = True
        prepared.append((index, path, None))
    return tuple(prepared)


def _dispatch_queue_path(
    path: Path,
    *,
    inflight_dir: str | Path,
    pending_dir: str | Path,
    archive_dir: str | Path,
    locks_dir: str | Path,
    repo_dir: str | Path,
    codex_bin: str | Path,
    dry_run: bool,
    move_to_pending: bool,
    runner: Runner,
    assignment_state_path: Optional[Union[str, Path]],
    claim_files: bool,
    session_lock_timeout_seconds: Optional[float],
) -> Optional[DispatchResult]:
    if dry_run or not claim_files:
        queue_path = path
        claim = None
    else:
        claim = claim_queue_file(path, inflight_dir=inflight_dir, locks_dir=locks_dir)
        if claim is None:
            return None
        queue_path = claim.claimed_path

    lock_path = None
    try:
        record = read_queue_record(queue_path)
        router_session_id = _resolve_router_session_id(
            record,
            assignment_state_path=assignment_state_path,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
            runner=runner,
            dry_run=dry_run,
        )
        if not dry_run:
            if not router_session_id:
                raise DispatchError("Session_router session ID could not be resolved")
            lock_path = acquire_session_lock(
                router_session_id,
                locks_dir=locks_dir,
                timeout_seconds=session_lock_timeout_seconds,
            )
        result = dispatch_queue_file(
            queue_path,
            pending_dir=pending_dir,
            archive_dir=archive_dir,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
            dry_run=dry_run,
            move_to_pending=move_to_pending,
            runner=runner,
            assignment_state_path=assignment_state_path,
            router_session_id=router_session_id,
        )
        if claim is not None and _should_restore_claim(result):
            _restore_claimed_queue_file(claim)
        return result
    except FileNotFoundError:
        return None
    except Exception as exc:
        try:
            plan = plan_dispatch(
                queue_path,
                pending_dir=pending_dir,
                repo_dir=repo_dir,
                codex_bin=codex_bin,
                assignment_state_path=assignment_state_path,
            )
        except Exception:
            if claim is not None:
                _restore_claimed_queue_file(claim)
            return None
        if claim is not None:
            _restore_claimed_queue_file(claim)
        return DispatchResult(
            plan=plan,
            sent=False,
            moved_to_pending=False,
            session_id=plan.router_session_id or plan.record.target_session_id,
            router_session_id=plan.router_session_id,
            error=str(exc),
            move_to_pending=move_to_pending,
        )
    finally:
        if lock_path is not None:
            release_file_lock(lock_path)


def _should_restore_claim(result: DispatchResult) -> bool:
    return not result.moved_to_pending


def claim_queue_file(
    path: str | Path,
    *,
    inflight_dir: str | Path = DEFAULT_INFLIGHT_DIR,
    locks_dir: str | Path = DEFAULT_LOCKS_DIR,
) -> Optional[QueueClaim]:
    source = Path(path)
    if not source.exists():
        return None
    lock_path = _queue_claim_lock_path(source, locks_dir)
    try:
        acquire_file_lock(lock_path, timeout_seconds=0)
    except DispatchError:
        return None
    try:
        if not source.exists():
            return None
        destination = _unique_destination(Path(inflight_dir), source.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        return QueueClaim(original_path=source, claimed_path=destination)
    finally:
        release_file_lock(lock_path)


def _restore_claimed_queue_file(claim: QueueClaim) -> Path:
    if not claim.claimed_path.exists():
        return claim.original_path
    destination = claim.original_path
    if destination.exists():
        destination = _unique_destination(destination.parent, destination.name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    claim.claimed_path.rename(destination)
    return destination


def _restore_pending_to_queue(pending_path: Path, queue_path: Path) -> Path:
    if not pending_path.exists():
        return queue_path
    destination = queue_path
    if destination.exists():
        destination = _unique_destination(destination.parent, destination.name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending_path.rename(destination)
    return destination


def _queue_claim_lock_path(path: Path, locks_dir: str | Path) -> Path:
    return Path(locks_dir) / f"queue_{safe_filename_part(path.name)}.lock"


def acquire_session_lock(
    session_id: str,
    *,
    locks_dir: str | Path = DEFAULT_LOCKS_DIR,
    timeout_seconds: Optional[float] = None,
) -> Path:
    lock_name = f"session_{safe_filename_part(session_id)}.lock"
    return acquire_file_lock(
        Path(locks_dir) / lock_name,
        timeout_seconds=timeout_seconds,
    )


def acquire_file_lock(
    path: str | Path,
    *,
    timeout_seconds: Optional[float] = None,
    poll_seconds: float = 0.1,
) -> Path:
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = None if timeout_seconds is None else time.time() + max(0, timeout_seconds)
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if deadline is not None and time.time() >= deadline:
                raise DispatchError(f"lock already held: {lock_path}")
            time.sleep(poll_seconds)
            continue
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"pid={os.getpid()}\n")
            return lock_path


def release_file_lock(path: str | Path) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


def _unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    source = Path(filename)
    for index in range(2, 10_000):
        candidate = directory / f"{source.stem}.{index}{source.suffix}"
        if not candidate.exists():
            return candidate
    raise DispatchError(f"could not allocate destination for {filename}")


def dispatch_results_to_dict(results: Iterable[DispatchResult]) -> Dict[str, object]:
    result_tuple = tuple(results)
    router_targets = tuple(
        result.router_session_id
        for result in result_tuple
        if result.router_session_id
    )
    skip_reasons = sorted(
        {
            str(result.skip_reason)
            for result in result_tuple
            if result.skip_reason
        }
    )
    defer_reasons = sorted(
        {
            str(result.skip_reason)
            for result in result_tuple
            if result.skip_reason in SESSION_DEFER_REASONS
        }
    )
    return {
        "schema_version": 1,
        "entry_count": len(result_tuple),
        "sent_count": sum(1 for result in result_tuple if result.sent),
        "moved_to_pending_count": sum(
            1 for result in result_tuple if result.moved_to_pending
        ),
        "dry_run_count": sum(1 for result in result_tuple if result.dry_run),
        "failed_count": sum(1 for result in result_tuple if result.error),
        "skipped_count": sum(1 for result in result_tuple if result.skipped),
        "deferred_count": sum(
            1
            for result in result_tuple
            if result.skipped and result.skip_reason in SESSION_DEFER_REASONS
        ),
        "router_target_session_id": router_targets[0] if router_targets else None,
        "router_target_session_ids": sorted(set(router_targets)),
        "skip_reasons": skip_reasons,
        "defer_reasons": defer_reasons,
        "items": [
            {
                "queue_path": str(result.plan.queue_path),
                "pending_path": str(result.plan.pending_path),
                "pending_movement": result.pending_movement,
                "issue_number": result.plan.record.issue_number,
                "prompt_kind": result.plan.record.prompt_kind,
                "recipient_role": result.plan.record.recipient_role,
                "target_session_id": result.plan.record.target_session_id,
                "source_target_session_id": result.plan.record.target_session_id,
                "dispatch_target_session_id": result.router_session_id,
                "router_target_session_id": result.router_session_id,
                "session_id": result.session_id,
                "router_session_id": result.router_session_id,
                "session_visibility": result.plan.session_visibility,
                "command": list(result.plan.command[:-1]) + ["<prompt>"],
                "sent": result.sent,
                "moved_to_pending": result.moved_to_pending,
                "dry_run": result.dry_run,
                "skipped": result.skipped,
                "skip_reason": result.skip_reason,
                "defer_reason": (
                    result.skip_reason
                    if result.skip_reason in SESSION_DEFER_REASONS
                    else None
                ),
                "error": result.error,
                "status": result.status,
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


def _prompt_kind_from_fields(fields: Dict[str, str]) -> str:
    prompt_kind = fields.get("prompt_kind", "").strip()
    if prompt_kind:
        return prompt_kind
    recipient_role = fields.get("recipient_role", "").strip()
    if recipient_role == "router":
        return "session_router"
    return "worker"


def _record_payload(record: QueueRecord) -> Dict[str, object]:
    payload: Dict[str, object] = asdict(record)
    payload["recipient_role"] = record.recipient_role
    return payload


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


def _dispatch_failure_message(result: CommandResult, record: QueueRecord) -> str:
    message = result.stderr.strip() or result.stdout.strip() or "failed to dispatch prompt"
    if record.recipient_role != "router" and _looks_like_interactive_permission_block(message):
        return (
            f"{message}\n"
            "Non-visible subagent could not request permission directly. "
            "Open or resume the Session_router and grant the required login, "
            "approval, permission, or TTY-gated action there."
        )
    return message


def _looks_like_interactive_permission_block(message: str) -> bool:
    lowered = message.lower()
    needles = (
        "stdout is not a terminal",
        "stdin is not a terminal",
        "not a terminal",
        "authentication",
        "login",
        "permission",
        "approval",
        "authorize",
        "interactive",
    )
    return any(needle in lowered for needle in needles)


def _run_resume_session(
    runner: Any,
    session_id: str,
    prompt: str,
    *,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    visible: bool = True,
) -> CommandResult:
    if hasattr(runner, "resume_session"):
        return runner.resume_session(session_id, prompt)
    if runner is _default_runner and visible:
        return launch_visible_codex_session(
            prompt,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
            role=f"resume_{session_id}",
            session_id=session_id,
        )
    args = (
        str(codex_bin),
        "resume",
        "--cd",
        str(repo_dir),
        "--include-non-interactive",
        session_id,
        prompt,
    )
    return _call_runner(runner, args, None)


def _run_start_session(
    runner: Any,
    prompt: str,
    *,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
) -> CommandResult:
    if hasattr(runner, "start_session"):
        return runner.start_session(prompt)
    if runner is _default_runner:
        return launch_visible_codex_session(
            prompt,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
            role="session_router_bootstrap",
            marker="SESSION_ROUTER_BOOTSTRAP_V1_INPUT",
        )
    return _call_runner(runner, (str(codex_bin), prompt), None)


def _run_session_router(
    runner: Any,
    prompt: str,
    *,
    router_session_id: Optional[str],
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
) -> CommandResult:
    if hasattr(runner, "run_session_router"):
        return runner.run_session_router(prompt, router_session_id=router_session_id)
    if router_session_id:
        return _run_resume_session(
            runner,
            router_session_id,
            prompt,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
        )
    if hasattr(runner, "start_session"):
        return runner.start_session(prompt)
    return _run_start_session(
        runner,
        prompt,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
    )


def bootstrap_session_router(
    *,
    assignment_state_path: str | Path = DEFAULT_ASSIGNMENT_STATE_PATH,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    runner: Runner = _default_runner,
    template_path: str | Path = DEFAULT_SESSION_ROUTER_BOOTSTRAP_PROMPT,
) -> str:
    state = _read_assignment_state(assignment_state_path)
    existing_session_id = state.get("router_session_id")
    if existing_session_id:
        return str(existing_session_id)

    prompt = build_session_router_bootstrap_prompt(
        repo_dir=repo_dir,
        template_path=template_path,
    )
    result = _run_start_session(
        runner,
        prompt,
        repo_dir=repo_dir,
        codex_bin=codex_bin,
    )
    if not _result_ok(result):
        raise DispatchError(
            _result_text(result, "stderr").strip()
            or _result_text(result, "stdout").strip()
            or "failed to start Session_router bootstrap session"
        )
    session_id = parse_bootstrap_session_id(result)

    state.setdefault("schema_version", 1)
    state.setdefault("assignments", [])
    state.setdefault("next_sub_artifact_number", 1)
    state["router_session_id"] = session_id
    _write_assignment_state(assignment_state_path, state)
    return session_id


def update_assignment_state(
    path: str | Path,
    record: QueueRecord,
    *,
    session_id: str,
) -> Path:
    payload = _read_assignment_state(path)
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
    return _write_assignment_state(path, payload)


def _default_assignment_state() -> Dict[str, object]:
    return {
        "schema_version": 1,
        "router_session_id": None,
        "next_sub_artifact_number": 1,
        "assignments": [],
    }


def _read_assignment_state(path: str | Path) -> Dict[str, object]:
    target = Path(path)
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    return _default_assignment_state()


def _write_assignment_state(path: str | Path, payload: Dict[str, object]) -> Path:
    target = Path(path)
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
