from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.models import IssueComment, IssueSnapshot  # noqa: E402
from artifactforge_dispatch_v1.queueing import (  # noqa: E402
    RouterSessionRequired,
    build_queue_records,
    collect_issue_events,
    comment_fingerprint,
    issue_body_fingerprint,
    write_queue_files,
)


ROUTER_SESSION_ID = "11111111-1111-4111-8111-111111111111"
WORKER_SESSION_ID = "22222222-2222-4222-8222-222222222222"


def _issue(
    number: int,
    *,
    title: str = "Test issue",
    body: str = "Issue body",
    comments: tuple[IssueComment, ...] = (),
) -> IssueSnapshot:
    return IssueSnapshot(
        issue_number=number,
        issue_state="open",
        issue_url=f"https://example.invalid/issues/{number}",
        title=title,
        body=body,
        created_at="2026-07-10T00:00:00+00:00",
        updated_at=None,
        comments=comments,
    )


def _comment(
    comment_id: str,
    body: str,
    *,
    created_at: str = "2026-07-10T00:01:00+00:00",
) -> IssueComment:
    return IssueComment(
        comment_id=comment_id,
        author="user",
        body=body,
        created_at=created_at,
        url=f"https://example.invalid/comments/{comment_id}",
    )


def _assignment_state() -> dict[str, object]:
    return {
        "router_session_id": ROUTER_SESSION_ID,
        "assignments": [
            {
                "issue_number": 2,
                "session_id": WORKER_SESSION_ID,
                "sub_artifact_path": "sub_artifact/001_existing",
                "status": "active",
            }
        ],
    }


