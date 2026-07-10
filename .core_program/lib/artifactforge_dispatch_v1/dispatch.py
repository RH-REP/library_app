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
from .queueing import build_queue_markdown, collect_existing_fingerprints, safe_filename_part


CORE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CORE_DIR.parent
DEFAULT_QUEUE_DIR = CORE_DIR / "queue"
DEFAULT_PENDING_DIR = CORE_DIR / "pending"
DEFAULT_ARCHIVE_DIR = CORE_DIR / "archive"
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
FINGERPRINT_START_RE = re.compile(r"_(?=issue-\d+-(?:body|comment)-)")
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


def build_dispatch_prompt(
    record: QueueRecord,
    *,
    repo_dir: str | Path = REPO_ROOT,
    template_path: str | Path = DEFAULT_DISPATCH_PROMPT,
) -> str:
    payload: Dict[str, object] = {
        "schema_version": 1,
        "repository": str(repo_dir),
        "recipient_role": record.recipient_role,
        "target_session_id": record.target_session_id,
        "issue_number": record.issue_number,
        "issue_url": record.issue_url,
        "trigger_fingerprint": record.trigger_fingerprint,
        "target_events": [_record_payload(record)],
        "sub_artifact_path": record.sub_artifact_path,
        "reassign_required": record.reassign_required,
        "previous_thread_id": record.previous_thread_id,
        "safety_contract": {
            "current_session_must_match_target_session_id": True,
            "wrong_session_must_not_perform_work": True,
        },
    }
    if record.recipient_role == "router":
        payload["routing_contract"] = {
            "prefer_existing_worker_check": True,
            "avoid_previous_thread_id": bool(record.previous_thread_id),
            "start_new_worker_only_if_no_existing_worker_accepts": True,
            "handoff_worker_prompt_once": True,
            "output_worker_session_id_one_line": True,
        }
    else:
        payload["worker_contract"] = {
            "process_issue_event": True,
            "post_github_comment": True,
            "commit_and_push_if_files_changed": True,
        }
        payload["github_comment_contract"] = {
            "visible_comment_required": True,
            "post_comment_required": True,
            "marker_required": True,
            "marker_statuses": [
                "done",
                "reassign_required",
                "authentication_blocked",
            ],
        }
        payload["git_contract"] = {
            "commit_required_when_files_change": True,
            "push_required": True,
            "push_remote": "origin",
            "do_not_push_remote": "upstream",
        }

    return (
        "ArtifactForge Dispatch Prompt v1\n\n"
        "You are receiving this prompt because your session ID is the dispatch target.\n\n"
        "Expected recipient:\n"
        f"- recipient_role: {record.recipient_role}\n"
        f"- target_session_id: {record.target_session_id}\n\n"
        "If your current session ID is not target_session_id, do not perform the work.\n"
        "If recipient_role is worker, process the issue event as the assigned worker.\n"
        "If recipient_role is router, route the issue event and hand it off to the correct worker.\n\n"
        f"{_read_prompt(template_path)}\n\n"
        "DISPATCH_V1_INPUT\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def build_session_router_prompt(
    record: QueueRecord,
    *,
    repo_dir: str | Path = REPO_ROOT,
    template_path: str | Path = DEFAULT_DISPATCH_PROMPT,
) -> str:
    return build_dispatch_prompt(
        replace(record, prompt_kind="session_router"),
        repo_dir=repo_dir,
        template_path=template_path,
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


def plan_dispatch(
    queue_path: str | Path,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
) -> DispatchPlan:
    path = Path(queue_path)
    record = parse_queue_file(path)
    prompt = build_dispatch_prompt(record, repo_dir=repo_dir)
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
    archive_dir: str | Path = DEFAULT_ARCHIVE_DIR,
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
    skip_reason = duplicate_dispatch_reason(
        plan.record,
        pending_dir=pending_dir,
        archive_dir=archive_dir,
    )
    if skip_reason:
        return DispatchResult(
            plan=plan,
            sent=False,
            moved_to_pending=False,
            session_id=plan.record.target_session_id,
            skipped=True,
            skip_reason=skip_reason,
            dry_run=dry_run,
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
        result = _run_resume_session(
            runner,
            plan.record.target_session_id,
            plan.prompt,
            repo_dir=repo_dir,
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
            plan.record.target_session_id if plan.record.recipient_role == "router" else None
        ),
    )


def dispatch_queue(
    queue_dir: str | Path = DEFAULT_QUEUE_DIR,
    *,
    pending_dir: str | Path = DEFAULT_PENDING_DIR,
    archive_dir: str | Path = DEFAULT_ARCHIVE_DIR,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
    dry_run: bool = False,
    move_to_pending: bool = True,
    runner: Runner = _default_runner,
    assignment_state_path: Optional[Union[str, Path]] = None,
    limit: Optional[int] = None,
) -> Tuple[DispatchResult, ...]:
    paths = iter_queue_paths(queue_dir)
    if limit is not None:
        paths = paths[: max(0, limit)]
    return tuple(
        dispatch_queue_file(
            path,
            pending_dir=pending_dir,
            archive_dir=archive_dir,
            repo_dir=repo_dir,
            codex_bin=codex_bin,
            dry_run=dry_run,
            move_to_pending=move_to_pending,
            runner=runner,
            assignment_state_path=assignment_state_path,
        )
        for path in paths
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
        "skipped_count": sum(1 for result in result_tuple if result.skipped),
        "items": [
            {
                "queue_path": str(result.plan.queue_path),
                "pending_path": str(result.plan.pending_path),
                "issue_number": result.plan.record.issue_number,
                "prompt_kind": result.plan.record.prompt_kind,
                "recipient_role": result.plan.record.recipient_role,
                "target_session_id": result.plan.record.target_session_id,
                "session_id": result.session_id,
                "router_session_id": result.router_session_id,
                "command": list(result.plan.command[:-1]) + ["<prompt>"],
                "sent": result.sent,
                "moved_to_pending": result.moved_to_pending,
                "dry_run": result.dry_run,
                "skipped": result.skipped,
                "skip_reason": result.skip_reason,
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


def _run_resume_session(
    runner: Any,
    session_id: str,
    prompt: str,
    *,
    repo_dir: str | Path = REPO_ROOT,
    codex_bin: str | Path = DEFAULT_CODEX_BIN,
) -> CommandResult:
    if hasattr(runner, "resume_session"):
        return runner.resume_session(session_id, prompt)
    if runner is _default_runner:
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
