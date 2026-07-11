from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.models import (  # noqa: E402
    AgentMarker,
    IssueComment,
    IssueSnapshot,
)
from artifactforge_dispatch_v1.queueing import (  # noqa: E402
    RouterSessionRequired,
    build_queue_records,
    collect_issue_events,
    thread_update_fingerprint,
    write_queue_files,
)


ROUTER_SESSION_ID = "11111111-1111-4111-8111-111111111111"
WORKER_SESSION_ID = "22222222-2222-4222-8222-222222222222"


def _issue(
    number: int,
    *,
    state: str = "open",
    title: str = "Test issue",
    body: str = "Issue body",
    comments: tuple[IssueComment, ...] = (),
) -> IssueSnapshot:
    return IssueSnapshot(
        issue_number=number,
        issue_state=state,
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
    def test_markerless_issue_body_and_comments_become_one_thread_event(self) -> None:
        user_comment = _comment("C1", "Please do this")
        second_comment = _comment(
            "C2",
            "Please include the settings screen",
            created_at="2026-07-10T00:02:00+00:00",
        )
        issue = _issue(
            1,
            body="Build the artifact",
            comments=(user_comment, second_comment),
        )

        events = collect_issue_events((issue,))
        event = events[0]

        self.assertEqual(1, len(events))
        self.assertEqual("thread_update", event.event_type)
        self.assertEqual("body..C2", event.source_id)
        self.assertIn("## Issue body", event.body)
        self.assertIn("Build the artifact", event.body)
        self.assertIn("## Comment C1", event.body)
        self.assertIn("Please do this", event.body)
        self.assertIn("## Comment C2", event.body)
        self.assertIn("Please include the settings screen", event.body)
        self.assertEqual(
            thread_update_fingerprint(1, "body", "C2", event.body),
            event.trigger_fingerprint,
        )
        self.assertEqual(tuple(event.trigger_fingerprint for event in events), tuple(
            event.trigger_fingerprint for event in collect_issue_events((issue,))
        ))

    def test_latest_marker_after_human_comments_starts_next_thread_event(self) -> None:
        before_marker = _comment("C1", "Earlier request")
        marker_comment = _comment(
            "M1",
            'Done\n\n<!-- codex-agent-v1: {"thread_id":"worker",'
            '"trigger_fingerprint":"issue-1-thread-body-C1-sha256-x","status":"done"} -->',
            created_at="2026-07-10T00:02:00+00:00",
        )
        first_after_marker = _comment(
            "C2",
            "New follow-up",
            created_at="2026-07-10T00:03:00+00:00",
        )
        second_after_marker = _comment(
            "C3",
            "Another follow-up",
            created_at="2026-07-10T00:04:00+00:00",
        )
        issue = _issue(
            1,
            body="Build the artifact",
            comments=(
                before_marker,
                marker_comment,
                first_after_marker,
                second_after_marker,
            ),
        )

        events = collect_issue_events((issue,))
        event = events[0]

        self.assertEqual(1, len(events))
        self.assertEqual("thread_update", event.event_type)
        self.assertEqual("C2..C3", event.source_id)
        self.assertIn("## Comment C2", event.body)
        self.assertIn("New follow-up", event.body)
        self.assertIn("## Comment C3", event.body)
        self.assertIn("Another follow-up", event.body)
        self.assertNotIn("## Issue body", event.body)
        self.assertNotIn("Build the artifact", event.body)
        self.assertNotIn("Earlier request", event.body)
        self.assertNotIn("codex-agent-v1", event.body)

    def test_latest_valid_marker_wins_and_ai_marker_comment_is_excluded(self) -> None:
        first_marker = _comment(
            "M1",
            'Done\n\n<!-- codex-agent-v1: {"thread_id":"worker",'
            '"trigger_fingerprint":"issue-1-thread-body-C1-sha256-x","status":"done"} -->',
            created_at="2026-07-10T00:02:00+00:00",
        )
        between_markers = _comment(
            "C2",
            "This comment is before the latest marker.",
            created_at="2026-07-10T00:03:00+00:00",
        )
        latest_marker = _comment(
            "M2",
            'Done\n\n<!-- codex-agent-v1: {"thread_id":"worker",'
            '"trigger_fingerprint":"issue-1-thread-C2-C2-sha256-y","status":"done"} -->',
            created_at="2026-07-10T00:04:00+00:00",
        )
        after_latest_marker = _comment(
            "C3",
            "This is the new request.",
            created_at="2026-07-10T00:05:00+00:00",
        )
        issue = _issue(
            1,
            body="Initial body",
            comments=(
                first_marker,
                between_markers,
                latest_marker,
                after_latest_marker,
            ),
        )

        events = collect_issue_events((issue,))
        event = events[0]

        self.assertEqual(1, len(events))
        self.assertEqual("C3", event.source_id)
        self.assertIn("This is the new request.", event.body)
        self.assertNotIn("This comment is before the latest marker.", event.body)
        self.assertNotIn("codex-agent-v1", event.body)

    def test_latest_marker_without_later_human_content_creates_no_event(self) -> None:
        marker_comment = _comment(
            "M1",
            'Done\n\n<!-- codex-agent-v1: {"thread_id":"worker",'
            '"trigger_fingerprint":"issue-1-thread-body-C1-sha256-x","status":"done"} -->',
            created_at="2026-07-10T00:02:00+00:00",
        )
        issue = _issue(
            1,
            body="Initial body",
            comments=(_comment("C1", "Earlier request"), marker_comment),
        )

        events = collect_issue_events((issue,))

        self.assertEqual((), events)

    def test_thread_fingerprint_is_stable_and_changes_when_comment_range_grows(self) -> None:
        issue = _issue(
            1,
            body="Initial body",
            comments=(_comment("C1", "First comment"),),
        )
        event = collect_issue_events((issue,))[0]
        repeated_event = collect_issue_events((issue,))[0]
        expanded_issue = _issue(
            1,
            body="Initial body",
            comments=(
                _comment("C1", "First comment"),
                _comment(
                    "C2",
                    "Second comment",
                    created_at="2026-07-10T00:02:00+00:00",
                ),
            ),
        )
        expanded_event = collect_issue_events((expanded_issue,))[0]

        self.assertEqual(event.trigger_fingerprint, repeated_event.trigger_fingerprint)
        self.assertNotEqual(event.trigger_fingerprint, expanded_event.trigger_fingerprint)
        self.assertTrue(event.trigger_fingerprint.startswith("issue-1-thread-body-C1-"))
        self.assertTrue(
            expanded_event.trigger_fingerprint.startswith("issue-1-thread-body-C2-")
        )

    def test_closed_issues_do_not_create_queue_records(self) -> None:
        issue = _issue(
            6,
            state="closed",
            body="This closed issue must not be queued again.",
            comments=(_comment("C6", "Closed issue follow-up"),),
        )

        records = build_queue_records((issue,), _assignment_state())

        self.assertEqual((), records)

    def test_build_queue_records_routes_worker_router_and_skips_duplicates(self) -> None:
        issue_one = _issue(1, title="New artifact", body="new body")
        issue_two = _issue(2, title="Existing artifact", body="existing body")
        issue_three = _issue(3, title="Already pending", body="pending body")
        issue_four = _issue(4, title="Already archived", body="archived body")

        pending_fingerprint = collect_issue_events((issue_three,))[0].trigger_fingerprint
        archive_fingerprint = collect_issue_events((issue_four,))[0].trigger_fingerprint

        records = build_queue_records(
            (issue_one, issue_two, issue_three, issue_four),
            _assignment_state(),
            pending_fingerprints=(pending_fingerprint,),
            archive_fingerprints=(archive_fingerprint,),
        )

        self.assertEqual([1, 2], [record.issue_number for record in records])
        self.assertEqual("session_router", records[0].prompt_kind)
        self.assertEqual("router", records[0].recipient_role)
        self.assertEqual(ROUTER_SESSION_ID, records[0].target_session_id)
        self.assertEqual("worker", records[1].prompt_kind)
        self.assertEqual("worker", records[1].recipient_role)
        self.assertEqual(WORKER_SESSION_ID, records[1].target_session_id)
        self.assertEqual("sub_artifact/001_existing", records[1].sub_artifact_path)

    def test_done_marker_for_thread_update_skips_queue_record(self) -> None:
        issue = _issue(1, title="Done thread", body="handled body")
        fingerprint = collect_issue_events((issue,))[0].trigger_fingerprint

        records = build_queue_records(
            (issue,),
            _assignment_state(),
            markers=(
                AgentMarker(
                    thread_id=WORKER_SESSION_ID,
                    trigger_fingerprint=fingerprint,
                    status="done",
                    issue_number=1,
                ),
            ),
        )

        self.assertEqual((), records)

    def test_worker_route_does_not_require_router_session_id(self) -> None:
        assignment_state = _assignment_state()
        assignment_state["router_session_id"] = ""

        records = build_queue_records(
            (_issue(2, title="Existing artifact", body="existing body"),),
            assignment_state,
        )

        self.assertEqual(1, len(records))
        self.assertEqual("worker", records[0].prompt_kind)
        self.assertEqual("worker", records[0].recipient_role)
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
        issue = _issue(5, body=body)
        fingerprint = collect_issue_events((issue,))[0].trigger_fingerprint

        records = build_queue_records(
            (issue,),
            _assignment_state(),
            markers=(
                AgentMarker(
                    thread_id=WORKER_SESSION_ID,
                    trigger_fingerprint=fingerprint,
                    status="reassign_required",
                    issue_number=5,
                ),
            ),
            pending_fingerprints=(fingerprint,),
        )

        self.assertEqual(1, len(records))
        self.assertEqual("session_router", records[0].prompt_kind)
        self.assertEqual("router", records[0].recipient_role)
        self.assertEqual(ROUTER_SESSION_ID, records[0].target_session_id)
        self.assertTrue(records[0].reassign_required)
        self.assertEqual(WORKER_SESSION_ID, records[0].previous_thread_id)

    def test_reassign_required_old_worker_pending_still_routes_to_router(self) -> None:
        body = "This should move to another worker"
        issue = _issue(5, body=body)
        fingerprint = collect_issue_events((issue,))[0].trigger_fingerprint

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
                markers=(
                    AgentMarker(
                        thread_id=WORKER_SESSION_ID,
                        trigger_fingerprint=fingerprint,
                        status="reassign_required",
                        issue_number=5,
                    ),
                ),
                pending_dir=pending_dir,
            )

        self.assertEqual(1, len(records))
        self.assertEqual("session_router", records[0].prompt_kind)
        self.assertEqual("router", records[0].recipient_role)
        self.assertEqual(WORKER_SESSION_ID, records[0].previous_thread_id)

    def test_reassign_required_existing_handoff_pending_skips_requeue(self) -> None:
        body = "This should move to another worker"
        issue = _issue(5, body=body)
        fingerprint = collect_issue_events((issue,))[0].trigger_fingerprint

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
                markers=(
                    AgentMarker(
                        thread_id=WORKER_SESSION_ID,
                        trigger_fingerprint=fingerprint,
                        status="reassign_required",
                        issue_number=5,
                    ),
                ),
                pending_dir=pending_dir,
            )

        self.assertEqual((), records)


if __name__ == "__main__":
    unittest.main()