class QueueingTests(unittest.TestCase):
    def test_collect_issue_events_skips_ai_marker_comments_and_is_stable(self) -> None:
        user_comment = _comment("C1", "Please do this")
        marker_comment = _comment(
            "M1",
            'Done\n\n<!-- codex-agent-v1: {"thread_id":"worker",'
            '"trigger_fingerprint":"issue-1-body-sha256-x","status":"done"} -->',
        )
        issue = _issue(1, body="Build the artifact", comments=(user_comment, marker_comment))

        events = collect_issue_events((issue,))

        self.assertEqual(["issue_body", "comment"], [event.event_type for event in events])
        self.assertEqual(
            issue_body_fingerprint(1, "Build the artifact"),
            events[0].trigger_fingerprint,
        )
        self.assertEqual(
            comment_fingerprint(1, "C1", "Please do this"),
            events[1].trigger_fingerprint,
        )
        self.assertEqual(tuple(event.trigger_fingerprint for event in events), tuple(
            event.trigger_fingerprint for event in collect_issue_events((issue,))
        ))

    def test_build_queue_records_routes_worker_router_and_skips_duplicates(self) -> None:
        issue_one = _issue(1, title="New artifact", body="new body")
        issue_two = _issue(2, title="Existing artifact", body="existing body")
        issue_three = _issue(3, title="Already pending", body="pending body")
        issue_four = _issue(4, title="Already archived", body="archived body")

        records = build_queue_records(
            (issue_one, issue_two, issue_three, issue_four),
            _assignment_state(),
            pending_fingerprints=(issue_body_fingerprint(3, "pending body"),),
            archive_fingerprints=(issue_body_fingerprint(4, "archived body"),),
        )

        self.assertEqual([1, 2], [record.issue_number for record in records])
        self.assertEqual("session_router", records[0].prompt_kind)
        self.assertEqual(ROUTER_SESSION_ID, records[0].target_session_id)
        self.assertEqual("worker", records[1].prompt_kind)
        self.assertEqual(WORKER_SESSION_ID, records[1].target_session_id)
        self.assertEqual("sub_artifact/001_existing", records[1].sub_artifact_path)

    def test_worker_route_does_not_require_router_session_id(self) -> None:
        assignment_state = _assignment_state()
        assignment_state["router_session_id"] = ""

        records = build_queue_records(
            (_issue(2, title="Existing artifact", body="existing body"),),
            assignment_state,
        )

        self.assertEqual(1, len(records))
        self.assertEqual("worker", records[0].prompt_kind)
        self.assertEqual(WORKER_SESSION_ID, records[0].target_session_id)
        self.assertEqual("sub_artifact/001_existing", records[0].sub_artifact_path)

    def test_router_route_reports_missing_router_session_id(self) -> None:
        assignment_state = _assignment_state()
        assignment_state["router_session_id"] = ""

        with self.assertRaisesRegex(RouterSessionRequired, "router_session_id"):
            build_queue_records(
                (_issue(1, title="New artifact", body="new body"),),
                assignment_state,
            )

    def test_write_queue_files_supports_dry_run_and_real_write(self) -> None:
        issue = _issue(1, body="queue me")
        record = build_queue_records((issue,), _assignment_state())[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            queue_dir = Path(tmpdir) / "queue"
            dry_run_results = write_queue_files(
                (record,),
                queue_dir=queue_dir,
                dry_run=True,
            )

            self.assertFalse(dry_run_results[0].written)
            self.assertEqual("dry_run", dry_run_results[0].reason)
            self.assertFalse(dry_run_results[0].plan.path.exists())
            self.assertIn("trigger_fingerprint", dry_run_results[0].plan.content)

            write_results = write_queue_files((record,), queue_dir=queue_dir)

            self.assertTrue(write_results[0].written)
            self.assertTrue(write_results[0].plan.path.exists())
            self.assertIn("queue me", write_results[0].plan.path.read_text(encoding="utf-8"))

    def test_reassign_required_pending_routes_back_to_router(self) -> None:
        body = "This should move to another worker"
        fingerprint = issue_body_fingerprint(5, body)
        marker_payload = json.dumps(
            {
                "thread_id": WORKER_SESSION_ID,
                "trigger_fingerprint": fingerprint,
                "status": "reassign_required",
            },
            separators=(",", ":"),
        )
        issue = _issue(
            5,
            body=body,
            comments=(
                _comment(
                    "M5",
                    f"Wrong session\n\n<!-- codex-agent-v1: {marker_payload} -->",
                    created_at="2026-07-10T00:02:00+00:00",
                ),
            ),
        )

        records = build_queue_records(
            (issue,),
            _assignment_state(),
            pending_fingerprints=(fingerprint,),
        )

        self.assertEqual(1, len(records))
        self.assertEqual("session_router", records[0].prompt_kind)
        self.assertEqual(ROUTER_SESSION_ID, records[0].target_session_id)
        self.assertTrue(records[0].reassign_required)
        self.assertEqual(WORKER_SESSION_ID, records[0].previous_thread_id)

    def test_reassign_required_old_worker_pending_still_routes_to_router(self) -> None:
        body = "This should move to another worker"
        fingerprint = issue_body_fingerprint(5, body)
        marker_payload = json.dumps(
            {
                "thread_id": WORKER_SESSION_ID,
                "trigger_fingerprint": fingerprint,
                "status": "reassign_required",
            },
            separators=(",", ":"),
        )
        issue = _issue(
            5,
            body=body,
            comments=(
                _comment(
                    "M5",
                    f"Wrong session\n\n<!-- codex-agent-v1: {marker_payload} -->",
                    created_at="2026-07-10T00:02:00+00:00",
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = Path(tmp) / "pending"
            pending_dir.mkdir()
            pending_path = pending_dir / f"{WORKER_SESSION_ID}_{fingerprint}.md"
            pending_path.write_text(
                "# ArtifactForge Issue Event\n\n"
                "## Routing\n"
                f"- target_session_id: {WORKER_SESSION_ID}\n\n"
                "## Issue Event\n"
                f"- trigger_fingerprint: {fingerprint}\n",
                encoding="utf-8",
            )

            records = build_queue_records(
                (issue,),
                _assignment_state(),
                pending_dir=pending_dir,
            )

        self.assertEqual(1, len(records))
        self.assertEqual("session_router", records[0].prompt_kind)
        self.assertEqual(WORKER_SESSION_ID, records[0].previous_thread_id)

    def test_reassign_required_existing_handoff_pending_skips_requeue(self) -> None:
        body = "This should move to another worker"
        fingerprint = issue_body_fingerprint(5, body)
        marker_payload = json.dumps(
            {
                "thread_id": WORKER_SESSION_ID,
                "trigger_fingerprint": fingerprint,
                "status": "reassign_required",
            },
            separators=(",", ":"),
        )
        issue = _issue(
            5,
            body=body,
            comments=(
                _comment(
                    "M5",
                    f"Wrong session\n\n<!-- codex-agent-v1: {marker_payload} -->",
                    created_at="2026-07-10T00:02:00+00:00",
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = Path(tmp) / "pending"
            pending_dir.mkdir()
            pending_path = pending_dir / f"{ROUTER_SESSION_ID}_{fingerprint}.md"
            pending_path.write_text(
                "# ArtifactForge Issue Event\n\n"
                "## Routing\n"
                f"- target_session_id: {ROUTER_SESSION_ID}\n\n"
                "## Issue Event\n"
                f"- trigger_fingerprint: {fingerprint}\n",
                encoding="utf-8",
            )

            records = build_queue_records(
                (issue,),
                _assignment_state(),
                pending_dir=pending_dir,
            )

        self.assertEqual((), records)


if __name__ == "__main__":
    unittest.main()
