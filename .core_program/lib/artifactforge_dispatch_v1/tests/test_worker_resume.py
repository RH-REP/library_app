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
RUN_WORKER_RESUME_PATH = (
    REPO_ROOT / ".core_program" / "app" / "02_dispatch_queue" / "run_worker_resume.py"
)


def _load_run_worker_resume_module(module_name: str = "artifactforge_run_worker_resume"):
    spec = importlib.util.spec_from_file_location(module_name, RUN_WORKER_RESUME_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load run_worker_resume.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_worker_resume = _load_run_worker_resume_module()

from artifactforge_dispatch_v1.dispatch import CommandResult  # noqa: E402
from artifactforge_dispatch_v1.worker_resume import (  # noqa: E402
    plan_worker_resume_by_index,
    worker_resume_plan_to_dict,
)


ROUTER_SESSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
WORKER_A_SESSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
WORKER_B_SESSION_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def _assignment_state(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "router_session_id": ROUTER_SESSION_ID,
                "next_sub_artifact_number": 3,
                "assignments": [
                    {
                        "issue_number": 1,
                        "session_id": WORKER_A_SESSION_ID,
                        "sub_artifact_path": "sub_artifact/001_alpha",
                        "status": "active",
                    },
                    {
                        "issue_number": 2,
                        "session_id": WORKER_B_SESSION_ID,
                        "sub_artifact_path": "sub_artifact/002_beta",
                        "status": "active",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


class WorkerResumeTests(unittest.TestCase):
    def test_plan_worker_resume_by_index_builds_prompt_and_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = root / ".core_program"
            core.mkdir(parents=True, exist_ok=True)
            assignment_state = core / "assignment_state.json"
            _assignment_state(assignment_state)

            plan = plan_worker_resume_by_index(
                index=2,
                repo_dir=root,
                assignment_state_path=assignment_state,
                pending_dir=core / "pending",
                request_for_human_dir=core / "request_for_human",
                human_waiting_dir=core / "human_wating",
            )

        self.assertEqual(2, plan.selected_index)
        self.assertEqual(WORKER_B_SESSION_ID, plan.selected_session_id)
        self.assertEqual(WORKER_B_SESSION_ID, plan.session_plan.session_id)
        self.assertEqual("worker", plan.session_plan.recipient_role)
        self.assertEqual("non_visible", plan.session_plan.session_visibility)
        self.assertIn("ArtifactForge Worker Resume Prompt v1", plan.session_plan.prompt or "")
        self.assertIn(f'"selected_worker_index": 2', plan.session_plan.prompt or "")
        self.assertIn(f'"target_session_id": "{WORKER_B_SESSION_ID}"', plan.session_plan.prompt or "")
        self.assertEqual(7, len(plan.command or ()))

        summary = worker_resume_plan_to_dict(plan)
        self.assertEqual(2, summary["selected_index"])
        self.assertEqual(WORKER_B_SESSION_ID, summary["selected_session_id"])
        self.assertEqual(2, summary["worker_count"])
        self.assertEqual([WORKER_A_SESSION_ID, WORKER_B_SESSION_ID], summary["worker_session_ids"])
        self.assertEqual(2, summary["selected_worker"]["index"])

    def test_run_worker_resume_main_calls_resume_once(self) -> None:
        calls = []

        def fake_resume_worker_session(plan, **kwargs):
            calls.append((plan.selected_session_id, kwargs))
            return CommandResult(
                ok=True,
                args=("codex", "resume", "--include-non-interactive", plan.selected_session_id),
                stdout="",
                stderr="",
                returncode=0,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = root / ".core_program"
            core.mkdir(parents=True, exist_ok=True)
            assignment_state = core / "assignment_state.json"
            _assignment_state(assignment_state)

            with mock.patch.object(
                run_worker_resume,
                "resume_worker_session",
                side_effect=fake_resume_worker_session,
            ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                exit_code = run_worker_resume.main(
                    [
                        "--repo-dir",
                        str(root),
                        "--assignment-state",
                        str(assignment_state),
                        "--index",
                        "1",
                        "--compact",
                    ]
                )
            summary = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual(1, len(calls))
        self.assertEqual(WORKER_A_SESSION_ID, calls[0][0])
        self.assertEqual("real", summary["mode"])
        self.assertEqual(WORKER_A_SESSION_ID, summary["selected_session_id"])
        self.assertEqual("resumed", summary["effects"]["codex_sessions"])


if __name__ == "__main__":
    unittest.main()
