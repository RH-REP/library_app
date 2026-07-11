"""Local demo for router, worker, subagent, and permission routing flow."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from .comments import append_marker_footer
from .dispatch import (
    CommandResult,
    bootstrap_session_router,
    dispatch_queue,
    dispatch_queue_file,
    dispatch_results_to_dict,
    write_queue_record,
)
from .github_client import read_issue_snapshots
from .models import QueueRecord
from .queueing import build_queue_records, write_queue_files


CORE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CORE_DIR.parent
DEFAULT_DEMO_FIXTURE_DIR = CORE_DIR / "fixtures" / "agent_flow_demo"
DEFAULT_DEMO_QUEUE_PATH = DEFAULT_DEMO_FIXTURE_DIR / "queue" / "router_demo.md"
DEFAULT_REAL_CODEX_FIXTURE_PATH = (
    DEFAULT_DEMO_FIXTURE_DIR / "real_codex_permission_issue.json"
)
DEFAULT_REAL_CODEX_WORK_DIR = CORE_DIR / "dry_run_output" / "real_codex_demo"

DEMO_ROUTER_SESSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DEMO_WORKER_A_SESSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
DEMO_SUBAGENT_A1_SESSION_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
DEMO_SUBAGENT_A2_SESSION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

_DISPATCH_INPUT_RE = re.compile(
    r"DISPATCH_V1_INPUT\s*```json\s*(?P<payload>.*?)\s*```",
    re.DOTALL,
)


@dataclass
class DemoTranscript:
    events: List[Dict[str, object]] = field(default_factory=list)

    def add(self, event: str, **fields: object) -> None:
        entry: Dict[str, object] = {"event": event}
        entry.update(fields)
        self.events.append(entry)


class AgentFlowDemoRunner:
    """Fake Codex runner that simulates the full router-led agent hierarchy."""

    def __init__(
        self,
        *,
        work_dir: Union[str, Path],
        permission_mode: str = "grant",
        transcript: Optional[DemoTranscript] = None,
        assignment_state_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.work_dir = Path(work_dir)
        self.permission_mode = permission_mode
        self.transcript = transcript or DemoTranscript()
        self.assignment_state_path = (
            Path(assignment_state_path)
            if assignment_state_path is not None
            else self.work_dir / "assignment_state.json"
        )
        self.resume_calls: List[Dict[str, object]] = []
        self.final_comment = ""
        self.demo_software_path: Optional[Path] = None
        self.verification_passed = False

    def resume_session(self, session_id: str, prompt: str) -> CommandResult:
        payload = _extract_dispatch_payload(prompt)
        recipient_role = str(payload.get("recipient_role") or "")
        session_visibility = str(payload.get("target_session_visibility") or "unknown")
        self.resume_calls.append(
            {
                "session_id": session_id,
                "recipient_role": recipient_role,
                "session_visibility": session_visibility,
            }
        )
        self.transcript.add(
            "dispatcher_prompt_sent",
            from_agent="dispatcher",
            to_session_id=session_id,
            recipient_role=recipient_role,
            session_visibility=session_visibility,
        )

        if recipient_role == "router":
            self._simulate_router(payload)
            stdout = f"{DEMO_WORKER_A_SESSION_ID}\n"
        elif recipient_role == "worker":
            self._simulate_worker(payload)
            stdout = ""
        else:
            return CommandResult(
                ok=False,
                args=("agent-flow-demo", "resume", session_id),
                stderr=f"unsupported recipient_role: {recipient_role}",
                returncode=64,
            )

        return CommandResult(
            ok=True,
            args=("agent-flow-demo", "resume", session_id),
            stdout=stdout,
            stderr="",
            returncode=0,
        )

    def _simulate_router(self, payload: Dict[str, object]) -> None:
        self.transcript.add(
            "router_visible_gateway_ready",
            agent="Session_router",
            session_id=DEMO_ROUTER_SESSION_ID,
            session_visibility="visible",
        )
        sub_artifact_path = (
            str(payload.get("sub_artifact_path") or "").strip()
            or "sub_artifact/001_agent_flow_demo"
        )
        self._write_assignment_state(payload, sub_artifact_path)
        self.transcript.add(
            "assignment_state_updated",
            agent="Session_router",
            issue_number=payload.get("issue_number"),
            worker_session_id=DEMO_WORKER_A_SESSION_ID,
            sub_artifact_path=sub_artifact_path,
        )
        self.transcript.add(
            "worker_handoff_once",
            from_agent="Session_router",
            to_agent="worker_A",
            to_session_id=DEMO_WORKER_A_SESSION_ID,
            session_visibility="non_visible",
        )
        worker_payload = dict(payload)
        worker_payload["recipient_role"] = "worker"
        worker_payload["target_session_id"] = DEMO_WORKER_A_SESSION_ID
        worker_payload["target_session_visibility"] = "non_visible"
        self._simulate_worker(worker_payload)

    def _simulate_worker(self, payload: Dict[str, object]) -> None:
        self.transcript.add(
            "worker_received",
            agent="worker_A",
            session_id=DEMO_WORKER_A_SESSION_ID,
            session_visibility="non_visible",
        )
        self.transcript.add(
            "subagent_started",
            parent_agent="worker_A",
            agent="subagent_A1",
            session_id=DEMO_SUBAGENT_A1_SESSION_ID,
            role="implement_minimal_demo_software",
            session_visibility="non_visible",
        )
        if not self._grant_permission_through_router(payload):
            self._finish_comment(payload, status="authentication_blocked")
            return

        self.demo_software_path = self._write_demo_software()
        self.transcript.add(
            "subagent_completed",
            agent="subagent_A1",
            produced_path=str(self.demo_software_path),
        )
        self.transcript.add(
            "subagent_started",
            parent_agent="worker_A",
            agent="subagent_A2",
            session_id=DEMO_SUBAGENT_A2_SESSION_ID,
            role="verify_minimal_demo_software",
            session_visibility="non_visible",
        )
        self.verification_passed = self._verify_demo_software(self.demo_software_path)
        self.transcript.add(
            "subagent_completed",
            agent="subagent_A2",
            verification_passed=self.verification_passed,
        )
        self._finish_comment(
            payload,
            status="done" if self.verification_passed else "authentication_blocked",
        )

    def _grant_permission_through_router(self, payload: Dict[str, object]) -> bool:
        self.transcript.add(
            "permission_requested",
            from_agent="subagent_A1",
            to_agent="Session_router",
            permission="write_demo_software_file",
            reason="non-visible subagent cannot ask the user directly",
        )
        granted = self.permission_mode == "grant"
        self.transcript.add(
            "permission_decision",
            agent="Session_router",
            permission="write_demo_software_file",
            decision="granted" if granted else "denied",
            issue_number=payload.get("issue_number"),
        )
        return granted

    def _write_assignment_state(
        self,
        payload: Dict[str, object],
        sub_artifact_path: str,
    ) -> None:
        self.assignment_state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "schema_version": 1,
            "router_session_id": DEMO_ROUTER_SESSION_ID,
            "next_sub_artifact_number": 2,
            "assignments": [
                {
                    "issue_number": payload.get("issue_number"),
                    "session_id": DEMO_WORKER_A_SESSION_ID,
                    "sub_artifact_path": sub_artifact_path,
                    "status": "active",
                    "demo": True,
                }
            ],
        }
        self.assignment_state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_demo_software(self) -> Path:
        target = self.work_dir / "demo_software" / "mini_counter.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "\n".join(
                [
                    '"""Tiny demo software created by the ArtifactForge agent-flow demo."""',
                    "",
                    "",
                    "class Counter:",
                    "    def __init__(self):",
                    "        self.value = 0",
                    "",
                    "    def increment(self):",
                    "        self.value += 1",
                    "        return self.value",
                    "",
                    "",
                    "def demo():",
                    "    counter = Counter()",
                    "    return [counter.increment(), counter.increment()]",
                    "",
                    "",
                    "if __name__ == \"__main__\":",
                    "    print(demo())",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return target

    def _verify_demo_software(self, path: Path) -> bool:
        namespace: Dict[str, object] = {}
        source = path.read_text(encoding="utf-8")
        compiled = compile(source, str(path), "exec")
        exec(compiled, namespace)
        demo = namespace.get("demo")
        return callable(demo) and demo() == [1, 2]

    def _finish_comment(self, payload: Dict[str, object], *, status: str) -> None:
        trigger_fingerprint = str(payload.get("trigger_fingerprint") or "")
        issue_number = payload.get("issue_number")
        lines = [
            "Agent flow demo result",
            "",
            f"- worker: worker_A ({DEMO_WORKER_A_SESSION_ID})",
            f"- permission_through_router: {self.permission_mode}",
            f"- verification_passed: {self.verification_passed}",
        ]
        if self.demo_software_path is not None:
            lines.append(f"- demo_software: {self.demo_software_path}")
        if status == "authentication_blocked":
            lines.append("- blocked: Session_router permission was not granted")
        self.final_comment = append_marker_footer(
            "\n".join(lines),
            session_id=DEMO_WORKER_A_SESSION_ID,
            trigger_fingerprint=trigger_fingerprint,
            status=status,
        )
        self.transcript.add(
            "github_comment_planned",
            agent="worker_A",
            issue_number=issue_number,
            marker_status=status,
            posted=False,
            comment=self.final_comment,
        )


def demo_queue_record() -> QueueRecord:
    return QueueRecord(
        issue_number=1,
        issue_url="https://github.example.test/acme/demo/issues/1",
        issue_title="Agent flow demo software",
        event_type="thread_update",
        trigger_fingerprint=(
            "issue-1-thread-body-comment-demo-sha256-"
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        target_session_id=DEMO_ROUTER_SESSION_ID,
        prompt_kind="session_router",
        body=(
            "## Issue body\n"
            "- author: demo-user\n"
            "- created_at: 2026-07-11T00:00:00Z\n\n"
            "ArtifactForge の agent hierarchy を確認するため、最小の demo software を作り、\n"
            "worker_A が subagent_A1 に実装、subagent_A2 に検証を依頼してください。\n"
            "subagent_A1 がファイル作成権限を必要とする場合は、Session_router 経由で確認してください。\n"
        ),
        source_id="body..comment-demo",
        sub_artifact_path="sub_artifact/001_agent_flow_demo_software",
        previous_thread_id=None,
        reassign_required=False,
    )


def write_default_demo_queue(path: Union[str, Path] = DEFAULT_DEMO_QUEUE_PATH) -> Path:
    target = Path(path)
    write_queue_record(target, demo_queue_record())
    return target


def run_agent_flow_demo(
    *,
    queue_file: Optional[Union[str, Path]] = None,
    work_dir: Optional[Union[str, Path]] = None,
    permission_mode: str = "grant",
) -> Dict[str, object]:
    if permission_mode not in {"grant", "deny"}:
        raise ValueError("permission_mode must be 'grant' or 'deny'")

    resolved_work_dir = Path(work_dir) if work_dir is not None else Path(
        tempfile.mkdtemp(prefix="artifactforge-agent-flow-demo-")
    )
    queue_dir = resolved_work_dir / "queue"
    pending_dir = resolved_work_dir / "pending"
    archive_dir = resolved_work_dir / "archive"
    assignment_state_path = resolved_work_dir / "assignment_state.json"
    queue_dir.mkdir(parents=True, exist_ok=True)
    pending_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    source_queue = Path(queue_file) if queue_file is not None else DEFAULT_DEMO_QUEUE_PATH
    if not source_queue.exists():
        source_queue = write_default_demo_queue(source_queue)
    staged_queue = queue_dir / source_queue.name
    staged_queue.write_text(source_queue.read_text(encoding="utf-8"), encoding="utf-8")

    transcript = DemoTranscript()
    runner = AgentFlowDemoRunner(
        work_dir=resolved_work_dir,
        permission_mode=permission_mode,
        transcript=transcript,
        assignment_state_path=assignment_state_path,
    )
    result = dispatch_queue_file(
        staged_queue,
        pending_dir=pending_dir,
        archive_dir=archive_dir,
        repo_dir=REPO_ROOT,
        runner=runner,
        assignment_state_path=assignment_state_path,
    )
    transcript_path = resolved_work_dir / "transcript.json"
    summary = {
        "schema_version": 1,
        "mode": "agent-flow-demo",
        "sample_queue": str(source_queue),
        "work_dir": str(resolved_work_dir),
        "effects": {
            "real_codex": "not_called",
            "github_api": "not_called",
            "queue_file": "copied_to_demo_work_dir",
            "pending_file": "moved_when_dispatch_succeeds",
            "permission": "simulated_router_grant"
            if permission_mode == "grant"
            else "simulated_router_deny",
        },
        "sessions": {
            "router": {
                "session_id": DEMO_ROUTER_SESSION_ID,
                "visibility": "visible",
            },
            "worker_A": {
                "session_id": DEMO_WORKER_A_SESSION_ID,
                "visibility": "non_visible",
            },
            "subagent_A1": {
                "session_id": DEMO_SUBAGENT_A1_SESSION_ID,
                "visibility": "non_visible",
            },
            "subagent_A2": {
                "session_id": DEMO_SUBAGENT_A2_SESSION_ID,
                "visibility": "non_visible",
            },
        },
        "dispatch": dispatch_results_to_dict((result,)),
        "resume_call_count": len(runner.resume_calls),
        "router_dispatch_count": sum(
            1
            for call in runner.resume_calls
            if call.get("recipient_role") == "router"
        ),
        "worker_dispatch_count": sum(
            1
            for call in runner.resume_calls
            if call.get("recipient_role") == "worker"
        ),
        "demo_software_path": str(runner.demo_software_path)
        if runner.demo_software_path is not None
        else None,
        "verification_passed": runner.verification_passed,
        "final_comment": runner.final_comment,
        "transcript": transcript.events,
        "transcript_path": str(transcript_path),
    }
    transcript_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def human_summary(summary: Dict[str, object]) -> str:
    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), dict) else {}
    transcript = summary.get("transcript") if isinstance(summary.get("transcript"), list) else []
    lines = [
        "ArtifactForge agent flow demo",
        f"sample_queue: {summary.get('sample_queue')}",
        f"work_dir: {summary.get('work_dir')}",
        "",
        "sessions",
        "-------",
    ]
    if isinstance(sessions, dict):
        for name in ("router", "worker_A", "subagent_A1", "subagent_A2"):
            value = sessions.get(name)
            if isinstance(value, dict):
                lines.append(
                    f"- {name}: {value.get('session_id')} ({value.get('visibility')})"
                )
    lines.extend(["", "transcript", "-------"])
    for index, event in enumerate(transcript, start=1):
        if not isinstance(event, dict):
            continue
        lines.append(f"{index}. {_event_line(event)}")
    lines.extend(
        [
            "",
            "result",
            "-------",
            f"resume_call_count: {summary.get('resume_call_count')}",
            f"router_dispatch_count: {summary.get('router_dispatch_count')}",
            f"worker_dispatch_count: {summary.get('worker_dispatch_count')}",
            f"permission: {_permission_decision(transcript)}",
            f"verification_passed: {summary.get('verification_passed')}",
            f"demo_software_path: {summary.get('demo_software_path')}",
            f"transcript_path: {summary.get('transcript_path')}",
        ]
    )
    return "\n".join(lines)


def run_real_codex_demo(
    *,
    fixture_path: Union[str, Path] = DEFAULT_REAL_CODEX_FIXTURE_PATH,
    work_dir: Union[str, Path] = DEFAULT_REAL_CODEX_WORK_DIR,
    router_session_id: Optional[str] = None,
    bootstrap_router: bool = False,
    dispatch: bool = False,
    dry_run_dispatch: bool = False,
    overwrite_queue: bool = False,
    codex_bin: Union[str, Path] = "codex",
) -> Dict[str, object]:
    paths = _real_codex_demo_paths(work_dir)
    for key in ("queue_dir", "pending_dir", "archive_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)

    assignment_state = _read_demo_assignment_state(paths["assignment_state"])
    resolved_router_session_id = _resolve_real_codex_router_session(
        assignment_state,
        paths["assignment_state"],
        router_session_id=router_session_id,
        bootstrap_router=bootstrap_router,
        codex_bin=codex_bin,
    )
    if resolved_router_session_id is None:
        return _real_codex_summary(
            fixture_path=fixture_path,
            work_dir=paths["work_dir"],
            assignment_state_path=paths["assignment_state"],
            router_session_id=None,
            queue_results=(),
            dispatch_results=(),
            status="router_session_required",
            effects={
                "router": "not_started",
                "queue_files": "not_written",
                "codex_dispatch": "not_started",
            },
        )

    assignment_state["router_session_id"] = resolved_router_session_id
    _write_demo_assignment_state(paths["assignment_state"], assignment_state)

    issues = read_issue_snapshots(fixture_path)
    records = build_queue_records(
        issues,
        assignment_state,
        pending_dir=paths["pending_dir"],
        archive_dir=paths["archive_dir"],
    )
    queue_results = write_queue_files(
        records,
        queue_dir=paths["queue_dir"],
        pending_dir=paths["pending_dir"],
        overwrite=overwrite_queue,
    )

    dispatch_results = ()
    if dispatch:
        dispatch_results = dispatch_queue(
            paths["queue_dir"],
            pending_dir=paths["pending_dir"],
            archive_dir=paths["archive_dir"],
            repo_dir=REPO_ROOT,
            codex_bin=codex_bin,
            dry_run=dry_run_dispatch,
            limit=1,
        )

    return _real_codex_summary(
        fixture_path=fixture_path,
        work_dir=paths["work_dir"],
        assignment_state_path=paths["assignment_state"],
        router_session_id=resolved_router_session_id,
        queue_results=queue_results,
        dispatch_results=dispatch_results,
        status="dispatched" if dispatch else "prepared",
        effects={
            "router": "bootstrapped_or_reused" if bootstrap_router else "reused_or_provided",
            "queue_files": "written_or_reused",
            "codex_dispatch": (
                "dry_run_not_sent"
                if dispatch and dry_run_dispatch
                else "sent_when_successful"
                if dispatch
                else "not_started"
            ),
        },
    )


def real_codex_human_summary(summary: Dict[str, object]) -> str:
    lines = [
        "ArtifactForge real Codex agent-flow demo",
        f"status: {summary.get('status')}",
        f"fixture: {summary.get('fixture')}",
        f"work_dir: {summary.get('work_dir')}",
        f"router_session_id: {summary.get('router_session_id') or '(required)'}",
        "",
        "queue",
        "-------",
    ]
    queue = summary.get("queue")
    queue_items = queue.get("items") if isinstance(queue, dict) else []
    if queue_items:
        for index, item in enumerate(queue_items, start=1):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"{index}. {item.get('action')} issue #{item.get('issue_number')} "
                f"-> {item.get('recipient_role')} {item.get('target_session_id')} "
                f"({item.get('path')})"
            )
    else:
        lines.append("(none)")

    dispatch = summary.get("dispatch")
    dispatch_items = dispatch.get("items") if isinstance(dispatch, dict) else []
    lines.extend(["", "dispatch", "-------"])
    if dispatch_items:
        for index, item in enumerate(dispatch_items, start=1):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"{index}. {item.get('status') or item.get('recipient_role')} "
                f"sent={item.get('sent')} dry_run={item.get('dry_run')} "
                f"visibility={item.get('session_visibility')}"
            )
    else:
        lines.append("(not started)")

    next_commands = summary.get("next_commands")
    lines.extend(["", "next", "-------"])
    if isinstance(next_commands, list) and next_commands:
        lines.extend(str(command) for command in next_commands)
    else:
        lines.append("(none)")
    return "\n".join(lines)


def _event_line(event: Dict[str, object]) -> str:
    name = str(event.get("event") or "")
    if name == "dispatcher_prompt_sent":
        return (
            "dispatcher -> "
            f"{event.get('recipient_role')} {event.get('to_session_id')} "
            f"({event.get('session_visibility')})"
        )
    if name == "worker_handoff_once":
        return (
            "Session_router -> worker_A handoff once "
            f"({event.get('session_visibility')})"
        )
    if name == "subagent_started":
        return (
            f"{event.get('parent_agent')} -> {event.get('agent')} "
            f"{event.get('role')} ({event.get('session_visibility')})"
        )
    if name == "permission_requested":
        return (
            f"{event.get('from_agent')} requested {event.get('permission')} "
            f"through {event.get('to_agent')}"
        )
    if name == "permission_decision":
        return f"Session_router permission decision: {event.get('decision')}"
    if name == "github_comment_planned":
        return f"worker_A planned issue comment marker={event.get('marker_status')}"
    if name == "subagent_completed":
        if "verification_passed" in event:
            return f"{event.get('agent')} completed verification={event.get('verification_passed')}"
        return f"{event.get('agent')} completed output={event.get('produced_path')}"
    if name == "assignment_state_updated":
        return (
            "Session_router updated assignment_state "
            f"worker={event.get('worker_session_id')} "
            f"path={event.get('sub_artifact_path')}"
        )
    if name == "router_visible_gateway_ready":
        return "Session_router is visible human permission gateway"
    return name


def _permission_decision(transcript: Sequence[object]) -> str:
    for event in transcript:
        if isinstance(event, dict) and event.get("event") == "permission_decision":
            return str(event.get("decision"))
    return "unknown"


def _extract_dispatch_payload(prompt: str) -> Dict[str, object]:
    match = _DISPATCH_INPUT_RE.search(prompt)
    if match is None:
        raise ValueError("dispatch prompt did not include DISPATCH_V1_INPUT JSON")
    payload = json.loads(match.group("payload"))
    if not isinstance(payload, dict):
        raise ValueError("DISPATCH_V1_INPUT must be a JSON object")
    return payload


def _real_codex_demo_paths(work_dir: Union[str, Path]) -> Dict[str, Path]:
    root = Path(work_dir)
    return {
        "work_dir": root,
        "queue_dir": root / "queue",
        "pending_dir": root / "pending",
        "archive_dir": root / "archive",
        "assignment_state": root / "assignment_state.json",
    }


def _resolve_real_codex_router_session(
    assignment_state: Dict[str, object],
    assignment_state_path: Path,
    *,
    router_session_id: Optional[str],
    bootstrap_router: bool,
    codex_bin: Union[str, Path],
) -> Optional[str]:
    if router_session_id:
        return router_session_id
    existing = str(assignment_state.get("router_session_id") or "").strip()
    if existing:
        return existing
    if bootstrap_router:
        return bootstrap_session_router(
            assignment_state_path=assignment_state_path,
            repo_dir=REPO_ROOT,
            codex_bin=codex_bin,
        )
    return None


def _read_demo_assignment_state(path: Path) -> Dict[str, object]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "router_session_id": None,
        "next_sub_artifact_number": 1,
        "assignments": [],
    }


def _write_demo_assignment_state(path: Path, payload: Dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _real_codex_summary(
    *,
    fixture_path: Union[str, Path],
    work_dir: Path,
    assignment_state_path: Path,
    router_session_id: Optional[str],
    queue_results: Sequence[Any],
    dispatch_results: Sequence[Any],
    status: str,
    effects: Dict[str, object],
) -> Dict[str, object]:
    summary_path = work_dir / "summary.json"
    summary = {
        "schema_version": 1,
        "mode": "real-codex-agent-flow-demo",
        "status": status,
        "fixture": str(fixture_path),
        "work_dir": str(work_dir),
        "summary_path": str(summary_path),
        "assignment_state": str(assignment_state_path),
        "router_session_id": router_session_id,
        "effects": effects,
        "queue": _queue_results_to_demo_dict(queue_results),
        "dispatch": dispatch_results_to_dict(dispatch_results),
        "next_commands": _real_codex_next_commands(
            work_dir=work_dir,
            fixture_path=fixture_path,
            router_session_id=router_session_id,
            status=status,
        ),
    }
    work_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _queue_results_to_demo_dict(results: Sequence[Any]) -> Dict[str, object]:
    return {
        "result_count": len(results),
        "written_count": sum(1 for result in results if getattr(result, "written", False)),
        "items": [
            {
                "action": result.plan.action,
                "reason": result.reason,
                "written": result.written,
                "path": str(result.plan.path),
                "issue_number": result.plan.record.issue_number,
                "event_type": result.plan.record.event_type,
                "recipient_role": result.plan.record.recipient_role,
                "target_session_id": result.plan.record.target_session_id,
                "trigger_fingerprint": result.plan.record.trigger_fingerprint,
            }
            for result in results
        ],
    }


def _real_codex_next_commands(
    *,
    work_dir: Path,
    fixture_path: Union[str, Path],
    router_session_id: Optional[str],
    status: str,
) -> List[str]:
    base = (
        "python3 -B .core_program/app/03_agent_flow_demo/run_real_codex_demo.py "
        f"--fixture {fixture_path} --work-dir {work_dir}"
    )
    if router_session_id is None:
        return [
            base + " --bootstrap-router",
            base + " --router-session-id SESSION_ID",
        ]
    if status == "prepared":
        return [base + " --dispatch"]
    return [
        f"tail -n +1 {work_dir / 'summary.json'}",
        f"ls {work_dir / 'pending'}",
    ]
