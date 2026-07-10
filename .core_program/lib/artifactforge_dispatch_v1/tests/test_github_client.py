from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Sequence


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.github_client import (  # noqa: E402
    GitHubFetchError,
    fetch_open_issues,
    load_open_issues_snapshot,
    write_open_issues_snapshot,
)


class FakeGhRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command_list = list(command)
        self.commands.append(command_list)
        if command_list[:3] == ["gh", "issue", "list"]:
            return subprocess.CompletedProcess(
                command_list,
                0,
                stdout=json.dumps([{"number": 2}, {"number": 3}]),
                stderr="",
            )
        if command_list[:3] == ["gh", "issue", "view"] and command_list[3] == "2":
            return subprocess.CompletedProcess(
                command_list,
                0,
                stdout=json.dumps(
                    {
                        "number": 2,
                        "state": "OPEN",
                        "title": "Build first app",
                        "url": "https://github.com/OWNER/REPO/issues/2",
                        "body": "作りたいもの",
                        "createdAt": "2026-07-10T00:00:00Z",
                        "updatedAt": "2026-07-10T00:01:00Z",
                        "comments": [
                            {
                                "databaseId": 55,
                                "author": {"login": "rh"},
                                "body": "追加要望",
                                "createdAt": "2026-07-10T00:02:00Z",
                                "updatedAt": "2026-07-10T00:03:00Z",
                                "url": "https://github.com/OWNER/REPO/issues/2#issuecomment-55",
                            }
                        ],
                    }
                ),
                stderr="",
            )
        if command_list[:3] == ["gh", "issue", "view"] and command_list[3] == "3":
            return subprocess.CompletedProcess(
                command_list,
                0,
                stdout=json.dumps(
                    {
                        "number": 3,
                        "state": "CLOSED",
                        "title": "Closed",
                        "url": "https://github.com/OWNER/REPO/issues/3",
                        "body": "done",
                        "comments": [],
                    }
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(command_list, 1, stdout="", stderr="unexpected command")


class GitHubClientTests(unittest.TestCase):
    def test_fetch_open_issues_uses_gh_and_normalizes_comments(self) -> None:
        runner = FakeGhRunner()

        issues = fetch_open_issues("OWNER/REPO", limit=50, runner=runner)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_number, 2)
        self.assertEqual(issues[0].issue_state, "open")
        self.assertEqual(issues[0].comments[0].comment_id, "55")
        self.assertEqual(issues[0].comments[0].author, "rh")
        self.assertIn("--repo", runner.commands[0])
        self.assertIn("OWNER/REPO", runner.commands[0])
        self.assertEqual(runner.commands[1][0:4], ["gh", "issue", "view", "2"])
        self.assertEqual(runner.commands[2][0:4], ["gh", "issue", "view", "3"])

    def test_fetch_raises_on_gh_error(self) -> None:
        def failing_runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(list(command), 1, stdout="", stderr="auth failed")

        with self.assertRaisesRegex(GitHubFetchError, "auth failed"):
            fetch_open_issues("OWNER/REPO", runner=failing_runner)

    def test_fetch_rejects_invalid_repo_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "OWNER/REPO"):
            fetch_open_issues("OWNER")

    def test_write_and_load_open_issue_snapshot(self) -> None:
        runner = FakeGhRunner()
        issues = fetch_open_issues("OWNER/REPO", runner=runner)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "open_issues.json"
            written = write_open_issues_snapshot(
                issues,
                repo="OWNER/REPO",
                path=path,
                fetched_at="2026-07-10T00:10:00+00:00",
            )
            payload = json.loads(written.read_text(encoding="utf-8"))
            loaded = load_open_issues_snapshot(path)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["repo"], "OWNER/REPO")
        self.assertEqual(payload["fetched_at"], "2026-07-10T00:10:00+00:00")
        self.assertEqual(loaded[0].issue_number, 2)
        self.assertEqual(loaded[0].comments[0].body, "追加要望")


if __name__ == "__main__":
    unittest.main()
