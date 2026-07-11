from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.lifecycle import (  # noqa: E402
    collect_agent_markers_from_issues,
    lifecycle_summary_to_dict,
    read_pending_record,
    reconcile_pending_from_issues,
    reconcile_pending_with_issue_snapshots,
    unresolved_pending_issue_numbers,
)
from artifactforge_dispatch_v1.models import IssueComment, IssueSnapshot  # noqa: E402


SESSION_ID = "11111111-1111-4111-8111-111111111111"


def issue_with_comment(
    marker: str,
    *,
    issue_number: int = 1,
    issue_state: str = "open",
    comment_id: str = "c1",
    created_at: str = "2026-07-10T00:00:00Z",
) -> IssueSnapshot:
    return IssueSnapshot(
        issue_number=issue_number,
        issue_state=issue_state,
        issue_url=f"https://github.com/example/repo/issues/{issue_number}",
        title="Test issue",
        body="request",
        created_at="2026-07-09T00:00:00Z",
        updated_at="2026-07-09T00:00:00Z",
        comments=(
            IssueComment(
                comment_id=comment_id,
                author="agent",
                body=marker,
                created_at=created_at,
            ),
        ),
    )


def issue_without_comments(
    *,
    issue_number: int = 1,
    issue_state: str = "open",
) -> IssueSnapshot:
    return IssueSnapshot(
        issue_number=issue_number,
        issue_state=issue_state,
        issue_url=f"https://github.com/example/repo/issues/{issue_number}",
        title="Test issue",
        body="request",
        created_at="2026-07-09T00:00:00Z",
        updated_at="2026-07-09T00:00:00Z",
        comments=(),
    )


def marker_body(
    fingerprint: str,
    status: str,
    *,
    thread_id: str = SESSION_ID,
) -> str:
    return (
        "Human visible comment.\n\n"
        "<!-- codex-agent-v1: "
        f'{{"thread_id":"{thread_id}",'
        f'"trigger_fingerprint":"{fingerprint}",'
        f'"status":"{status}"}}'
        " -->"
    )


