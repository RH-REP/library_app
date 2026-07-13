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
RUN_WORKER_LIST_PATH = (
    REPO_ROOT / ".core_program" / "app" / "02_dispatch_queue" / "run_worker_list.py"
)


def _load_run_worker_list_module(module_name: str = "artifactforge_run_worker_list"):
    spec = importlib.util.spec_from_file_location(module_name, RUN_WORKER_LIST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load run_worker_list.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_worker_list = _load_run_worker_list_module()

from artifactforge_dispatch_v1.dispatch import QueueRecord, write_queue_record  # noqa: E402
from artifactforge_dispatch_v1.worker_list import (  # noqa: E402
    collect_worker_session_catalog,
    human_summary,
    worker_session_catalog_to_dict,
)


ROUTER_SESSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
WORKER_A_SESSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
WORKER_B_SESSION_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
WORKER_C_SESSION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


def _record(
    *,
    issue_number: int,
    session_id: str,
    trigger_fingerprint: str,
) -> QueueRecord:
    return QueueRecord(
        issue_number=issue_number,
        issue_url=f"https://github.com/example/project/issues/{issue_number}",
        issue_title=f"issue {issue_number}",
        event_type="thread_update",
        trigger_fingerprint=trigger_fingerprint,
        target_session_id=session_id,
        prompt_kind="worker",
        body="## Issue body\n- source_id: body\n\nPlease do this",
        source_id="body",
        sub_artifact_path=f"sub_artifact/{issue_number:03d}_demo",
    )


class WorkerListTests(unittest.TestCase):
    def test_collect_worker_session_catalog_merges_sources_and_skips_router(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = root / ".core_program"
            core.mkdir(parents=True, exist_ok=True)
            assignment_state = core / "assignment_state.json"
            pending_dir = core / "pending"
            human_wating_dir = core / "human_wating"
            request_dir = core / "request_for_human"
            assignment_state.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "router_session_id": ROUTER_SESSION_ID,
                        "next_sub_artifact_number": 4,
                        "assignments": [
                            {
                                "issue_number": 1,
                                "session_id": WORKER_A_SESSION_ID,
                                "sub_artifact_path": "sub_artifact/001_alpha",
                                "status": "active",
                            },
                            {
                                "issue_number": 2,
                                "session_id": WORKER_B_SESSION_ID,
                                "sub_artifact_path": "sub_artifact/002_beta",
                                "status": "active",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            write_queue_record(
                pending_dir / "worker_a_pending.md",
                _record(
                    issue_number=1,
                    session_id=WORKER_A_SESSION_ID,
                    trigger_fingerprint="issue-1-thread-a-sha256-111",
                ),
            )
            write_queue_record(
                human_wating_dir / "worker_c_waiting.md",
                _record(
                    issue_number=3,
                    session_id=WORKER_C_SESSION_ID,
                    trigger_fingerprint="issue-3-thread-c-sha256-333",
                ),
            )
            (request_dir / "worker_b_request.md").parent.mkdir(parents=True, exist_ok=True)
            (request_dir / "worker_b_request.md").write_text(
                "\n".join(
                    [
                        "日時: 2026-07-13 10:00",
                        "Pending fingerprints: issue-2-thread-b-sha256-222",
                        f"Worker session ID: {WORKER_B_SESSION_ID}",
                        "問い合わせ内容: ask for clarification",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            catalog = collect_worker_session_catalog(
                repo_dir=root,
                assignment_state_path=assignment_state,
                pending_dir=pending_dir,
                request_for_human_dir=request_dir,
                human_waiting_dir=human_wating_dir,
            )

        self.assertEqual(ROUTER_SESSION_ID, catalog.router_session_id)
        self.assertEqual(
            (
                WORKER_A_SESSION_ID,
                WORKER_B_SESSION_ID,
                WORKER_C_SESSION_ID,
            ),
            catalog.worker_session_ids,
        )
        self.assertEqual(3, len(catalog.entries))
        self.assertEqual(
            ["assignment_state", "pending"],
            list(catalog.entries[0].source_kinds),
        )
        self.assertEqual(
            ["assignment_state", "request_for_human"],
            list(catalog.entries[1].source_kinds),
        )
        self.assertEqual(
            ["human_wating"],
            list(catalog.entries[2].source_kinds),
        )

        summary_text = human_summary(catalog)
        self.assertIn("ArtifactForge worker list", summary_text)
        self.assertIn("1. " + WORKER_A_SESSION_ID, summary_text)
        self.assertIn("2. " + WORKER_B_SESSION_ID, summary_text)
        self.assertIn("3. " + WORKER_C_SESSION_ID, summary_text)
        self.assertNotIn(ROUTER_SESSION_ID, catalog.worker_session_ids)

        summary = worker_session_catalog_to_dict(catalog)
        self.assertEqual(3, summary["worker_count"])
        self.assertEqual(
            [WORKER_A_SESSION_ID, WORKER_B_SESSION_ID, WORKER_C_SESSION_ID],
            summary["worker_session_ids"],
        )
        self.assertEqual(1, summary["items"][0]["index"])
        self.assertEqual(3, summary["items"][2]["index"])

    def test_run_worker_list_main_compact_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = root / ".core_program"
            core.mkdir(parents=True, exist_ok=True)
            assignment_state = core / "assignment_state.json"
            assignment_state.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "router_session_id": ROUTER_SESSION_ID,
                        "next_sub_artifact_number": 1,
                        "assignments": [
                            {
                                "issue_number": 1,
                                "session_id": WORKER_A_SESSION_ID,
                                "sub_artifact_path": "sub_artifact/001_alpha",
                                "status": "active",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                exit_code = run_worker_list.main(
                    [
                        "--repo-dir",
                        str(root),
                        "--assignment-state",
                        str(assignment_state),
                        "--compact",
                    ]
                )
            summary = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual("compact", summary["mode"])
        self.assertEqual(1, summary["worker_count"])
        self.assertEqual([WORKER_A_SESSION_ID], summary["worker_session_ids"])
        self.assertEqual(1, summary["items"][0]["index"])


if __name__ == "__main__":
    unittest.main()
