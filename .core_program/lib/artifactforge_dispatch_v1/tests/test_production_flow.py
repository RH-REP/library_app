from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.dispatch import (  # noqa: E402
    CommandResult,
    dispatch_queue_file,
)
from artifactforge_dispatch_v1.lifecycle import reconcile_pending_from_issues  # noqa: E402
from artifactforge_dispatch_v1.models import IssueComment, IssueSnapshot  # noqa: E402
from artifactforge_dispatch_v1.queueing import (  # noqa: E402
    build_queue_records,
    write_queue_files,
)


ROUTER_SESSION_ID = "11111111-1111-4111-8111-111111111111"
WORKER_SESSION_ID = "22222222-2222-4222-8222-222222222222"


class FakeCodexRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def run_session_router(
        self,
        prompt: str,
        *,
        router_session_id: str | None = None,
    ) -> CommandResult:
        self.calls.append(("router", router_session_id or "", prompt))
        return CommandResult(
            ok=True,
            args=("codex", "resume", "--include-non-interactive", router_session_id or "", prompt),
            stdout=f"{WORKER_SESSION_ID}\n",
        )

    def resume_session(self, session_id: str, prompt: str) -> CommandResult:
        self.calls.append(("resume", session_id, prompt))
        return CommandResult(
            ok=True,
            args=("codex", "resume", "--include-non-interactive", session_id, prompt),
        )


def _marker(
    *,
    trigger_fingerprint: str,
    status: str = "done",
    thread_id: str = WORKER_SESSION_ID,
) -> str:
    payload = {
        "thread_id": thread_id,
        "trigger_fingerprint": trigger_fingerprint,
        "status": status,
    }
    return f"作業しました。\n\n<!-- codex-agent-v1: {json.dumps(payload, separators=(',', ':'))} -->"


class ProductionFlowTest(unittest.TestCase):
    def test_queue_dispatch_and_archive_with_fake_codex(self) -> None:
        issue = IssueSnapshot(
            issue_number=1,
            issue_state="open",
            issue_url="https://github.com/example/project/issues/1",
            title="Build first artifact",
            body="最初の成果物を作ってください。",
            created_at="2026-07-10T00:00:00Z",
        )
        assignment_state = {
            "schema_version": 1,
            "router_session_id": ROUTER_SESSION_ID,
            "next_sub_artifact_number": 1,
            "assignments": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_dir = root / "queue"
            pending_dir = root / "pending"
            archive_dir = root / "archive"
            assignment_path = root / "assignment_state.json"

            records = build_queue_records((issue,), assignment_state)
            queue_results = write_queue_files(records, queue_dir=queue_dir)
            queue_path = queue_results[0].plan.path

            runner = FakeCodexRunner()
            dispatch = dispatch_queue_file(
                queue_path,
                pending_dir=pending_dir,
                assignment_state_path=assignment_path,
                runner=runner,
            )

            self.assertTrue(dispatch.ok)
            self.assertEqual(["router", "resume"], [call[0] for call in runner.calls])
            self.assertFalse(queue_path.exists())
            self.assertTrue(dispatch.plan.pending_path.exists())
            state = json.loads(assignment_path.read_text(encoding="utf-8"))
            self.assertEqual(WORKER_SESSION_ID, state["assignments"][0]["session_id"])

            completed_issue = IssueSnapshot(
                issue_number=issue.issue_number,
                issue_state="open",
                issue_url=issue.issue_url,
                title=issue.title,
                body=issue.body,
                created_at=issue.created_at,
                comments=(
                    IssueComment(
                        comment_id="done-1",
                        author="codex",
                        body=_marker(
                            trigger_fingerprint=records[0].trigger_fingerprint,
                        ),
                        created_at="2026-07-10T00:10:00Z",
                    ),
                ),
            )
            lifecycle = reconcile_pending_from_issues(
                (completed_issue,),
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=False,
            )

            self.assertEqual("archive", lifecycle.results[0].action)
            self.assertTrue(lifecycle.results[0].moved)
            self.assertFalse(dispatch.plan.pending_path.exists())


if __name__ == "__main__":
    unittest.main()
