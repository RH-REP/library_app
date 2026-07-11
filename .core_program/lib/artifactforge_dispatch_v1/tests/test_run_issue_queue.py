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

from artifactforge_dispatch_v1.github_client import GitHubFetchError  # noqa: E402
from artifactforge_dispatch_v1.models import IssueComment, IssueSnapshot  # noqa: E402


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


def _write_thread_update_issue_snapshots(path: Path) -> None:
    payload = {
        "issues": [
            {
                "issue_number": 12,
                "issue_state": "open",
                "issue_url": "https://example.invalid/issues/12",
                "title": "Combined issue thread",
                "body": "Initial request",
                "created_at": "2026-07-10T00:00:00+00:00",
                "comments": [
                    {
                        "comment_id": "C12A",
                        "author": "user",
                        "body": "First follow-up",
                        "created_at": "2026-07-10T00:01:00+00:00",
                        "url": "https://example.invalid/comments/C12A",
                    },
                    {
                        "comment_id": "C12B",
                        "author": "user",
                        "body": "Second follow-up",
                        "created_at": "2026-07-10T00:02:00+00:00",
                        "url": "https://example.invalid/comments/C12B",
                    },
                ],
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


def _marker_body(
    fingerprint: str,
    status: str,
    *,
    thread_id: str = WORKER_SESSION_ID,
) -> str:
    return (
        "Finished.\n\n"
        "<!-- codex-agent-v1: "
        f'{{"thread_id":"{thread_id}",'
        f'"trigger_fingerprint":"{fingerprint}",'
        f'"status":"{status}"}}'
        " -->"
    )


def _issue_snapshot(
    issue_number: int,
    *,
    issue_state: str,
    comments: tuple[IssueComment, ...] = (),
) -> IssueSnapshot:
    return IssueSnapshot(
        issue_number=issue_number,
        issue_state=issue_state,
        issue_url=f"https://example.invalid/issues/{issue_number}",
        title=f"Issue {issue_number}",
        body="body",
        created_at="2026-07-10T00:00:00+00:00",
        updated_at="2026-07-10T00:10:00+00:00",
        comments=comments,
    )


def _write_pending_event(path: Path, fingerprint: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# ArtifactForge Issue Event\n\n"
        "## Routing\n"
        f"- target_session_id: {WORKER_SESSION_ID}\n\n"
        "## Issue Event\n"
        f"- trigger_fingerprint: {fingerprint}\n",
        encoding="utf-8",
    )


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
        self.assertEqual("worker", summary["queue"]["items"][0]["recipient_role"])
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

    def test_real_run_checks_closed_issue_for_unresolved_pending_marker(self) -> None:
        fingerprint = "issue-9-body-sha256-closed-marker"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            output = root / "open_issues.json"
            pending_dir = root / "pending"
            archive_dir = root / "archive"
            pending_path = pending_dir / f"{WORKER_SESSION_ID}_{fingerprint}.md"
            _write_assignment_state(assignment_state)
            _write_pending_event(pending_path, fingerprint)
            issue = _issue_snapshot(
                9,
                issue_state="closed",
                comments=(
                    IssueComment(
                        comment_id="IC9",
                        author="codex",
                        body=_marker_body(fingerprint, "done"),
                        created_at="2026-07-10T00:12:00+00:00",
                    ),
                ),
            )

            with mock.patch.object(
                run_issue_queue,
                "fetch_open_issues",
                return_value=(),
            ) as fetch_open_issues, mock.patch.object(
                run_issue_queue,
                "fetch_issues_by_number",
                return_value=(issue,),
            ) as fetch_issues_by_number, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ) as stdout:
                exit_code = run_issue_queue.main(
                    [
                        "--repo",
                        "OWNER/REPO",
                        "--compact",
                        "--assignment-state",
                        str(assignment_state),
                        "--output",
                        str(output),
                        "--queue-dir",
                        str(root / "queue"),
                        "--pending-dir",
                        str(pending_dir),
                        "--archive-dir",
                        str(archive_dir),
                    ]
                )
                summary = json.loads(stdout.getvalue())
                pending_exists_after = pending_path.exists()
                archive_exists_after = archive_dir.exists()

        self.assertEqual(0, exit_code)
        fetch_open_issues.assert_called_once_with("OWNER/REPO", limit=100, gh_bin="gh")
        fetch_issues_by_number.assert_called_once_with(
            "OWNER/REPO",
            (9,),
            gh_bin="gh",
        )
        self.assertFalse(pending_exists_after)
        self.assertTrue(archive_exists_after)
        self.assertEqual("checked", summary["pending_issue_check"]["status"])
        self.assertEqual([9], summary["pending_issue_check"]["issue_numbers"])
        self.assertEqual(1, summary["pending_issue_check"]["fetched_count"])
        self.assertEqual(1, summary["archive"]["archived_count"])
        self.assertEqual(
            "done_marker_closed_issue",
            summary["archive"]["items"][0]["reason"],
        )

    def test_real_run_keeps_pending_when_closed_issue_check_fails(self) -> None:
        fingerprint = "issue-10-body-sha256-fetch-failed"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            output = root / "open_issues.json"
            pending_dir = root / "pending"
            archive_dir = root / "archive"
            pending_path = pending_dir / f"{WORKER_SESSION_ID}_{fingerprint}.md"
            _write_assignment_state(assignment_state)
            _write_pending_event(pending_path, fingerprint)

            with mock.patch.object(
                run_issue_queue,
                "fetch_open_issues",
                return_value=(),
            ) as fetch_open_issues, mock.patch.object(
                run_issue_queue,
                "fetch_issues_by_number",
                side_effect=GitHubFetchError("not visible"),
            ) as fetch_issues_by_number, mock.patch(
                "sys.stdout",
                new_callable=io.StringIO,
            ) as stdout:
                exit_code = run_issue_queue.main(
                    [
                        "--repo",
                        "OWNER/REPO",
                        "--compact",
                        "--assignment-state",
                        str(assignment_state),
                        "--output",
                        str(output),
                        "--queue-dir",
                        str(root / "queue"),
                        "--pending-dir",
                        str(pending_dir),
                        "--archive-dir",
                        str(archive_dir),
                    ]
                )
                summary = json.loads(stdout.getvalue())
                pending_exists_after = pending_path.exists()

        self.assertEqual(0, exit_code)
        fetch_open_issues.assert_called_once_with("OWNER/REPO", limit=100, gh_bin="gh")
        fetch_issues_by_number.assert_called_once_with(
            "OWNER/REPO",
            (10,),
            gh_bin="gh",
        )
        self.assertTrue(pending_exists_after)
        self.assertEqual("failed", summary["pending_issue_check"]["status"])
        self.assertEqual([10], summary["pending_issue_check"]["issue_numbers"])
        self.assertIn("not visible", summary["pending_issue_check"]["error"])
        self.assertEqual(0, summary["archive"]["archived_count"])
        self.assertEqual(1, summary["archive"]["kept_pending_count"])

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
        self.assertEqual("router", summary["queue"]["items"][0]["recipient_role"])
        self.assertEqual(
            run_issue_queue.PLANNED_ROUTER_SESSION_ID,
            summary["queue"]["items"][0]["target_session_id"],
        )
        self.assertNotIn("router_session_id", state)

    def test_dry_run_summary_combines_body_and_comments_into_one_queue_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assignment_state = root / "assignment_state.json"
            issues = root / "issues.json"
            _write_assignment_state(assignment_state)
            _write_thread_update_issue_snapshots(issues)

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
        self.assertEqual(1, summary["queue"]["queue_result_count"])
        item = summary["queue"]["items"][0]
        self.assertEqual("thread_update", item["event_type"])
        self.assertEqual("body..C12B", item["source_id"])
        self.assertTrue(item["trigger_fingerprint"].startswith("issue-12-thread-body-C12B-"))

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
                        "event_type": "thread_update",
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

        self.assertIn("Found new issue thread update (0)", text)
        self.assertIn("already queued (1)", text)
        self.assertIn("#2 thread: Demo screen -> worker", text)
        self.assertIn("pending (0)", text)

    def test_human_summary_lists_pending_requeue_commands(self) -> None:
        summary = {
            "repo": "OWNER/REPO",
            "mode": "real",
            "effects": {"codex_sessions": "not_started"},
            "queue": {"items": []},
            "archive": {
                "items": [
                    {
                        "action": "keep_pending",
                        "reason": "no_marker",
                        "pending": {
                            "path": f"/repo/.core_program/pending/pending-{index}.md",
                            "session_id": WORKER_SESSION_ID,
                            "trigger_fingerprint": f"issue-2-comment-{index}",
                        },
                    }
                    for index in range(1, 7)
                ]
            },
        }

        text = run_issue_queue.human_summary(
            summary,
            queue_dir="/repo/.core_program/queue",
        )

        self.assertIn("pending (6)", text)
        self.assertIn("pending -> queue commands (6)", text)
        self.assertIn(
            "mv /repo/.core_program/pending/pending-1.md "
            "/repo/.core_program/queue/pending-1.md",
            text,
        )
        self.assertIn("... and 1 more", text)
        self.assertNotIn("pending-6.md /repo/.core_program/queue/pending-6.md", text)


if __name__ == "__main__":
    unittest.main()
