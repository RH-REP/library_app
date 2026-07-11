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
RUN_DISPATCH_QUEUE_PATH = (
    REPO_ROOT / ".core_program" / "app" / "02_dispatch_queue" / "run_dispatch_queue.py"
)


def _load_run_dispatch_queue_module(module_name: str = "artifactforge_run_dispatch_queue"):
    spec = importlib.util.spec_from_file_location(module_name, RUN_DISPATCH_QUEUE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load run_dispatch_queue.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_dispatch_queue = _load_run_dispatch_queue_module()


class RunDispatchQueueTest(unittest.TestCase):
    def test_limit_argument_is_passed_to_dispatch_queue(self) -> None:
        calls = []

        def fake_dispatch_queue(queue_dir, **kwargs):
            calls.append((queue_dir, kwargs))
            return ()

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            run_dispatch_queue,
            "dispatch_queue",
            side_effect=fake_dispatch_queue,
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            exit_code = run_dispatch_queue.main(
                [
                    "--dry-run",
                    "--compact",
                    "--queue-dir",
                    str(Path(temp_dir) / "queue"),
                    "--limit",
                    "1",
                ]
            )
            summary = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual(1, calls[0][1]["limit"])
        self.assertEqual(0, summary["entry_count"])

    def test_parallel_inflight_and_locks_are_passed_to_dispatch_queue(self) -> None:
        calls = []

        def fake_dispatch_queue(queue_dir, **kwargs):
            calls.append((queue_dir, kwargs))
            return ()

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            run_dispatch_queue,
            "dispatch_queue",
            side_effect=fake_dispatch_queue,
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            exit_code = run_dispatch_queue.main(
                [
                    "--compact",
                    "--queue-dir",
                    str(Path(temp_dir) / "queue"),
                    "--inflight-dir",
                    str(Path(temp_dir) / "inflight"),
                    "--pending-dir",
                    str(Path(temp_dir) / "pending"),
                    "--archive-dir",
                    str(Path(temp_dir) / "archive"),
                    "--locks-dir",
                    str(Path(temp_dir) / "locks"),
                    "--parallel",
                    "4",
                ]
            )
            summary = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual(str(Path(temp_dir) / "inflight"), calls[0][1]["inflight_dir"])
        self.assertEqual(str(Path(temp_dir) / "locks"), calls[0][1]["locks_dir"])
        self.assertEqual(4, calls[0][1]["parallel"])
        self.assertEqual("claimed_before_dispatch", summary["effects"]["inflight_files"])
        self.assertEqual("router_session_id_serialized", summary["effects"]["session_locks"])


if __name__ == "__main__":
    unittest.main()
