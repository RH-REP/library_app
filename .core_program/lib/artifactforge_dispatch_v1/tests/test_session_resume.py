from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[4]
RUN_SESSION_RESUME_PATH = (
    REPO_ROOT / ".core_program" / "app" / "02_dispatch_queue" / "run_session_resume.py"
)


def _load_run_session_resume_module(
    module_name: str = "artifactforge_run_session_resume",
):
    spec = importlib.util.spec_from_file_location(module_name, RUN_SESSION_RESUME_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load run_session_resume.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_session_resume = _load_run_session_resume_module()

from artifactforge_dispatch_v1.dispatch import CommandResult, write_queue_record  # noqa: E402
from artifactforge_dispatch_v1.models import QueueRecord  # noqa: E402
from artifactforge_dispatch_v1.session_resume import (  # noqa: E402
    plan_session_resume,
    resume_session,
    session_resume_plan_to_dict,
)


ROUTER_SESSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
WORKER_SESSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class FakeResumeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def resume_session(self, session_id: str, prompt: str) -> CommandResult:
        self.calls.append((session_id, prompt))
        return CommandResult(
            ok=True,
            args=("codex", "resume", "--include-non-interactive", session_id, prompt),
            stdout="",
            stderr="",
            returncode=0,
        )


def sample_record(
    *,
    issue_number: int = 7,
    prompt_kind: str = "worker",
    target_session_id: str = WORKER_SESSION_ID,
    trigger_fingerprint: str = "issue-7-thread-body-comment-sha256-abc123",
) -> QueueRecord:
    return QueueRecord(
        issue_number=issue_number,
        issue_url="https://github.com/example/project/issues/7",
        issue_title="first artifact",
        event_type="thread_update",
        trigger_fingerprint=trigger_fingerprint,
        target_session_id=target_session_id,
        prompt_kind=prompt_kind,
        body="## Issue body\n- source_id: body\n\nWhat should we build?",
        source_id="body",
        sub_artifact_path="sub_artifact/001_first_artifact",
    )


def write_assignment_state(path: Path, *, router_session_id: str = ROUTER_SESSION_ID) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "router_session_id": router_session_id,
                "next_sub_artifact_number": 1,
                "assignments": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_request_for_human_memo(path: Path, *, worker_session_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "日時: 2026-07-13 10:00",
                "Pending fingerprints: issue-7-thread-body-comment-sha256-abc123",
                f"Worker session ID: {worker_session_id}",
                "問い合わせ内容: human confirmation is needed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


class SessionResumePlanTest(unittest.TestCase):
    def test_plan_session_resume_prioritizes_router_for_request_memos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignment_state = root / ".core_program" / "assignment_state.json"
            pending_dir = root / ".core_program" / "pending"
            human_wating_dir = root / ".core_program" / "human_wating"
            request_dir = root / ".core_program" / "request_for_human"
            write_assignment_state(assignment_state)
            write_request_for_human_memo(
                request_dir / "issue_7_waiting.md",
                worker_session_id=WORKER_SESSION_ID,
            )
            write_queue_record(
                human_wating_dir / f"{WORKER_SESSION_ID}_issue-7-thread-body-comment-sha256-abc123.md",
                sample_record(),
            )

            plan = plan_session_resume(
                repo_dir=root,
                assignment_state_path=assignment_state,
                pending_dir=pending_dir,
                request_for_human_dir=request_dir,
                human_waiting_dir=human_wating_dir,
            )

        self.assertEqual(ROUTER_SESSION_ID, plan.session_id)
        self.assertEqual("router", plan.recipient_role)
        self.assertEqual("visible", plan.session_visibility)
        self.assertEqual("request_for_human", plan.source_kind)
        self.assertEqual(1, len(plan.request_for_human_memos))
        self.assertEqual(1, len(plan.human_waiting_records))
        self.assertIn(WORKER_SESSION_ID, plan.worker_session_ids)
        self.assertIn("ArtifactForge Session Resume Prompt v1", plan.prompt or "")
        self.assertIn("worker_session_id", plan.prompt or "")
        self.assertIn("human_wating", plan.prompt or "")
        self.assertIn(f'"target_session_id": "{ROUTER_SESSION_ID}"', plan.prompt or "")

        summary = session_resume_plan_to_dict(plan)
        self.assertEqual(ROUTER_SESSION_ID, summary["selected_session_id"])
        self.assertEqual("router", summary["recipient_role"])
        self.assertEqual(1, summary["request_for_human_count"])
        self.assertEqual(1, summary["human_waiting_count"])

    def test_plan_session_resume_selects_worker_pending_record_when_no_waiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignment_state = root / ".core_program" / "assignment_state.json"
            pending_dir = root / ".core_program" / "pending"
            write_assignment_state(assignment_state)
            pending_path = pending_dir / "worker_pending.md"
            write_queue_record(
                pending_path,
                sample_record(
                    prompt_kind="worker",
                    target_session_id=WORKER_SESSION_ID,
                ),
            )

            plan = plan_session_resume(
                repo_dir=root,
                assignment_state_path=assignment_state,
                pending_dir=pending_dir,
                request_for_human_dir=root / ".core_program" / "request_for_human",
                human_waiting_dir=root / ".core_program" / "human_wating",
            )

        self.assertEqual(WORKER_SESSION_ID, plan.session_id)
        self.assertEqual("worker", plan.recipient_role)
        self.assertEqual("non_visible", plan.session_visibility)
        self.assertEqual("pending", plan.source_kind)
        self.assertEqual(str(pending_path), plan.selected_pending_path)
        self.assertIn("ArtifactForge Dispatch Prompt v1", plan.prompt or "")
        self.assertIn('"recipient_role": "worker"', plan.prompt or "")
        self.assertIn(
            "If your current session ID is not target_session_id",
            plan.prompt or "",
        )

    def test_resume_session_calls_runner_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignment_state = root / ".core_program" / "assignment_state.json"
            pending_dir = root / ".core_program" / "pending"
            write_assignment_state(assignment_state)
            pending_path = pending_dir / "worker_pending.md"
            write_queue_record(
                pending_path,
                sample_record(
                    prompt_kind="worker",
                    target_session_id=WORKER_SESSION_ID,
                ),
            )
            plan = plan_session_resume(
                repo_dir=root,
                assignment_state_path=assignment_state,
                pending_dir=pending_dir,
                request_for_human_dir=root / ".core_program" / "request_for_human",
                human_waiting_dir=root / ".core_program" / "human_wating",
            )
            runner = FakeResumeRunner()

            result = resume_session(plan, repo_dir=root, runner=runner)

        self.assertTrue(result.ok)
        self.assertEqual(1, len(runner.calls))
        self.assertEqual(WORKER_SESSION_ID, runner.calls[0][0])
        self.assertIn("ArtifactForge Dispatch Prompt v1", runner.calls[0][1])


class RunSessionResumeCliTest(unittest.TestCase):
    def test_dry_run_compact_reports_router_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ) as stdout:
            root = Path(tmp)
            assignment_state = root / ".core_program" / "assignment_state.json"
            pending_dir = root / ".core_program" / "pending"
            human_wating_dir = root / ".core_program" / "human_wating"
            request_dir = root / ".core_program" / "request_for_human"
            write_assignment_state(assignment_state)
            write_request_for_human_memo(
                request_dir / "issue_7_waiting.md",
                worker_session_id=WORKER_SESSION_ID,
            )
            write_queue_record(
                human_wating_dir / f"{WORKER_SESSION_ID}_issue-7-thread-body-comment-sha256-abc123.md",
                sample_record(),
            )

            exit_code = run_session_resume.main(
                [
                    "--dry-run",
                    "--compact",
                    "--repo-dir",
                    str(root),
                    "--pending-dir",
                    str(pending_dir),
                    "--human-wating-dir",
                    str(human_wating_dir),
                    "--request-for-human-dir",
                    str(request_dir),
                    "--pending-state",
                    str(root / ".core_program" / "pending_state.json"),
                ]
            )
            summary = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual(ROUTER_SESSION_ID, summary["selected_session_id"])
        self.assertEqual("router", summary["recipient_role"])
        self.assertEqual("request_for_human", summary["source_kind"])
        self.assertEqual("not_started", summary["effects"]["codex_sessions"])
        self.assertEqual(1, summary["request_for_human_count"])
        self.assertEqual(1, summary["human_waiting_count"])
        self.assertIn("ArtifactForge Session Resume Prompt v1", summary["prompt_preview"])


if __name__ == "__main__":
    unittest.main()

