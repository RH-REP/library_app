from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.comments import (  # noqa: E402
    CommentPostResult,
    append_marker_footer,
    post_issue_comment,
)
from artifactforge_dispatch_v1.dispatch import (  # noqa: E402
    CommandResult,
    DispatchError,
    assignment_session_id,
    bootstrap_session_router,
    build_session_router_bootstrap_prompt,
    build_session_router_prompt,
    build_worker_prompt,
    discover_recent_codex_session_id,
    dispatch_queue_file,
    launch_visible_codex_session,
    parse_bootstrap_session_id,
    read_queue_record,
    validate_session_router_output,
    wait_for_assignment_session_id,
    write_queue_record,
)
from artifactforge_dispatch_v1.models import QueueRecord  # noqa: E402


WORKER_SESSION_ID = "11111111-1111-4111-8111-111111111111"
ROUTER_SESSION_ID = "22222222-2222-4222-8222-222222222222"
SELECTED_SESSION_ID = "33333333-3333-4333-8333-333333333333"


class FakeCodexRunner:
    def __init__(
        self,
        *,
        router_stdout: str = f"{SELECTED_SESSION_ID}\n",
        start_stdout: str = f"{SELECTED_SESSION_ID}\n",
        start_result: Any = None,
    ) -> None:
        self.router_stdout = router_stdout
        self.start_stdout = start_stdout
        self.start_result = start_result
        self.calls: list[tuple[str, str | None, str]] = []

    def resume_session(self, session_id: str, prompt: str) -> CommandResult:
        self.calls.append(("resume", session_id, prompt))
        return CommandResult(
            ok=True,
            args=("codex", "resume", "--include-non-interactive", session_id, prompt),
            stdout="",
        )

    def start_session(self, prompt: str) -> CommandResult:
        self.calls.append(("start", None, prompt))
        if self.start_result is not None:
            return self.start_result
        return CommandResult(
            ok=True,
            args=("codex", prompt),
            stdout=self.start_stdout,
        )

    def run_session_router(
        self,
        prompt: str,
        *,
        router_session_id: str | None = None,
    ) -> CommandResult:
        self.calls.append(("router", router_session_id, prompt))
        return CommandResult(
            ok=True,
            args=("codex", "resume", "--include-non-interactive", router_session_id or "", prompt),
            stdout=self.router_stdout,
        )


class BootstrapStartResult:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        session_id: str | None = None,
        router_session_id: str | None = None,
    ) -> None:
        self.ok = True
        self.args = ("codex",)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = 0
        if session_id is not None:
            self.session_id = session_id
        if router_session_id is not None:
            self.router_session_id = router_session_id


class FakeCommentRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def issue_comment(
        self,
        *,
        repo: str,
        issue_number: int,
        body: str,
    ) -> CommentPostResult:
        self.calls.append((repo, issue_number, body))
        return CommentPostResult(
            repo=repo,
            issue_number=issue_number,
            body=body,
            args=("gh", "issue", "comment", str(issue_number), "--repo", repo, "--body-file", "-"),
            posted=True,
            skipped=False,
            stdout="ok",
        )


def sample_record(*, prompt_kind: str = "worker", target_session_id: str = WORKER_SESSION_ID) -> QueueRecord:
    return QueueRecord(
        issue_number=7,
        issue_url="https://github.com/example/project/issues/7",
        issue_title="first artifact",
        event_type="issue_body",
        trigger_fingerprint="issue-7-body-sha256-abc123",
        target_session_id=target_session_id,
        prompt_kind=prompt_kind,
        body="What do you want to build?\nA small web app",
        source_id=None,
        sub_artifact_path="sub_artifact/001_first_artifact",
    )


