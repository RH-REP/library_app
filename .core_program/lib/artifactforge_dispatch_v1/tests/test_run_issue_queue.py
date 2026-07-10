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
RUN_ISSUE_QUEUE_PATH = (
    REPO_ROOT / ".core_program" / "app" / "01_fetch_issue" / "run_issue_queue.py"
)


def _load_run_issue_queue_module(module_name: str = "artifactforge_run_issue_queue"):
    spec = importlib.util.spec_from_file_location(module_name, RUN_ISSUE_QUEUE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load run_issue_queue.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_issue_queue = _load_run_issue_queue_module()


ROUTER_SESSION_ID = "11111111-1111-4111-8111-111111111111"
WORKER_SESSION_ID = "22222222-2222-4222-8222-222222222222"
BOOTSTRAPPED_ROUTER_SESSION_ID = "99999999-9999-4999-8999-999999999999"
CLI_ROUTER_SESSION_ID = "88888888-8888-4888-8888-888888888888"


def _write_assignment_state(
    path: Path,
    *,
    router_session_id=ROUTER_SESSION_ID,
    assignments=None,
) -> None:
    payload = {
        "schema_version": 1,
        "next_sub_artifact_number": 1,
        "assignments": list(assignments or []),
    }
    if router_session_id is not None:
        payload["router_session_id"] = router_session_id
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_issue_snapshots(
    path: Path,
    *,
    issue_number: int = 1,
    title: str = "First issue",
    body: str = "Please build the first artifact.",
) -> None:
    payload = {
        "issues": [
            {
                "issue_number": issue_number,
                "issue_state": "open",
                "issue_url": "https://example.invalid/issues/{}".format(issue_number),
                "title": title,
                "body": body,
                "created_at": "2026-07-10T00:00:00+00:00",
                "comments": [],
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _dry_run_args(root: Path, assignment_state: Path, issues: Path):
    return [
        "--dry-run",
        "--repo",
        "OWNER/REPO",
        "--issues",
        str(issues),
        "--assignment-state",
        str(assignment_state),
        "--queue-dir",
        str(root / "queue"),
        "--pending-dir",
        str(root / "pending"),
        "--archive-dir",
        str(root / "archive"),
    ]


class RunIssueQueueTests(unittest.TestCase):
    def test_missing_router_id_worker_only_dry_run_does_not_plan_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            issues = root / "issues.json"
            assignment = {
                "issue_number": 2,
                "session_id": WORKER_SESSION_ID,
                "sub_artifact_path": "sub_artifact/001_existing",
                "status": "active",
            }
            _write_assignment_state(
                assignment_state,
                router_session_id="",
                assignments=[assignment],
            )
            _write_issue_snapshots(
                issues,
                issue_number=2,
                title="Existing worker issue",
                body="Continue the existing work.",
            )

            with mock.patch.object(
                run_issue_queue,
                "bootstrap_session_router",
            ) as bootstrap_session_router, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ) as stdout:
                exit_code = run_issue_queue.main(
                    _dry_run_args(root, assignment_state, issues) + ["--compact"]
                )
                summary = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        bootstrap_session_router.assert_not_called()
        self.assertEqual("not_started", summary["effects"]["codex_sessions"])
        self.assertEqual(1, len(summary["queue"]["items"]))
        self.assertEqual("worker", summary["queue"]["items"][0]["prompt_kind"])
        self.assertEqual(
            WORKER_SESSION_ID,
            summary["queue"]["items"][0]["target_session_id"],
        )

    def test_real_run_infers_origin_repo_when_repo_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            output = root / "open_issues.json"
            _write_assignment_state(assignment_state)

            with mock.patch.object(
                run_issue_queue,
                "infer_repo_from_origin_remote",
                return_value="OWNER/REPO",
            ) as infer_repo, mock.patch.object(
                run_issue_queue,
                "fetch_open_issues",
                return_value=(),
            ) as fetch_open_issues, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ) as stdout:
                exit_code = run_issue_queue.main(
                    [
                        "--compact",
                        "--assignment-state",
                        str(assignment_state),
                        "--output",
                        str(output),
                        "--queue-dir",
                        str(root / "queue"),
                        "--pending-dir",
                        str(root / "pending"),
                        "--archive-dir",
                        str(root / "archive"),
                    ]
                )

        self.assertEqual(0, exit_code)
        infer_repo.assert_called_once_with(run_issue_queue.REPO_ROOT)
        fetch_open_issues.assert_called_once_with("OWNER/REPO", limit=100, gh_bin="gh")
        summary = json.loads(stdout.getvalue())
        self.assertEqual("OWNER/REPO", summary["repo"])
        self.assertEqual("github", summary["issue_source"])
        self.assertEqual("called", summary["effects"]["github_fetch"])

    def test_repo_argument_takes_priority_over_origin_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            _write_assignment_state(assignment_state)

            with mock.patch.object(
                run_issue_queue,
                "infer_repo_from_origin_remote",
            ) as infer_repo, mock.patch.object(
                run_issue_queue,
                "fetch_open_issues",
                return_value=(),
            ) as fetch_open_issues, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ):
                exit_code = run_issue_queue.main(
                    [
                        "--repo",
                        "EXPLICIT/REPO",
                        "--compact",
                        "--assignment-state",
                        str(assignment_state),
                        "--output",
                        str(root / "open_issues.json"),
                        "--queue-dir",
                        str(root / "queue"),
                        "--pending-dir",
                        str(root / "pending"),
                        "--archive-dir",
                        str(root / "archive"),
                    ]
                )

        self.assertEqual(0, exit_code)
        infer_repo.assert_not_called()
        fetch_open_issues.assert_called_once_with("EXPLICIT/REPO", limit=100, gh_bin="gh")

    def test_dry_run_without_repo_keeps_fixture_default(self) -> None:
        with mock.patch.object(
            run_issue_queue,
            "infer_repo_from_origin_remote",
        ) as infer_repo, mock.patch.object(
            run_issue_queue,
            "fetch_open_issues",
        ) as fetch_open_issues, mock.patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ) as stdout:
            exit_code = run_issue_queue.main(["--dry-run", "--compact"])

        self.assertEqual(0, exit_code)
        infer_repo.assert_not_called()
        fetch_open_issues.assert_not_called()
        summary = json.loads(stdout.getvalue())
        self.assertEqual("fixture", summary["repo"])
        self.assertIn("fixtures/dry_run/issues.json", summary["issue_source"])
        self.assertEqual("not_called", summary["effects"]["github_fetch"])

    def test_missing_router_id_dry_run_plans_bootstrap_without_starting_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            issues = root / "issues.json"
            _write_assignment_state(assignment_state, router_session_id=None)
            _write_issue_snapshots(issues)

            with mock.patch.object(
                run_issue_queue,
                "bootstrap_session_router",
            ) as bootstrap_session_router, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ) as stdout:
                exit_code = run_issue_queue.main(
                    _dry_run_args(root, assignment_state, issues) + ["--compact"]
                )
                summary = json.loads(stdout.getvalue())
                state = json.loads(assignment_state.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        bootstrap_session_router.assert_not_called()
        self.assertEqual("router_bootstrap_planned", summary["effects"]["codex_sessions"])
        self.assertEqual("session_router", summary["queue"]["items"][0]["prompt_kind"])
        self.assertEqual(
            run_issue_queue.PLANNED_ROUTER_SESSION_ID,
            summary["queue"]["items"][0]["target_session_id"],
        )
        self.assertNotIn("router_session_id", state)

    def test_missing_router_id_real_run_bootstraps_and_uses_new_router_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            issues = root / "issues.json"
            _write_assignment_state(assignment_state, router_session_id=None)
            _write_issue_snapshots(issues)

            with mock.patch.object(
                run_issue_queue,
                "bootstrap_session_router",
                return_value=BOOTSTRAPPED_ROUTER_SESSION_ID,
            ) as bootstrap_session_router, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ) as stdout:
                exit_code = run_issue_queue.main(
                    [
                        "--repo",
                        "OWNER/REPO",
                        "--issues",
                        str(issues),
                        "--compact",
                        "--assignment-state",
                        str(assignment_state),
                        "--queue-dir",
                        str(root / "queue"),
                        "--pending-dir",
                        str(root / "pending"),
                        "--archive-dir",
                        str(root / "archive"),
                    ]
                )
                summary = json.loads(stdout.getvalue())
                state = json.loads(assignment_state.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        bootstrap_session_router.assert_called_once_with(
            assignment_state_path=str(assignment_state),
            repo_dir=run_issue_queue.REPO_ROOT,
        )
        self.assertEqual("router_bootstrap_started", summary["effects"]["codex_sessions"])
        self.assertEqual(
            BOOTSTRAPPED_ROUTER_SESSION_ID,
            summary["queue"]["items"][0]["target_session_id"],
        )
        self.assertEqual(BOOTSTRAPPED_ROUTER_SESSION_ID, state["router_session_id"])

    def test_missing_router_id_real_run_reports_bootstrap_failure_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            issues = root / "issues.json"
            _write_assignment_state(assignment_state, router_session_id=None)
            _write_issue_snapshots(issues)

            with mock.patch.object(
                run_issue_queue,
                "bootstrap_session_router",
                side_effect=RuntimeError("no session ID in stdout"),
            ) as bootstrap_session_router, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ):
                with self.assertRaises(SystemExit) as raised:
                    run_issue_queue.main(
                        [
                            "--repo",
                            "OWNER/REPO",
                            "--issues",
                            str(issues),
                            "--compact",
                            "--assignment-state",
                            str(assignment_state),
                            "--queue-dir",
                            str(root / "queue"),
                            "--pending-dir",
                            str(root / "pending"),
                            "--archive-dir",
                            str(root / "archive"),
                        ]
                    )

        message = str(raised.exception)
        self.assertIn("router bootstrap failed", message)
        self.assertIn("--router-session-id SESSION_ID", message)
        self.assertIn("assignment_state", message)
        bootstrap_session_router.assert_called_once_with(
            assignment_state_path=str(assignment_state),
            repo_dir=run_issue_queue.REPO_ROOT,
        )

    def test_router_session_id_argument_skips_bootstrap_and_updates_assignment_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            issues = root / "issues.json"
            _write_assignment_state(assignment_state, router_session_id=None)
            _write_issue_snapshots(issues)

            with mock.patch.object(
                run_issue_queue,
                "bootstrap_session_router",
            ) as bootstrap_session_router, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ) as stdout:
                exit_code = run_issue_queue.main(
                    [
                        "--repo",
                        "OWNER/REPO",
                        "--issues",
                        str(issues),
                        "--router-session-id",
                        CLI_ROUTER_SESSION_ID,
                        "--compact",
                        "--assignment-state",
                        str(assignment_state),
                        "--queue-dir",
                        str(root / "queue"),
                        "--pending-dir",
                        str(root / "pending"),
                        "--archive-dir",
                        str(root / "archive"),
                    ]
                )
                summary = json.loads(stdout.getvalue())
                state = json.loads(assignment_state.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        bootstrap_session_router.assert_not_called()
        self.assertEqual("not_started", summary["effects"]["codex_sessions"])
        self.assertEqual(
            CLI_ROUTER_SESSION_ID,
            summary["queue"]["items"][0]["target_session_id"],
        )
        self.assertEqual(CLI_ROUTER_SESSION_ID, state["router_session_id"])

    def test_human_summary_lists_already_queued_items(self) -> None:
        summary = {
            "repo": "OWNER/REPO",
            "mode": "real",
            "effects": {"codex_sessions": "not_started"},
            "queue": {
                "items": [
                    {
                        "action": "skip",
                        "event_type": "comment",
                        "issue_number": 2,
                        "issue_title": "Demo screen",
                        "prompt_kind": "worker",
                        "target_session_id": WORKER_SESSION_ID,
                        "sub_artifact_path": "sub_artifact/002_demo_screen",
                        "reassign_required": False,
                    }
                ]
            },
            "archive": {"items": []},
        }

        text = run_issue_queue.human_summary(summary)

        self.assertIn("Found new body/comment (0)", text)
        self.assertIn("already queued (1)", text)
        self.assertIn("#2 comment: Demo screen -> worker", text)
        self.assertIn("pending (0)", text)


if __name__ == "__main__":
    unittest.main()
