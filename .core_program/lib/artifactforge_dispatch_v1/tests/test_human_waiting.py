from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.human_waiting import (  # noqa: E402
    human_waiting_records_to_dict,
    summarize_human_waiting_records,
)


SESSION_ID = "11111111-1111-4111-8111-111111111111"
WORKER_SESSION_ID = "22222222-2222-4222-8222-222222222222"


class HumanWaitingSummaryTest(unittest.TestCase):
    def test_summarize_human_waiting_records_reads_status_reason_and_session_id(self) -> None:
        fingerprint = "issue-3-body-sha256-human-wating"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            human_waiting_dir = root / "human_wating"
            human_waiting_dir.mkdir(parents=True)
            pending_state = root / "pending_state.json"
            waiting_path = human_waiting_dir / f"{SESSION_ID}_{fingerprint}.md"
            waiting_path.write_text("prompt", encoding="utf-8")
            pending_state.write_text(
                "{\n"
                '  "records": [\n'
                "    {\n"
                f'      "pending_path": "{waiting_path}",\n'
                f'      "trigger_fingerprint": "{fingerprint}",\n'
                '      "status": "reassign_required",\n'
                '      "reason": "needs human confirmation",\n'
                f'      "worker_session_id": "{WORKER_SESSION_ID}"\n'
                "    }\n"
                "  ]\n"
                "}\n",
                encoding="utf-8",
            )

            summaries = summarize_human_waiting_records(
                human_waiting_dir,
                pending_state_path=pending_state,
            )

        self.assertEqual(1, len(summaries))
        summary = summaries[0]
        self.assertEqual(fingerprint, summary.pending.trigger_fingerprint)
        self.assertEqual(3, summary.issue_number)
        self.assertEqual(str(waiting_path), summary.pending_state_path)
        self.assertEqual("reassign_required", summary.pending_state_status)
        self.assertEqual("needs human confirmation", summary.pending_state_reason)
        self.assertEqual(WORKER_SESSION_ID, summary.pending_state_session_id)

        as_dict = human_waiting_records_to_dict(summaries)
        self.assertEqual(fingerprint, as_dict[0]["pending"]["trigger_fingerprint"])
        self.assertEqual("reassign_required", as_dict[0]["pending_state_status"])

    def test_summarize_human_waiting_records_handles_missing_state(self) -> None:
        fingerprint = "issue-4-body-sha256-human-wating-missing-state"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            human_waiting_dir = root / "human_wating"
            human_waiting_dir.mkdir(parents=True)
            waiting_path = human_waiting_dir / f"{SESSION_ID}_{fingerprint}.md"
            waiting_path.write_text("prompt", encoding="utf-8")

            summaries = summarize_human_waiting_records(human_waiting_dir)

        self.assertEqual(1, len(summaries))
        summary = summaries[0]
        self.assertEqual(fingerprint, summary.pending.trigger_fingerprint)
        self.assertEqual(4, summary.issue_number)
        self.assertIsNone(summary.pending_state_path)
        self.assertIsNone(summary.pending_state_status)
        self.assertIsNone(summary.pending_state_reason)
        self.assertIsNone(summary.pending_state_session_id)


if __name__ == "__main__":
    unittest.main()