class LifecycleTest(unittest.TestCase):
    def test_collects_valid_markers_from_issue_comments_only(self) -> None:
        valid_fingerprint = "issue-1-body-sha256-valid"
        invalid = (
            "<!-- codex-agent-v1: "
            '{"thread_id":"x","trigger_fingerprint":"issue-1-body-sha256-invalid",'
            '"status":"complete"}'
            " -->"
        )
        issue = issue_with_comment(
            marker_body(valid_fingerprint, "done") + "\n" + invalid
        )

        markers = collect_agent_markers_from_issues((issue,))

        self.assertEqual(1, len(markers))
        self.assertEqual(valid_fingerprint, markers[0].trigger_fingerprint)
        self.assertEqual("done", markers[0].status)
        self.assertEqual("c1", markers[0].comment_id)

    def test_reads_pending_record_from_markdown_metadata_or_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            metadata_path = tmp_path / "anything.md"
            metadata_path.write_text(
                "---\n"
                "session_id: session-from-metadata\n"
                "trigger_fingerprint: issue-1-body-sha256-meta\n"
                "---\n"
                "prompt",
                encoding="utf-8",
            )
            filename_path = (
                tmp_path / "session-from-name_issue-2-comment-c1-sha256-name.md"
            )
            filename_path.write_text("prompt", encoding="utf-8")

            metadata_record = read_pending_record(metadata_path)
            filename_record = read_pending_record(filename_path)

        self.assertEqual("session-from-metadata", metadata_record.session_id)
        self.assertEqual(
            "issue-1-body-sha256-meta",
            metadata_record.trigger_fingerprint,
        )
        self.assertEqual("session-from-name", filename_record.session_id)
        self.assertEqual(
            "issue-2-comment-c1-sha256-name",
            filename_record.trigger_fingerprint,
        )

    def test_reads_pending_record_from_bullet_queue_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "worker_issue-1-body-sha256-wrong.2.3.md"
            path.write_text(
                "# ArtifactForge Issue Event\n\n"
                "## Routing\n"
                "- target_session_id: session-from-bullet\n\n"
                "## Issue Event\n"
                "- trigger_fingerprint: issue-1-body-sha256-bullet\n",
                encoding="utf-8",
            )

            record = read_pending_record(path)

        self.assertEqual("session-from-bullet", record.session_id)
        self.assertEqual("issue-1-body-sha256-bullet", record.trigger_fingerprint)

    def test_done_marker_dry_run_plans_archive_without_moving(self) -> None:
        fingerprint = "issue-1-body-sha256-done"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_dir = tmp_path / "pending"
            archive_dir = tmp_path / "archive"
            pending_dir.mkdir()
            pending_path = pending_dir / f"{SESSION_ID}_{fingerprint}.md"
            pending_path.write_text("prompt", encoding="utf-8")
            issue = issue_with_comment(marker_body(fingerprint, "done"))

            summary = reconcile_pending_from_issues(
                (issue,),
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=True,
            )
            result = summary.results[0]

            self.assertEqual("archive", result.action)
            self.assertFalse(result.moved)
            self.assertTrue(pending_path.exists())
            self.assertFalse(archive_dir.exists())
            self.assertEqual(
                [fingerprint],
                [
                    item["pending"]["trigger_fingerprint"]
                    for item in lifecycle_summary_to_dict(summary)["items"]
                ],
            )

    def test_done_marker_real_run_moves_pending_to_archive(self) -> None:
        fingerprint = "issue-1-body-sha256-done"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_dir = tmp_path / "pending"
            archive_dir = tmp_path / "archive"
            pending_dir.mkdir()
            pending_path = pending_dir / f"{SESSION_ID}_{fingerprint}.md"
            pending_path.write_text("prompt", encoding="utf-8")
            issue = issue_with_comment(marker_body(fingerprint, "done"))

            summary = reconcile_pending_from_issues(
                (issue,),
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=False,
            )
            result = summary.results[0]

            self.assertEqual("archive", result.action)
            self.assertTrue(result.moved)
            self.assertFalse(pending_path.exists())
            self.assertTrue(Path(result.archive_path or "").exists())

    def test_closed_issue_done_marker_archives_unresolved_pending(self) -> None:
        fingerprint = "issue-7-body-sha256-closed-done"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_dir = tmp_path / "pending"
            archive_dir = tmp_path / "archive"
            pending_dir.mkdir()
            pending_path = pending_dir / f"{SESSION_ID}_{fingerprint}.md"
            pending_path.write_text("prompt", encoding="utf-8")
            initial_summary = reconcile_pending_from_issues(
                (),
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=False,
            )
            issue = issue_with_comment(
                marker_body(fingerprint, "done"),
                issue_number=7,
                issue_state="closed",
            )

            summary = reconcile_pending_with_issue_snapshots(initial_summary, (issue,))
            result = summary.results[0]

            self.assertEqual((7,), unresolved_pending_issue_numbers(initial_summary.results))
            self.assertEqual("archive", result.action)
            self.assertTrue(result.moved)
            self.assertEqual("done", result.status)
            self.assertEqual("done_marker_closed_issue", result.reason)
            self.assertFalse(pending_path.exists())
            self.assertTrue(Path(result.archive_path or "").exists())

    def test_closed_issue_without_marker_archives_unresolved_pending(self) -> None:
        fingerprint = "issue-8-body-sha256-closed-no-marker"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_dir = tmp_path / "pending"
            archive_dir = tmp_path / "archive"
            pending_dir.mkdir()
            pending_path = pending_dir / f"{SESSION_ID}_{fingerprint}.md"
            pending_path.write_text("prompt", encoding="utf-8")
            initial_summary = reconcile_pending_from_issues(
                (),
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=False,
            )
            issue = issue_without_comments(issue_number=8, issue_state="closed")

            summary = reconcile_pending_with_issue_snapshots(initial_summary, (issue,))
            result = summary.results[0]

            self.assertEqual("archive", result.action)
            self.assertTrue(result.moved)
            self.assertIsNone(result.status)
            self.assertEqual("issue_closed_without_marker", result.reason)
            self.assertFalse(pending_path.exists())
            self.assertTrue(Path(result.archive_path or "").exists())

    def test_open_or_missing_issue_keeps_unresolved_pending(self) -> None:
        open_fingerprint = "issue-9-body-sha256-open-no-marker"
        missing_fingerprint = "issue-10-body-sha256-not-visible"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_dir = tmp_path / "pending"
            archive_dir = tmp_path / "archive"
            pending_dir.mkdir()
            open_path = pending_dir / f"{SESSION_ID}_{open_fingerprint}.md"
            missing_path = pending_dir / f"{SESSION_ID}_{missing_fingerprint}.md"
            open_path.write_text("prompt", encoding="utf-8")
            missing_path.write_text("prompt", encoding="utf-8")
            initial_summary = reconcile_pending_from_issues(
                (),
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=False,
            )
            issue = issue_without_comments(issue_number=9, issue_state="open")

            summary = reconcile_pending_with_issue_snapshots(initial_summary, (issue,))
            result_by_fingerprint = {
                result.pending.trigger_fingerprint: result
                for result in summary.results
            }

            self.assertEqual(
                (9, 10),
                unresolved_pending_issue_numbers(initial_summary.results),
            )
            self.assertEqual(
                "keep_pending",
                result_by_fingerprint[open_fingerprint].action,
            )
            self.assertEqual(
                "keep_pending",
                result_by_fingerprint[missing_fingerprint].action,
            )
            self.assertTrue(open_path.exists())
            self.assertTrue(missing_path.exists())
            self.assertFalse(archive_dir.exists())

    def test_closed_issue_dry_run_plans_archive_without_moving(self) -> None:
        fingerprint = "issue-11-body-sha256-dry-run-closed"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_dir = tmp_path / "pending"
            archive_dir = tmp_path / "archive"
            pending_dir.mkdir()
            pending_path = pending_dir / f"{SESSION_ID}_{fingerprint}.md"
            pending_path.write_text("prompt", encoding="utf-8")
            initial_summary = reconcile_pending_from_issues(
                (),
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=True,
            )
            issue = issue_without_comments(issue_number=11, issue_state="closed")

            summary = reconcile_pending_with_issue_snapshots(initial_summary, (issue,))
            result = summary.results[0]

            self.assertEqual("archive", result.action)
            self.assertFalse(result.moved)
            self.assertEqual("issue_closed_without_marker", result.reason)
            self.assertTrue(pending_path.exists())
            self.assertFalse(archive_dir.exists())

    def test_blocked_marker_moves_to_human_wating_and_reassign_marker_does_the_same(self) -> None:
        reassign_fingerprint = "issue-1-body-sha256-reassign"
        auth_fingerprint = "issue-2-body-sha256-auth"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_dir = tmp_path / "pending"
            human_waiting_dir = tmp_path / "human_wating"
            archive_dir = tmp_path / "archive"
            pending_dir.mkdir()
            reassign_path = pending_dir / f"{SESSION_ID}_{reassign_fingerprint}.md"
            auth_path = pending_dir / f"{SESSION_ID}_{auth_fingerprint}.md"
            reassign_path.write_text("prompt", encoding="utf-8")
            auth_path.write_text("prompt", encoding="utf-8")
            issues = (
                issue_with_comment(
                    marker_body(reassign_fingerprint, "reassign_required"),
                    issue_number=1,
                    comment_id="c1",
                ),
                issue_with_comment(
                    marker_body(auth_fingerprint, "authentication_blocked"),
                    issue_number=2,
                    comment_id="c2",
                ),
            )

            summary = reconcile_pending_from_issues(
                issues,
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=False,
            )
            result_by_fingerprint = {
                result.pending.trigger_fingerprint: result
                for result in summary.results
            }

            self.assertEqual(
                "human_waiting",
                result_by_fingerprint[reassign_fingerprint].action,
            )
            self.assertTrue(
                result_by_fingerprint[reassign_fingerprint].reassign_required
            )
            self.assertEqual((reassign_fingerprint,), summary.reassign_required_fingerprints)
            self.assertEqual(
                {reassign_fingerprint, auth_fingerprint},
                set(summary.human_waiting_fingerprints),
            )
            self.assertEqual(
                "human_waiting",
                result_by_fingerprint[auth_fingerprint].action,
            )
            self.assertTrue(
                result_by_fingerprint[auth_fingerprint].authentication_blocked
            )
            self.assertFalse(reassign_path.exists())
            self.assertFalse(auth_path.exists())
            self.assertTrue((human_waiting_dir / reassign_path.name).exists())
            self.assertTrue((human_waiting_dir / auth_path.name).exists())
            self.assertFalse(archive_dir.exists())

    def test_human_wating_records_archive_when_done_marker_arrives(self) -> None:
        fingerprint = "issue-3-body-sha256-human-wating"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_dir = tmp_path / "pending"
            human_waiting_dir = tmp_path / "human_wating"
            archive_dir = tmp_path / "archive"
            human_waiting_dir.mkdir(parents=True)
            waiting_path = human_waiting_dir / f"{SESSION_ID}_{fingerprint}.md"
            waiting_path.write_text("prompt", encoding="utf-8")
            issue = issue_with_comment(marker_body(fingerprint, "done"))

            summary = reconcile_pending_from_issues(
                (issue,),
                pending_dir=pending_dir,
                archive_dir=archive_dir,
                dry_run=False,
            )
            result = summary.results[0]

            self.assertEqual("archive", result.action)
            self.assertTrue(result.moved)
            self.assertFalse(waiting_path.exists())
            self.assertTrue(Path(result.archive_path or "").exists())


if __name__ == "__main__":
    unittest.main()
