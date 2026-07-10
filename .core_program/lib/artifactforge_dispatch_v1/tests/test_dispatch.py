from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


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
    build_session_router_prompt,
    build_worker_prompt,
    dispatch_queue_file,
    read_queue_record,
    validate_session_router_output,
    write_queue_record,
)
from artifactforge_dispatch_v1.models import QueueRecord  # noqa: E402


WORKER_SESSION_ID = "11111111-1111-4111-8111-111111111111"
ROUTER_SESSION_ID = "22222222-2222-4222-8222-222222222222"
SELECTED_SESSION_ID = "33333333-3333-4333-8333-333333333333"


class FakeCodexRunner:
    def __init__(self, *, router_stdout: str = f"{SELECTED_SESSION_ID}\n") -> None:
        self.router_stdout = router_stdout
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
        return CommandResult(
            ok=True,
            args=("codex", prompt),
            stdout=f"{SELECTED_SESSION_ID}\n",
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
            record = sample_record()

            write_queue_record(queue_path, record)
            parsed = read_queue_record(queue_path)
            worker_prompt = build_worker_prompt(parsed)
            router_prompt = build_session_router_prompt(
                sample_record(prompt_kind="session_router", target_session_id=ROUTER_SESSION_ID)
            )

            self.assertEqual(parsed, record)
            self.assertIn("# Worker v1", worker_prompt)
            self.assertIn("WORKER_V1_INPUT", worker_prompt)
            self.assertIn("issue-7-body-sha256-abc123", worker_prompt)
            self.assertIn("# Session_router v1", router_prompt)
            self.assertIn("SESSION_ROUTER_V1_INPUT", router_prompt)

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
