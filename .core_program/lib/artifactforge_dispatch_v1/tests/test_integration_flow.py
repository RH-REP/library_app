from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1 import dry_run  # noqa: E402
from artifactforge_dispatch_v1.models import IssueComment, IssueSnapshot  # noqa: E402


def _snapshot_dict(snapshot: IssueSnapshot) -> dict[str, Any]:
    """Convert the production snapshot contract into the current fixture shape."""
    return {
        "number": snapshot.issue_number,
        "state": snapshot.issue_state,
        "url": snapshot.issue_url,
        "title": snapshot.title,
        "body": snapshot.body,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
        "comments": [
            {
                "id": comment.comment_id,
                "author": comment.author,
                "body": comment.body,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
                "url": comment.url,
            }
            for comment in snapshot.comments
        ],
    }


def _marker_comment(
    *,
    thread_id: str,
    trigger_fingerprint: str,
    status: str,
) -> str:
    payload = {
        "thread_id": thread_id,
        "trigger_fingerprint": trigger_fingerprint,
        "status": status,
    }
    return (
        "作業結果を確認しました。\n\n"
        f"<!-- codex-agent-v1: {json.dumps(payload, ensure_ascii=False)} -->"
    )


def _write_queue_file(
    root: Path,
    queue_entry: dict[str, Any],
    event: dry_run.IssueEvent,
) -> Path:
    queue_file = root / queue_entry["planned_queue_path"]
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        "\n".join(
            [
                f"# Issue {event.issue_number}: {event.issue_title}",
                "",
                f"- trigger_fingerprint: {event.trigger_fingerprint}",
                f"- prompt_kind: {queue_entry['prompt_kind']}",
                f"- target_session_id: {queue_entry['queue_target_session_id']}",
                "",
                event.body,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return queue_file


class FakeCodexRunner:
    """Small fake for the future production dispatch boundary.

    Expected production interface:
    - accept a queue file and dispatch metadata
    - send either the Session_router prompt or worker prompt
    - return the worker session ID that owns the pending item
    - move the successfully sent queue file into pending
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[dict[str, str]] = []

    def dispatch_and_move_to_pending(self, dispatch: dict[str, Any]) -> dict[str, str]:
        queue_file = self.root / dispatch["queue_path"]
        pending_file = self.root / dispatch["planned_pending_path"]
        pending_file.parent.mkdir(parents=True, exist_ok=True)

        prompt = queue_file.read_text(encoding="utf-8")
        session_id = str(dispatch["worker_prompt_target_session_id"])
        self.calls.append(
            {
                "prompt_kind": str(dispatch["prompt_kind"]),
                "target_session_id": session_id,
                "prompt": prompt,
            }
        )

        shutil.move(str(queue_file), str(pending_file))
        return {
            "session_id": session_id,
            "trigger_fingerprint": str(dispatch["trigger_fingerprint"]),
            "path": str(dispatch["planned_pending_path"]),
        }


class IntegrationFlowTest(unittest.TestCase):
    def test_queue_dispatch_pending_archive_flow_with_fake_runner(self) -> None:
        issue = IssueSnapshot(
            issue_number=101,
            issue_state="OPEN",
            issue_url="https://github.example.test/acme/app/issues/101",
            title="Create first artifact",
            body="何を作りたいですか？\n\n小さなWebアプリを作りたい。",
            created_at="2026-07-10T00:00:00Z",
            updated_at="2026-07-10T00:00:00Z",
        )
        assignment_state = {
            "schema_version": 1,
            "router_session_id": "router-session-0001",
            "next_sub_artifact_number": 1,
            "assignments": [],
        }

        issues = [_snapshot_dict(issue)]
        events = dry_run.collect_events(issues)
        self.assertEqual(1, len(events))

        queue_entries = dry_run.queue_plan(
            events,
            pending_entries=[],
            markers=[],
            assignment_state=assignment_state,
        )
        self.assertEqual(1, len(queue_entries))
        self.assertEqual("queue", queue_entries[0]["planned_action"])
        self.assertEqual("session_router", queue_entries[0]["prompt_kind"])
        self.assertEqual("sub_artifact/001_create_first_artifact", queue_entries[0]["sub_artifact_path"])

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue_file = _write_queue_file(root, queue_entries[0], events[0])
            self.assertTrue(queue_file.exists())

            dispatches = dry_run.dispatch_plan(queue_entries)
            self.assertEqual(1, len(dispatches))
            self.assertEqual("exactly one session ID line", dispatches[0]["router_output_contract"])
            self.assertEqual(
                "00000000-0000-4000-8000-000000000101",
                dispatches[0]["worker_prompt_target_session_id"],
            )

            runner = FakeCodexRunner(root)
            pending_record = runner.dispatch_and_move_to_pending(dispatches[0])

            self.assertFalse(queue_file.exists())
            self.assertTrue((root / pending_record["path"]).exists())
            self.assertEqual("session_router", runner.calls[0]["prompt_kind"])
            self.assertIn(events[0].body, runner.calls[0]["prompt"])

            completed_issue = IssueSnapshot(
                issue_number=issue.issue_number,
                issue_state="OPEN",
                issue_url=issue.issue_url,
                title=issue.title,
                body=issue.body,
                created_at=issue.created_at,
                updated_at="2026-07-10T00:10:00Z",
                comments=(
                    IssueComment(
                        comment_id="agent-done-1",
                        author="codex",
                        body=_marker_comment(
                            thread_id=pending_record["session_id"],
                            trigger_fingerprint=pending_record["trigger_fingerprint"],
                            status="done",
                        ),
                        created_at="2026-07-10T00:10:00Z",
                    ),
                ),
            )

            markers = dry_run.collect_markers([_snapshot_dict(completed_issue)])
            lifecycle = dry_run.pending_lifecycle([pending_record], markers)
            self.assertEqual(1, len(lifecycle))
            self.assertEqual("archive", lifecycle[0]["planned_state"])

            archive_file = root / lifecycle[0]["planned_archive_path"]
            archive_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(root / pending_record["path"]), str(archive_file))

            self.assertFalse((root / pending_record["path"]).exists())
            self.assertTrue(archive_file.exists())

    def test_done_pending_and_agent_comments_are_not_requeued(self) -> None:
        body = "初回依頼です。"
        user_comment_body = "追加で一覧画面も必要です。"
        issue_number = 202
        body_fingerprint = dry_run.issue_body_fingerprint(issue_number, body)
        comment_fingerprint = dry_run.comment_fingerprint(
            issue_number,
            "user-comment-1",
            user_comment_body,
        )
        issue = IssueSnapshot(
            issue_number=issue_number,
            issue_state="OPEN",
            issue_url="https://github.example.test/acme/app/issues/202",
            title="Existing worker flow",
            body=body,
            created_at="2026-07-10T01:00:00Z",
            updated_at="2026-07-10T01:30:00Z",
            comments=(
                IssueComment(
                    comment_id="user-comment-1",
                    author="user",
                    body=user_comment_body,
                    created_at="2026-07-10T01:05:00Z",
                ),
                IssueComment(
                    comment_id="agent-done",
                    author="codex",
                    body=_marker_comment(
                        thread_id="worker-session-202",
                        trigger_fingerprint=body_fingerprint,
                        status="done",
                    ),
                    created_at="2026-07-10T01:10:00Z",
                ),
                IssueComment(
                    comment_id="agent-reassign",
                    author="codex",
                    body=_marker_comment(
                        thread_id="worker-session-202",
                        trigger_fingerprint=comment_fingerprint,
                        status="reassign_required",
                    ),
                    created_at="2026-07-10T01:20:00Z",
                ),
            ),
        )
        assignment_state = {
            "schema_version": 1,
            "router_session_id": "router-session-0001",
            "next_sub_artifact_number": 2,
            "assignments": [
                {
                    "issue_number": issue_number,
                    "session_id": "worker-session-202",
                    "sub_artifact_path": "sub_artifact/001_existing_worker_flow",
                    "status": "active",
                }
            ],
        }
        pending_entries = [
            {
                "session_id": "worker-session-202",
                "trigger_fingerprint": comment_fingerprint,
                "path": dry_run.pending_path("worker-session-202", comment_fingerprint),
            }
        ]

        issues = [_snapshot_dict(issue)]
        events = dry_run.collect_events(issues)
        markers = dry_run.collect_markers(issues)
        queue_entries = dry_run.queue_plan(
            events,
            pending_entries=pending_entries,
            markers=markers,
            assignment_state=assignment_state,
        )
        lifecycle = dry_run.pending_lifecycle(pending_entries, markers)

        self.assertEqual((), events)
        self.assertEqual([], queue_entries)
        self.assertEqual("pending_reassign_required", lifecycle[0]["planned_state"])


if __name__ == "__main__":
    unittest.main()
