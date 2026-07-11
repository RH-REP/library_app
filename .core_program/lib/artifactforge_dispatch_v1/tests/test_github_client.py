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
    GitHubRepoInferenceError,
    fetch_issues_by_number,
    fetch_open_issues,
    infer_repo_from_origin_remote,
    load_open_issues_snapshot,
    parse_github_repo_from_remote_url,
    write_open_issues_snapshot,
)


class FakeGhRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command_list = list(command)
        self.commands.append(command_list)
        if command_list[:3] == ["gh", "api", "graphql"]:
            return subprocess.CompletedProcess(
                command_list,
                0,
                stdout=json.dumps(
                    {
                        "data": {
                            "repository": {
                                "issues": {
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                    "nodes": [
                                        {
                                            "number": 2,
                                            "state": "OPEN",
                                            "title": "Build first app",
                                            "url": "https://github.com/OWNER/REPO/issues/2",
                                            "body": "作りたいもの",
                                            "createdAt": "2026-07-10T00:00:00Z",
                                            "updatedAt": "2026-07-10T00:01:00Z",
                                            "comments": {
                                                "pageInfo": {
                                                    "hasNextPage": False,
                                                    "endCursor": None,
                                                },
                                                "nodes": [
                                                    {
                                                        "id": "IC_comment_55",
                                                        "databaseId": 55,
                                                        "author": {"login": "rh"},
                                                        "body": "追加要望",
                                                        "createdAt": "2026-07-10T00:02:00Z",
                                                        "updatedAt": "2026-07-10T00:03:00Z",
                                                        "url": "https://github.com/OWNER/REPO/issues/2#issuecomment-55",
                                                    }
                                                ],
                                            },
                                        }
                                    ],
                                }
                            }
                        }
                    }
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(command_list, 1, stdout="", stderr="unexpected command")


class PaginatedCommentRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command_list = list(command)
        self.commands.append(command_list)
        if "number=2" in command_list:
            return subprocess.CompletedProcess(
                command_list,
                0,
                stdout=json.dumps(
                    {
                        "data": {
                            "repository": {
                                "issue": {
                                    "comments": {
                                        "pageInfo": {
                                            "hasNextPage": False,
                                            "endCursor": None,
                                        },
                                        "nodes": [
                                            {
                                                "id": "IC_comment_second_page",
                                                "databaseId": 56,
                                                "author": {"login": "rh"},
                                                "body": "追加要望2",
                                                "createdAt": "2026-07-10T00:04:00Z",
                                                "updatedAt": "2026-07-10T00:05:00Z",
                                                "url": "https://github.com/OWNER/REPO/issues/2#issuecomment-56",
                                            }
                                        ],
                                    }
                                }
                            }
                        }
                    }
                ),
                stderr="",
            )
        if command_list[:3] == ["gh", "api", "graphql"]:
            return subprocess.CompletedProcess(
                command_list,
                0,
                stdout=json.dumps(
                    {
                        "data": {
                            "repository": {
                                "issues": {
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                    "nodes": [
                                        {
                                            "number": 2,
                                            "state": "OPEN",
                                            "title": "Build first app",
                                            "url": "https://github.com/OWNER/REPO/issues/2",
                                            "body": "作りたいもの",
                                            "createdAt": "2026-07-10T00:00:00Z",
                                            "updatedAt": "2026-07-10T00:01:00Z",
                                            "comments": {
                                                "pageInfo": {
                                                    "hasNextPage": True,
                                                    "endCursor": "COMMENT_CURSOR",
                                                },
                                                "nodes": [
                                                    {
                                                        "id": "IC_comment_first_page",
                                                        "databaseId": 55,
                                                        "author": {"login": "rh"},
                                                        "body": "追加要望",
                                                        "createdAt": "2026-07-10T00:02:00Z",
                                                        "updatedAt": "2026-07-10T00:03:00Z",
                                                        "url": "https://github.com/OWNER/REPO/issues/2#issuecomment-55",
                                                    }
                                                ],
                                            },
                                        }
                                    ],
                                }
                            }
                        }
                    }
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(command_list, 1, stdout="", stderr="unexpected command")


class IssueByNumberRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command_list = list(command)
        self.commands.append(command_list)
        if command_list[:3] == ["gh", "api", "graphql"]:
            return subprocess.CompletedProcess(
                command_list,
                0,
                stdout=json.dumps(
                    {
                        "data": {
                            "repository": {
                                "issue_2": {
                                    "number": 2,
                                    "state": "CLOSED",
                                    "title": "Closed work",
                                    "url": "https://github.com/OWNER/REPO/issues/2",
                                    "body": "done",
                                    "createdAt": "2026-07-10T00:00:00Z",
                                    "updatedAt": "2026-07-10T00:10:00Z",
                                    "comments": {
                                        "pageInfo": {
                                            "hasNextPage": False,
                                            "endCursor": None,
                                        },
                                        "nodes": [
                                            {
                                                "id": "IC_done",
                                                "databaseId": 77,
                                                "author": {"login": "codex"},
                                                "body": "done marker",
                                                "createdAt": "2026-07-10T00:09:00Z",
                                                "updatedAt": "2026-07-10T00:09:00Z",
                                                "url": "https://github.com/OWNER/REPO/issues/2#issuecomment-77",
                                            }
                                        ],
                                    },
                                },
                                "issue_3": None,
                            }
                        }
                    }
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(command_list, 1, stdout="", stderr="unexpected command")


class GitHubClientTests(unittest.TestCase):
    def test_parse_github_repo_from_remote_url_supports_https_and_ssh(self) -> None:
        cases = {
            "https://github.com/OWNER/REPO.git": "OWNER/REPO",
            "https://github.com/OWNER/REPO": "OWNER/REPO",
            "git@github.com:OWNER/REPO.git": "OWNER/REPO",
            "git@github.com:OWNER/REPO": "OWNER/REPO",
            "ssh://git@github.com/OWNER/REPO.git": "OWNER/REPO",
        }

        for remote_url, expected in cases.items():
            with self.subTest(remote_url=remote_url):
                self.assertEqual(expected, parse_github_repo_from_remote_url(remote_url))

    def test_parse_github_repo_from_remote_url_rejects_unknown_shapes(self) -> None:
        for remote_url in (
            "",
            "https://example.com/OWNER/REPO.git",
            "https://github.com/OWNER/REPO/extra.git",
            "not-a-github-remote",
        ):
            with self.subTest(remote_url=remote_url):
                self.assertIsNone(parse_github_repo_from_remote_url(remote_url))

    def test_infer_repo_from_origin_remote_uses_git_origin(self) -> None:
        commands = []

        def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
            commands.append(list(command))
            return subprocess.CompletedProcess(
                list(command),
                0,
                stdout="git@github.com:OWNER/REPO.git\n",
                stderr="",
            )

        repo = infer_repo_from_origin_remote("/repo/root", runner=runner)

        self.assertEqual("OWNER/REPO", repo)
        self.assertEqual(
            ["git", "-C", "/repo/root", "remote", "get-url", "origin"],
            commands[0],
        )

    def test_infer_repo_from_origin_remote_has_actionable_error(self) -> None:
        def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                list(command),
                0,
                stdout="https://example.com/OWNER/REPO.git\n",
                stderr="",
            )

        with self.assertRaisesRegex(GitHubRepoInferenceError, "--repo OWNER/REPO"):
            infer_repo_from_origin_remote("/repo/root", runner=runner)

    def test_fetch_open_issues_uses_graphql_and_normalizes_comments(self) -> None:
        runner = FakeGhRunner()

        issues = fetch_open_issues("OWNER/REPO", limit=50, runner=runner)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_number, 2)
        self.assertEqual(issues[0].issue_state, "open")
        self.assertEqual(issues[0].comments[0].comment_id, "IC_comment_55")
        self.assertEqual(issues[0].comments[0].author, "rh")
        self.assertEqual(len(runner.commands), 1)
        self.assertEqual(runner.commands[0][0:3], ["gh", "api", "graphql"])
        self.assertIn("owner=OWNER", runner.commands[0])
        self.assertIn("name=REPO", runner.commands[0])

    def test_fetch_open_issues_fetches_additional_comment_pages(self) -> None:
        runner = PaginatedCommentRunner()

        issues = fetch_open_issues("OWNER/REPO", runner=runner)

        self.assertEqual(len(issues), 1)
        self.assertEqual(
            [comment.comment_id for comment in issues[0].comments],
            ["IC_comment_first_page", "IC_comment_second_page"],
        )
        self.assertEqual(len(runner.commands), 2)
        self.assertIn("number=2", runner.commands[1])
        self.assertIn("commentCursor=COMMENT_CURSOR", runner.commands[1])

    def test_fetch_issues_by_number_uses_graphql_aliases_for_open_or_closed(self) -> None:
        runner = IssueByNumberRunner()

        issues = fetch_issues_by_number("OWNER/REPO", (2, 3), runner=runner)

        self.assertEqual(len(issues), 1)
        self.assertEqual(2, issues[0].issue_number)
        self.assertEqual("closed", issues[0].issue_state)
        self.assertEqual("IC_done", issues[0].comments[0].comment_id)
        self.assertEqual(len(runner.commands), 1)
        query_arg = next(arg for arg in runner.commands[0] if arg.startswith("query="))
        self.assertIn("issue_2: issue(number: 2)", query_arg)
        self.assertIn("issue_3: issue(number: 3)", query_arg)
        self.assertNotIn("states: OPEN", query_arg)

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