class DispatchTest(unittest.TestCase):
    def test_queue_record_round_trip_and_prompt_wrapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.md"
            bootstrap_template = Path(tmp) / "bootstrap.md"
            bootstrap_template.write_text("# Session_router bootstrap v1\n", encoding="utf-8")
            record = sample_record()

            write_queue_record(queue_path, record)
            parsed = read_queue_record(queue_path)
            worker_prompt = build_worker_prompt(parsed)
            router_prompt = build_session_router_prompt(
                sample_record(prompt_kind="session_router", target_session_id=ROUTER_SESSION_ID)
            )
            bootstrap_prompt = build_session_router_bootstrap_prompt(
                repo_dir=Path(tmp),
                template_path=bootstrap_template,
            )

            self.assertEqual(parsed, record)
            self.assertIn("# Worker v1", worker_prompt)
            self.assertIn("WORKER_V1_INPUT", worker_prompt)
            self.assertIn("issue-7-body-sha256-abc123", worker_prompt)
            self.assertIn("# Session_router v1", router_prompt)
            self.assertIn("SESSION_ROUTER_V1_INPUT", router_prompt)
            self.assertIn("# Session_router bootstrap v1", bootstrap_prompt)
            self.assertIn("SESSION_ROUTER_BOOTSTRAP_V1_INPUT", bootstrap_prompt)

    def test_bootstrap_session_router_starts_and_saves_new_router_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "assignment_state.json"
            template_path = root / "bootstrap.md"
            template_path.write_text("# Session_router bootstrap v1\n", encoding="utf-8")
            original_assignments = [
                {
                    "issue_number": 7,
                    "session_id": WORKER_SESSION_ID,
                    "status": "active",
                }
            ]
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "router_session_id": None,
                        "next_sub_artifact_number": 5,
                        "assignments": original_assignments,
                    }
                ),
                encoding="utf-8",
            )
            runner = FakeCodexRunner()

            session_id = bootstrap_session_router(
                assignment_state_path=state_path,
                repo_dir=root,
                runner=runner,
                template_path=template_path,
            )

            self.assertEqual(session_id, SELECTED_SESSION_ID)
            self.assertEqual([call[0] for call in runner.calls], ["start"])
            self.assertIn("SESSION_ROUTER_BOOTSTRAP_V1_INPUT", runner.calls[0][2])
            self.assertIn(str(root), runner.calls[0][2])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["router_session_id"], SELECTED_SESSION_ID)
            self.assertEqual(state["next_sub_artifact_number"], 5)
            self.assertEqual(state["assignments"], original_assignments)

    def test_bootstrap_session_router_reuses_existing_router_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "assignment_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "router_session_id": ROUTER_SESSION_ID,
                        "next_sub_artifact_number": 2,
                        "assignments": [],
                    }
                ),
                encoding="utf-8",
            )
            runner = FakeCodexRunner()

            session_id = bootstrap_session_router(
                assignment_state_path=state_path,
                runner=runner,
                template_path=root / "missing.md",
            )

            self.assertEqual(session_id, ROUTER_SESSION_ID)
            self.assertEqual(runner.calls, [])

    def test_bootstrap_session_router_rejects_invalid_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "assignment_state.json"
            template_path = root / "bootstrap.md"
            template_path.write_text("# Session_router bootstrap v1\n", encoding="utf-8")
            runner = FakeCodexRunner(start_stdout="not-a-session-id\n")

            with self.assertRaises(DispatchError):
                bootstrap_session_router(
                    assignment_state_path=state_path,
                    repo_dir=root,
                    runner=runner,
                    template_path=template_path,
                )

    def test_parse_bootstrap_session_id_accepts_bare_uuid_stdout(self) -> None:
        result = CommandResult(
            ok=True,
            args=("codex",),
            stdout=f"{SELECTED_SESSION_ID}\n",
        )

        self.assertEqual(parse_bootstrap_session_id(result), SELECTED_SESSION_ID)

    def test_parse_bootstrap_session_id_accepts_ready_banner_with_session_line(self) -> None:
        result = CommandResult(
            ok=True,
            args=("codex",),
            stdout=f"SESSION_ROUTER_READY\nSession ID: {SELECTED_SESSION_ID}\n",
        )

        self.assertEqual(parse_bootstrap_session_id(result), SELECTED_SESSION_ID)

    def test_parse_bootstrap_session_id_rejects_ready_without_session_id(self) -> None:
        result = CommandResult(
            ok=True,
            args=("codex",),
            stdout="SESSION_ROUTER_READY\n",
        )

        with self.assertRaises(DispatchError):
            parse_bootstrap_session_id(result)

    def test_parse_bootstrap_session_id_rejects_multiple_uuid_candidates(self) -> None:
        result = CommandResult(
            ok=True,
            args=("codex",),
            stdout=f"SESSION_ROUTER_READY\nSession ID: {SELECTED_SESSION_ID}\n",
            stderr=f"debug previous session {ROUTER_SESSION_ID}\n",
        )

        with self.assertRaises(DispatchError):
            parse_bootstrap_session_id(result)

    def test_bootstrap_session_router_prefers_result_session_id_attribute_over_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "assignment_state.json"
            template_path = root / "bootstrap.md"
            template_path.write_text("# Session_router bootstrap v1\n", encoding="utf-8")
            result = BootstrapStartResult(
                session_id=SELECTED_SESSION_ID,
                stdout=f"Session ID: {ROUTER_SESSION_ID}\n",
            )
            runner = FakeCodexRunner(start_result=result)

            session_id = bootstrap_session_router(
                assignment_state_path=state_path,
                repo_dir=root,
                runner=runner,
                template_path=template_path,
            )

            self.assertEqual(session_id, SELECTED_SESSION_ID)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["router_session_id"], SELECTED_SESSION_ID)

    def test_visible_launch_discovers_bootstrap_session_id_from_codex_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex_home"
            run_dir = root / "runs"
            sessions_dir = codex_home / "sessions" / "2026" / "07"

            def launcher(script_path: Path, terminal_app: str) -> CommandResult:
                self.assertEqual("Terminal", terminal_app)
                script_text = script_path.read_text(encoding="utf-8")
                self.assertIn("--no-alt-screen", script_text)
                self.assertIn("prompt.md", script_text)
                sessions_dir.mkdir(parents=True)
                jsonl = sessions_dir / f"{SELECTED_SESSION_ID}.jsonl"
                jsonl.write_text(
                    "\n".join(
                        (
                            json.dumps(
                                {
                                    "type": "session_meta",
                                    "payload": {"session_id": SELECTED_SESSION_ID},
                                }
                            ),
                            "SESSION_ROUTER_BOOTSTRAP_V1_INPUT",
                        )
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return CommandResult(ok=True, args=("open",), returncode=0)

            result = launch_visible_codex_session(
                "hello\nSESSION_ROUTER_BOOTSTRAP_V1_INPUT\n",
                repo_dir=root,
                role="session_router_bootstrap",
                marker="SESSION_ROUTER_BOOTSTRAP_V1_INPUT",
                run_dir_base=run_dir,
                launcher=launcher,
                wait_seconds=0,
                codex_home=codex_home,
            )

            self.assertTrue(result.ok)
            self.assertEqual(f"{SELECTED_SESSION_ID}\n", result.stdout)

    def test_discover_recent_codex_session_id_requires_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions_dir = root / "sessions"
            sessions_dir.mkdir()
            (sessions_dir / f"{SELECTED_SESSION_ID}.jsonl").write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"session_id": SELECTED_SESSION_ID},
                    }
                )
                + "\n"
                + "other prompt\n",
                encoding="utf-8",
            )

            session_id = discover_recent_codex_session_id(
                marker="SESSION_ROUTER_BOOTSTRAP_V1_INPUT",
                cutoff_time=0,
                timeout_seconds=0,
                codex_home=root,
            )

            self.assertIsNone(session_id)

    def test_wait_for_assignment_session_id_reads_router_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assignment_state.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "router_session_id": ROUTER_SESSION_ID,
                        "next_sub_artifact_number": 2,
                        "assignments": [
                            {
                                "issue_number": 7,
                                "session_id": SELECTED_SESSION_ID,
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                SELECTED_SESSION_ID,
                assignment_session_id(path, issue_number=7),
            )
            self.assertEqual(
                SELECTED_SESSION_ID,
                wait_for_assignment_session_id(path, issue_number=7, timeout_seconds=0),
            )

    def test_dispatch_existing_worker_moves_queue_to_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "worker.md"
            pending_dir = root / "pending"
            write_queue_record(queue_path, sample_record())
            runner = FakeCodexRunner()

            result = dispatch_queue_file(
                queue_path,
                runner=runner,
                pending_dir=pending_dir,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.worker_session_id, WORKER_SESSION_ID)
            self.assertTrue(result.queue_moved)
            self.assertFalse(queue_path.exists())
            self.assertTrue((pending_dir / "worker.md").exists())
            self.assertEqual(runner.calls[0][0], "resume")
            self.assertEqual(runner.calls[0][1], WORKER_SESSION_ID)

    def test_dispatch_router_validates_output_sends_worker_and_updates_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "router.md"
            pending_dir = root / "pending"
            assignment_state = root / "assignment_state.json"
            write_queue_record(
                queue_path,
                sample_record(prompt_kind="session_router", target_session_id=ROUTER_SESSION_ID),
            )
            runner = FakeCodexRunner()

            result = dispatch_queue_file(
                queue_path,
                runner=runner,
                pending_dir=pending_dir,
                assignment_state_path=assignment_state,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.router_session_id, ROUTER_SESSION_ID)
            self.assertEqual(result.worker_session_id, SELECTED_SESSION_ID)
            self.assertEqual([call[0] for call in runner.calls], ["router", "resume"])
            self.assertTrue((pending_dir / "router.md").exists())
            state = json.loads(assignment_state.read_text(encoding="utf-8"))
            self.assertEqual(state["assignments"][0]["session_id"], SELECTED_SESSION_ID)

    def test_router_output_must_be_exactly_one_session_id_line(self) -> None:
        valid = validate_session_router_output(f"{SELECTED_SESSION_ID}\n")
        invalid = validate_session_router_output(f"{SELECTED_SESSION_ID}\nextra\n")

        self.assertTrue(valid.valid)
        self.assertEqual(valid.session_id, SELECTED_SESSION_ID)
        self.assertFalse(invalid.valid)
        self.assertEqual(invalid.error, "output must be one line")

    def test_dry_run_does_not_move_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "worker.md"
            pending_dir = root / "pending"
            write_queue_record(queue_path, sample_record())

            result = dispatch_queue_file(queue_path, dry_run=True, pending_dir=pending_dir)

            self.assertEqual(result.status, "planned")
            self.assertFalse(result.queue_moved)
            self.assertTrue(queue_path.exists())
            self.assertFalse((pending_dir / "worker.md").exists())

    def test_comment_posting_is_explicit_only(self) -> None:
        runner = FakeCommentRunner()
        body = append_marker_footer(
            "Done.",
            session_id=WORKER_SESSION_ID,
            trigger_fingerprint="issue-7-body-sha256-abc123",
            status="done",
        )

        planned = post_issue_comment(
            repo="example/project",
            issue_number=7,
            body=body,
            runner=runner,
        )
        posted = post_issue_comment(
            repo="example/project",
            issue_number=7,
            body=body,
            post_comments=True,
            runner=runner,
        )

        self.assertTrue(planned.skipped)
        self.assertFalse(planned.posted)
        self.assertEqual(runner.calls, [("example/project", 7, body)])
        self.assertTrue(posted.posted)


if __name__ == "__main__":
    unittest.main()
