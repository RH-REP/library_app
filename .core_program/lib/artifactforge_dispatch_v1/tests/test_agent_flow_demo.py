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
LIB_DIR = REPO_ROOT / ".core_program" / "lib"
RUN_DEMO_PATH = (
    REPO_ROOT / ".core_program" / "app" / "03_agent_flow_demo" / "run_agent_flow_demo.py"
)
RUN_REAL_CODEX_DEMO_PATH = (
    REPO_ROOT
    / ".core_program"
    / "app"
    / "03_agent_flow_demo"
    / "run_real_codex_demo.py"
)
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.agent_flow_demo import (  # noqa: E402
    DEMO_ROUTER_SESSION_ID,
    DEMO_WORKER_A_SESSION_ID,
    DEFAULT_DEMO_QUEUE_PATH,
    DEFAULT_REAL_CODEX_FIXTURE_PATH,
    run_real_codex_demo,
    run_agent_flow_demo,
)
from artifactforge_dispatch_v1.dispatch import (  # noqa: E402
    build_dispatch_prompt,
    iter_queue_paths,
    read_queue_record,
)


def _load_run_demo_module(module_name: str = "artifactforge_run_agent_flow_demo"):
    spec = importlib.util.spec_from_file_location(module_name, RUN_DEMO_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load run_agent_flow_demo.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_run_real_codex_demo_module(
    module_name: str = "artifactforge_run_real_codex_demo",
):
    spec = importlib.util.spec_from_file_location(module_name, RUN_REAL_CODEX_DEMO_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load run_real_codex_demo.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AgentFlowDemoTest(unittest.TestCase):
    def test_demo_runs_router_worker_subagents_and_permission_grant(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = run_agent_flow_demo(work_dir=temp_dir)

            self.assertEqual("agent-flow-demo", summary["mode"])
            self.assertEqual(1, summary["resume_call_count"])
            self.assertEqual(1, summary["router_dispatch_count"])
            self.assertEqual(0, summary["worker_dispatch_count"])
            self.assertTrue(summary["verification_passed"])
            self.assertTrue(Path(str(summary["demo_software_path"])).exists())
            self.assertTrue((Path(temp_dir) / "pending" / DEFAULT_DEMO_QUEUE_PATH.name).exists())

            dispatch = summary["dispatch"]
            self.assertEqual(1, dispatch["sent_count"])
            self.assertEqual("visible", dispatch["items"][0]["session_visibility"])
            self.assertEqual(DEMO_ROUTER_SESSION_ID, dispatch["items"][0]["target_session_id"])

            event_names = [
                event["event"]
                for event in summary["transcript"]
                if isinstance(event, dict)
            ]
            self.assertIn("worker_handoff_once", event_names)
            self.assertIn("permission_requested", event_names)
            self.assertIn("permission_decision", event_names)
            self.assertIn("github_comment_planned", event_names)

            decisions = [
                event
                for event in summary["transcript"]
                if isinstance(event, dict) and event.get("event") == "permission_decision"
            ]
            self.assertEqual("granted", decisions[0]["decision"])
            self.assertIn("codex-agent-v1", summary["final_comment"])
            self.assertIn('"status":"done"', summary["final_comment"])

            state = json.loads((Path(temp_dir) / "assignment_state.json").read_text(encoding="utf-8"))
            self.assertEqual(DEMO_WORKER_A_SESSION_ID, state["assignments"][0]["session_id"])

    def test_demo_can_show_router_permission_denial(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = run_agent_flow_demo(work_dir=temp_dir, permission_mode="deny")

            self.assertFalse(summary["verification_passed"])
            self.assertIsNone(summary["demo_software_path"])
            self.assertIn('"status":"authentication_blocked"', summary["final_comment"])

    def test_demo_cli_compact_output(self) -> None:
        run_demo = _load_run_demo_module()
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ) as stdout:
            exit_code = run_demo.main(["--work-dir", temp_dir, "--compact"])
            summary = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual("agent-flow-demo", summary["mode"])
        self.assertEqual(1, summary["resume_call_count"])

    def test_real_codex_demo_prepares_isolated_router_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = run_real_codex_demo(
                fixture_path=DEFAULT_REAL_CODEX_FIXTURE_PATH,
                work_dir=temp_dir,
                router_session_id=DEMO_ROUTER_SESSION_ID,
            )

            self.assertEqual("prepared", summary["status"])
            self.assertEqual(DEMO_ROUTER_SESSION_ID, summary["router_session_id"])
            self.assertEqual(1, summary["queue"]["written_count"])
            queue_paths = iter_queue_paths(Path(temp_dir) / "queue")
            self.assertEqual(1, len(queue_paths))

            record = read_queue_record(queue_paths[0])
            self.assertEqual("router", record.recipient_role)
            self.assertEqual(DEMO_ROUTER_SESSION_ID, record.target_session_id)
            self.assertEqual("thread_update", record.event_type)

            prompt = build_dispatch_prompt(record)
            self.assertIn('"local_demo_contract"', prompt)
            self.assertIn('"external_side_effects_forbidden": true', prompt)

    def test_real_codex_demo_dry_run_dispatch_uses_real_dispatch_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = run_real_codex_demo(
                fixture_path=DEFAULT_REAL_CODEX_FIXTURE_PATH,
                work_dir=temp_dir,
                router_session_id=DEMO_ROUTER_SESSION_ID,
                dispatch=True,
                dry_run_dispatch=True,
            )

            self.assertEqual("dispatched", summary["status"])
            self.assertEqual(1, summary["dispatch"]["entry_count"])
            item = summary["dispatch"]["items"][0]
            self.assertEqual("router", item["recipient_role"])
            self.assertEqual("visible", item["session_visibility"])
            self.assertTrue(item["dry_run"])
            self.assertFalse(item["sent"])

    def test_real_codex_demo_requires_router_before_queue_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = run_real_codex_demo(
                fixture_path=DEFAULT_REAL_CODEX_FIXTURE_PATH,
                work_dir=temp_dir,
            )

            self.assertEqual("router_session_required", summary["status"])
            self.assertEqual(0, summary["queue"]["result_count"])
            self.assertIn("--bootstrap-router", summary["next_commands"][0])

    def test_real_codex_demo_cli_compact_output(self) -> None:
        run_real_demo = _load_run_real_codex_demo_module()
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ) as stdout:
            exit_code = run_real_demo.main(
                [
                    "--work-dir",
                    temp_dir,
                    "--router-session-id",
                    DEMO_ROUTER_SESSION_ID,
                    "--dry-run-dispatch",
                    "--compact",
                ]
            )
            summary = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual("real-codex-agent-flow-demo", summary["mode"])
        self.assertEqual(1, summary["dispatch"]["entry_count"])


if __name__ == "__main__":
    unittest.main()
