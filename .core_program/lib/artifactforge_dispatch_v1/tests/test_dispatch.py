from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


LIB_DIR = Path(__file__).resolve().parents[2]
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1 import dispatch as dispatch_module  # noqa: E402
from artifactforge_dispatch_v1.comments import (  # noqa: E402
    CommentPostResult,
    append_marker_footer,
    post_issue_comment,
)
from artifactforge_dispatch_v1.dispatch import (  # noqa: E402
    CommandResult,
    DispatchError,
    assignment_session_id,
    bootstrap_session_router,
    build_dispatch_prompt,
    build_session_router_bootstrap_prompt,
    build_session_router_prompt,
    build_worker_prompt,
    claim_queue_file,
    discover_recent_codex_session_id,
    dispatch_session_visibility,
    dispatch_queue,
    dispatch_queue_file,
    launch_visible_codex_session,
    parse_bootstrap_session_id,
    pending_destination,
    read_queue_record,
    acquire_session_lock,
    release_file_lock,
    validate_session_router_output,
    wait_for_assignment_session_id,
    write_queue_record,
)
from artifactforge_dispatch_v1.models import QueueRecord  # noqa: E402


WORKER_SESSION_ID = "11111111-1111-4111-8111-111111111111"
ROUTER_SESSION_ID = "22222222-2222-4222-8222-222222222222"
SELECTED_SESSION_ID = "33333333-3333-4333-8333-333333333333"


class FakeCodexRunner:
    def __init__(
        self,
        *,
        router_stdout: str = f"{SELECTED_SESSION_ID}\n",
        start_stdout: str = f"{SELECTED_SESSION_ID}\n",
        start_result: Any = None,
    ) -> None:
        self.router_stdout = router_stdout
        self.start_stdout = start_stdout
        self.start_result = start_result
        self.calls: list[tuple[str, str | None, str]] = []

    def resume_session(self, session_id: str, prompt: str) -> CommandResult:
        self.calls.append(("resume", session_id, prompt))
        return CommandResult(
            ok=True,
            args=("codex", "resume", "--include-non-interactive", session_id, prompt),
            stdout="",
        )

    def start_session(self, prompt: str) -> CommandResult:
        self.calls.append(("start", None, prompt))
        if self.start_result is not None:
            return self.start_result
        return CommandResult(
            ok=True,
            args=("codex", prompt),
            stdout=self.start_stdout,
        )

    def run_session_router(
        self,
        prompt: str,
        *,
        router_session_id: str | None = None,
    ) -> CommandResult:
        self.calls.append(("router", router_session_id, prompt))
        return CommandResult(
            ok=True,
            args=("codex", "resume", "--include-non-interactive", router_session_id or "", prompt),
            stdout=self.router_stdout,
        )


class BootstrapStartResult:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        session_id: str | None = None,
        router_session_id: str | None = None,
    ) -> None:
        self.ok = True
        self.args = ("codex",)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = 0
        if session_id is not None:
            self.session_id = session_id
        if router_session_id is not None:
            self.router_session_id = router_session_id


class FakeCommentRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def issue_comment(
        self,
        *,
        repo: str,
        issue_number: int,
        body: str,
    ) -> CommentPostResult:
        self.calls.append((repo, issue_number, body))
        return CommentPostResult(
            repo=repo,
            issue_number=issue_number,
            body=body,
            args=("gh", "issue", "comment", str(issue_number), "--repo", repo, "--body-file", "-"),
            posted=True,
            skipped=False,
            stdout="ok",
        )


def sample_record(
    *,
    issue_number: int = 7,
    prompt_kind: str = "worker",
    target_session_id: str = WORKER_SESSION_ID,
    trigger_fingerprint: str = "issue-7-body-sha256-abc123",
) -> QueueRecord:
    return QueueRecord(
        issue_number=issue_number,
        issue_url="https://github.com/example/project/issues/7",
        issue_title="first artifact",
        event_type="issue_body",
        trigger_fingerprint=trigger_fingerprint,
        target_session_id=target_session_id,
        prompt_kind=prompt_kind,
        body="What do you want to build?\nA small web app",
        source_id=None,
        sub_artifact_path="sub_artifact/001_first_artifact",
    )


def write_assignment_state(
    path: Path,
    *,
    router_session_id: str = ROUTER_SESSION_ID,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "router_session_id": router_session_id,
                "next_sub_artifact_number": 1,
                "assignments": [],
            }
        ),
        encoding="utf-8",
    )


class DispatchTest(unittest.TestCase):
    def test_queue_record_round_trip_and_prompt_wrapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.md"
            bootstrap_template = Path(tmp) / "bootstrap.md"
            bootstrap_template.write_text("# Session_router bootstrap v1\n", encoding="utf-8")
            record = sample_record()

            write_queue_record(queue_path, record)
            parsed = read_queue_record(queue_path)
            dispatch_prompt = build_dispatch_prompt(parsed)
            worker_prompt = build_worker_prompt(parsed)
            router_prompt = build_session_router_prompt(
                sample_record(prompt_kind="session_router", target_session_id=ROUTER_SESSION_ID)
            )
            bootstrap_prompt = build_session_router_bootstrap_prompt(
                repo_dir=Path(tmp),
                template_path=bootstrap_template,
            )

            self.assertEqual(parsed, record)
            self.assertEqual("worker", parsed.recipient_role)
            self.assertIn("ArtifactForge Dispatch Prompt v1", dispatch_prompt)
            self.assertIn("issue thread update", dispatch_prompt)
            self.assertIn("- recipient_role: worker", worker_prompt)
            self.assertIn(f"- target_session_id: {WORKER_SESSION_ID}", worker_prompt)
            self.assertIn("If your current session ID is not target_session_id", worker_prompt)
            self.assertIn("DISPATCH_V1_INPUT", worker_prompt)
            self.assertIn("issue-7-body-sha256-abc123", worker_prompt)
            self.assertIn('"recipient_role": "worker"', worker_prompt)
            self.assertIn('"target_session_visibility": "non_visible"', worker_prompt)
            self.assertIn('"human_gateway_contract"', worker_prompt)
            self.assertIn('"router_is_only_human_permission_surface": true', worker_prompt)
            self.assertIn('"worker_sessions_default_visibility": "non_visible"', worker_prompt)
            self.assertIn('"subagent_sessions_default_visibility": "non_visible"', worker_prompt)
            self.assertIn('"visible_child_session_requires_reason": true', worker_prompt)
            self.assertIn('"permission_requests_must_go_through_router": true', worker_prompt)
            self.assertIn(
                '"router_existing_capabilities_may_be_granted_to_subagents": true',
                worker_prompt,
            )
            self.assertIn(
                '"new_or_broader_capabilities_require_user_approval": true',
                worker_prompt,
            )
            self.assertIn('"target_thread_updates"', worker_prompt)
            self.assertIn('"target_events"', worker_prompt)
            self.assertIn('"worker_contract"', worker_prompt)
            self.assertIn('"process_issue_thread_update": true', worker_prompt)
            self.assertIn('"process_issue_event": true', worker_prompt)
            self.assertIn(
                '"may_spawn_subagents_for_minimal_implementation_and_verification_pairs": true',
                worker_prompt,
            )
            self.assertIn('"archive_pending_after_final_comment": true', worker_prompt)
            self.assertIn(
                '"archive_command_template": "mv .core_program/pending/xxx.md .core_program/archive/xxx.md"',
                worker_prompt,
            )
            self.assertIn('"post_comment_required": true', worker_prompt)
            self.assertIn('"push_required": true', worker_prompt)
            self.assertIn("- recipient_role: router", router_prompt)
            self.assertIn(f"- target_session_id: {ROUTER_SESSION_ID}", router_prompt)
            self.assertIn('"recipient_role": "router"', router_prompt)
            self.assertIn('"target_session_visibility": "visible"', router_prompt)
            self.assertIn('"target_thread_updates"', router_prompt)
            self.assertIn('"routing_contract"', router_prompt)
            self.assertIn('"request_for_human_dir": ".core_program/request_for_human"', router_prompt)
            self.assertIn('"check_request_for_human_empty_before_pending": true', router_prompt)
            self.assertIn('"write_request_for_human_memo_before_user_question": true', router_prompt)
            self.assertIn('"Pending fingerprints"', router_prompt)
            self.assertIn('"archive_pending_after_final_comment": true', router_prompt)
            self.assertIn("mv .core_program/pending/xxx.md .core_program/archive/xxx.md", router_prompt)
            self.assertIn('"router_posts_contract_violation_bug_report": true', router_prompt)
            self.assertIn(
                '"contract_violation_bug_report_default_status": "authentication_blocked"',
                router_prompt,
            )
            self.assertIn(
                '"contract_violation_bug_report_wrong_session_status": "reassign_required"',
                router_prompt,
            )
            self.assertIn('"workers_may_be_non_visible": true', router_prompt)
            self.assertIn('"subagents_may_be_non_visible": true', router_prompt)
            self.assertIn('"worker_sessions_default_visibility": "non_visible"', router_prompt)
            self.assertIn('"subagent_sessions_default_visibility": "non_visible"', router_prompt)
            self.assertIn('"visible_child_session_requires_reason": true', router_prompt)
            self.assertIn(
                '"router_may_grant_existing_capabilities_to_subagents": true',
                router_prompt,
            )
            self.assertIn("DISPATCH_V1_INPUT", router_prompt)
            self.assertIn("# Session_router bootstrap v1", bootstrap_prompt)
            self.assertIn("SESSION_ROUTER_BOOTSTRAP_V1_INPUT", bootstrap_prompt)

    def test_reassign_router_prompt_avoids_previous_thread_id(self) -> None:
        record = QueueRecord(
            issue_number=7,
            issue_url="https://github.com/example/project/issues/7",
            issue_title="first artifact",
            event_type="issue_body",
            trigger_fingerprint="issue-7-body-sha256-abc123",
            target_session_id=ROUTER_SESSION_ID,
            prompt_kind="session_router",
            body="wrong worker",
            source_id=None,
            sub_artifact_path="sub_artifact/001_first_artifact",
            previous_thread_id=WORKER_SESSION_ID,
            reassign_required=True,
        )

        prompt = build_session_router_prompt(record)

        self.assertIn("- recipient_role: router", prompt)
        self.assertIn(f'"previous_thread_id": "{WORKER_SESSION_ID}"', prompt)
        self.assertIn('"avoid_previous_thread_id": true', prompt)
        self.assertIn('"reassign_required": true', prompt)

    def test_bootstrap_session_router_starts_and_saves_new_router_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "assignment_state.json"
            template_path = root / "bootstrap.md"
            template_path.write_text("# Session_router bootstrap v1\n", encoding="utf-8")
            original_assignments = [
                {
                    "issue_number": 7,
                    "session_id": WORKER_SESSION_ID,
                    "status": "active",
                }
            ]
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "router_session_id": None,
                        "next_sub_artifact_number": 5,
                        "assignments": original_assignments,
                    }
                ),
                encoding="utf-8",
            )
            runner = FakeCodexRunner()

            session_id = bootstrap_session_router(
                assignment_state_path=state_path,
                repo_dir=root,
                runner=runner,
                template_path=template_path,
            )

            self.assertEqual(session_id, SELECTED_SESSION_ID)
            self.assertEqual([call[0] for call in runner.calls], ["start"])
            self.assertIn("SESSION_ROUTER_BOOTSTRAP_V1_INPUT", runner.calls[0][2])
            self.assertIn(str(root), runner.calls[0][2])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["router_session_id"], SELECTED_SESSION_ID)
            self.assertEqual(state["next_sub_artifact_number"], 5)
            self.assertEqual(state["assignments"], original_assignments)

    def test_bootstrap_session_router_reuses_existing_router_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "assignment_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "router_session_id": ROUTER_SESSION_ID,
                        "next_sub_artifact_number": 2,
                        "assignments": [],
                    }
                ),
                encoding="utf-8",
            )
            runner = FakeCodexRunner()

            session_id = bootstrap_session_router(
                assignment_state_path=state_path,
                runner=runner,
                template_path=root / "missing.md",
            )

            self.assertEqual(session_id, ROUTER_SESSION_ID)
            self.assertEqual(runner.calls, [])

    def test_bootstrap_session_router_rejects_invalid_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "assignment_state.json"
            template_path = root / "bootstrap.md"
            template_path.write_text("# Session_router bootstrap v1\n", encoding="utf-8")
            runner = FakeCodexRunner(start_stdout="not-a-session-id\n")

            with self.assertRaises(DispatchError):
                bootstrap_session_router(
                    assignment_state_path=state_path,
                    repo_dir=root,
                    runner=runner,
                    template_path=template_path,
                )

    def test_parse_bootstrap_session_id_accepts_bare_uuid_stdout(self) -> None:
        result = CommandResult(
            ok=True,
            args=("codex",),
            stdout=f"{SELECTED_SESSION_ID}\n",
        )

        self.assertEqual(parse_bootstrap_session_id(result), SELECTED_SESSION_ID)

    def test_parse_bootstrap_session_id_accepts_ready_banner_with_session_line(self) -> None:
        result = CommandResult(
            ok=True,
            args=("codex",),
            stdout=f"SESSION_ROUTER_READY\nSession ID: {SELECTED_SESSION_ID}\n",
        )

        self.assertEqual(parse_bootstrap_session_id(result), SELECTED_SESSION_ID)

    def test_parse_bootstrap_session_id_rejects_ready_without_session_id(self) -> None:
        result = CommandResult(
            ok=True,
            args=("codex",),
            stdout="SESSION_ROUTER_READY\n",
        )

        with self.assertRaises(DispatchError):
            parse_bootstrap_session_id(result)

    def test_parse_bootstrap_session_id_rejects_multiple_uuid_candidates(self) -> None:
        result = CommandResult(
            ok=True,
            args=("codex",),
            stdout=f"SESSION_ROUTER_READY\nSession ID: {SELECTED_SESSION_ID}\n",
            stderr=f"debug previous session {ROUTER_SESSION_ID}\n",
        )

        with self.assertRaises(DispatchError):
            parse_bootstrap_session_id(result)

    def test_bootstrap_session_router_prefers_result_session_id_attribute_over_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "assignment_state.json"
            template_path = root / "bootstrap.md"
            template_path.write_text("# Session_router bootstrap v1\n", encoding="utf-8")
            result = BootstrapStartResult(
                session_id=SELECTED_SESSION_ID,
                stdout=f"Session ID: {ROUTER_SESSION_ID}\n",
            )
            runner = FakeCodexRunner(start_result=result)

            session_id = bootstrap_session_router(
                assignment_state_path=state_path,
                repo_dir=root,
                runner=runner,
                template_path=template_path,
            )

            self.assertEqual(session_id, SELECTED_SESSION_ID)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["router_session_id"], SELECTED_SESSION_ID)

    def test_visible_launch_discovers_bootstrap_session_id_from_codex_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex_home"
            run_dir = root / "runs"
            sessions_dir = codex_home / "sessions" / "2026" / "07"

            def launcher(script_path: Path, terminal_app: str) -> CommandResult:
                self.assertEqual("Terminal", terminal_app)
                script_text = script_path.read_text(encoding="utf-8")
                self.assertIn("--no-alt-screen", script_text)
                self.assertIn("prompt.md", script_text)
                sessions_dir.mkdir(parents=True)
                jsonl = sessions_dir / f"{SELECTED_SESSION_ID}.jsonl"
                jsonl.write_text(
                    "\n".join(
                        (
                            json.dumps(
                                {
                                    "type": "session_meta",
                                    "payload": {"session_id": SELECTED_SESSION_ID},
                                }
                            ),
                            "SESSION_ROUTER_BOOTSTRAP_V1_INPUT",
                        )
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return CommandResult(ok=True, args=("open",), returncode=0)

            result = launch_visible_codex_session(
                "hello\nSESSION_ROUTER_BOOTSTRAP_V1_INPUT\n",
                repo_dir=root,
                role="session_router_bootstrap",
                marker="SESSION_ROUTER_BOOTSTRAP_V1_INPUT",
                run_dir_base=run_dir,
                launcher=launcher,
                wait_seconds=0,
                codex_home=codex_home,
            )

            self.assertTrue(result.ok)
            self.assertEqual(f"{SELECTED_SESSION_ID}\n", result.stdout)

    def test_discover_recent_codex_session_id_requires_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions_dir = root / "sessions"
            sessions_dir.mkdir()
            (sessions_dir / f"{SELECTED_SESSION_ID}.jsonl").write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"session_id": SELECTED_SESSION_ID},
                    }
                )
                + "\n"
                + "other prompt\n",
                encoding="utf-8",
            )

            session_id = discover_recent_codex_session_id(
                marker="SESSION_ROUTER_BOOTSTRAP_V1_INPUT",
                cutoff_time=0,
                timeout_seconds=0,
                codex_home=root,
            )

            self.assertIsNone(session_id)

    def test_wait_for_assignment_session_id_reads_router_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assignment_state.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "router_session_id": ROUTER_SESSION_ID,
                        "next_sub_artifact_number": 2,
                        "assignments": [
                            {
                                "issue_number": 7,
                                "session_id": SELECTED_SESSION_ID,
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                SELECTED_SESSION_ID,
                assignment_session_id(path, issue_number=7),
            )
            self.assertEqual(
                SELECTED_SESSION_ID,
                wait_for_assignment_session_id(path, issue_number=7, timeout_seconds=0),
            )

    def test_dispatch_legacy_worker_record_routes_to_router(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "worker.md"
            pending_dir = root / "pending"
            assignment_state = root / "assignment_state.json"
            write_assignment_state(assignment_state)
            write_queue_record(queue_path, sample_record())
            runner = FakeCodexRunner()

            result = dispatch_queue_file(
                queue_path,
                runner=runner,
                pending_dir=pending_dir,
                assignment_state_path=assignment_state,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.router_session_id, ROUTER_SESSION_ID)
            self.assertEqual(result.worker_session_id, ROUTER_SESSION_ID)
            self.assertTrue(result.queue_moved)
            self.assertFalse(queue_path.exists())
            self.assertTrue((pending_dir / "worker.md").exists())
            self.assertEqual(1, len(runner.calls))
            self.assertEqual(runner.calls[0][0], "router")
            self.assertEqual(runner.calls[0][1], ROUTER_SESSION_ID)
            self.assertIn("- recipient_role: router", runner.calls[0][2])
            self.assertIn('"source_recipient_role": "worker"', runner.calls[0][2])
            self.assertIn(f'"source_target_session_id": "{WORKER_SESSION_ID}"', runner.calls[0][2])
            self.assertIn("Read `.core_program/pending`", runner.calls[0][2])

    def test_dispatch_visibility_policy_keeps_router_as_only_visible_gateway(self) -> None:
        self.assertEqual(
            "visible",
            dispatch_session_visibility(
                sample_record(
                    prompt_kind="session_router",
                    target_session_id=ROUTER_SESSION_ID,
                )
            ),
        )
        self.assertEqual("non_visible", dispatch_session_visibility(sample_record()))

    def test_default_worker_dispatch_uses_visible_router(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "worker.md"
            pending_dir = root / "pending"
            assignment_state = root / "assignment_state.json"
            write_assignment_state(assignment_state)
            write_queue_record(queue_path, sample_record())
            calls: list[tuple[tuple[str, ...], Any]] = []

            def fake_default_runner(args: Any, input_text: Any) -> CommandResult:
                calls.append((tuple(args), input_text))
                return CommandResult(ok=True, args=tuple(args), returncode=0)

            with mock.patch.object(
                dispatch_module,
                "_default_runner",
                fake_default_runner,
            ), mock.patch.object(
                dispatch_module,
                "launch_visible_codex_session",
            ) as launch_visible:
                result = dispatch_queue_file(
                    queue_path,
                    runner=dispatch_module._default_runner,
                    repo_dir=root,
                    pending_dir=pending_dir,
                    assignment_state_path=assignment_state,
                )

        self.assertTrue(result.ok)
        self.assertEqual("visible", result.plan.session_visibility)
        self.assertEqual([], calls)
        launch_visible.assert_called_once()
        _, launch_kwargs = launch_visible.call_args
        self.assertEqual(root, Path(launch_kwargs["repo_dir"]))
        self.assertEqual(ROUTER_SESSION_ID, launch_kwargs["session_id"])
        self.assertEqual(f"resume_{ROUTER_SESSION_ID}", launch_kwargs["role"])

    def test_default_router_dispatch_uses_visible_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "router.md"
            pending_dir = root / "pending"
            write_queue_record(
                queue_path,
                sample_record(
                    prompt_kind="session_router",
                    target_session_id=ROUTER_SESSION_ID,
                ),
            )

            def fake_default_runner(args: Any, input_text: Any) -> CommandResult:
                raise AssertionError("router dispatch must use visible launch")

            with mock.patch.object(
                dispatch_module,
                "_default_runner",
                fake_default_runner,
            ), mock.patch.object(
                dispatch_module,
                "launch_visible_codex_session",
                return_value=CommandResult(ok=True, args=("open",), returncode=0),
            ) as launch_visible:
                result = dispatch_queue_file(
                    queue_path,
                    runner=dispatch_module._default_runner,
                    repo_dir=root,
                    pending_dir=pending_dir,
                )

        self.assertTrue(result.ok)
        self.assertEqual("visible", result.plan.session_visibility)
        launch_visible.assert_called_once()
        _, launch_kwargs = launch_visible.call_args
        self.assertEqual(root, Path(launch_kwargs["repo_dir"]))
        self.assertEqual(ROUTER_SESSION_ID, launch_kwargs["session_id"])
        self.assertEqual(f"resume_{ROUTER_SESSION_ID}", launch_kwargs["role"])

    def test_router_send_failure_restores_pending_to_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "worker.md"
            pending_dir = root / "pending"
            assignment_state = root / "assignment_state.json"
            write_assignment_state(assignment_state)
            write_queue_record(queue_path, sample_record())

            class BlockedRouterRunner(FakeCodexRunner):
                def run_session_router(
                    self,
                    prompt: str,
                    *,
                    router_session_id: str | None = None,
                ) -> CommandResult:
                    self.calls.append(("router", router_session_id, prompt))
                    return CommandResult(
                        ok=False,
                        args=("codex", "resume", router_session_id or "", prompt),
                        stderr="Error: stdout is not a terminal",
                        returncode=1,
                    )

            runner = BlockedRouterRunner()

            result = dispatch_queue_file(
                queue_path,
                runner=runner,
                repo_dir=root,
                pending_dir=pending_dir,
                assignment_state_path=assignment_state,
            )
            queue_exists = queue_path.exists()
            pending_files = sorted(pending_dir.glob("*.md")) if pending_dir.exists() else []

        self.assertFalse(result.ok)
        self.assertFalse(result.sent)
        self.assertFalse(result.moved_to_pending)
        self.assertEqual("visible", result.plan.session_visibility)
        self.assertIn("stdout is not a terminal", result.error or "")
        self.assertEqual(1, len(runner.calls))
        self.assertTrue(queue_exists)
        self.assertEqual([], pending_files)

    def test_pending_destination_uses_flat_numeric_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pending_dir = root / "pending"
            pending_dir.mkdir()
            queue_path = root / "queue" / "worker.md"
            (pending_dir / "worker.md").write_text("one", encoding="utf-8")
            (pending_dir / "worker.2.md").write_text("two", encoding="utf-8")
            (pending_dir / "worker.3.md").write_text("three", encoding="utf-8")

            destination = pending_destination(queue_path, pending_dir, WORKER_SESSION_ID)

        self.assertEqual("worker.4.md", destination.name)

    def test_dispatch_skips_stale_queue_when_fingerprint_is_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "worker.md"
            pending_dir = root / "pending"
            pending_dir.mkdir()
            record = sample_record()
            write_queue_record(queue_path, record)
            pending_path = pending_dir / f"{WORKER_SESSION_ID}_{record.trigger_fingerprint}.md"
            pending_path.write_text(
                "# ArtifactForge Issue Event\n\n"
                "## Routing\n"
                f"- target_session_id: {WORKER_SESSION_ID}\n\n"
                "## Issue Event\n"
                f"- trigger_fingerprint: {record.trigger_fingerprint}\n",
                encoding="utf-8",
            )
            runner = FakeCodexRunner()

            result = dispatch_queue_file(
                queue_path,
                runner=runner,
                pending_dir=pending_dir,
            )
            queue_exists = queue_path.exists()

        self.assertTrue(result.skipped)
        self.assertEqual("skipped", result.status)
        self.assertEqual("fingerprint_already_pending", result.skip_reason)
        self.assertFalse(result.sent)
        self.assertEqual([], runner.calls)
        self.assertTrue(queue_exists)

    def test_dispatch_skips_reassign_queue_when_handoff_is_already_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "router.md"
            pending_dir = root / "pending"
            pending_dir.mkdir()
            record = QueueRecord(
                issue_number=7,
                issue_url="https://github.com/example/project/issues/7",
                issue_title="first artifact",
                event_type="issue_body",
                trigger_fingerprint="issue-7-body-sha256-abc123",
                target_session_id=ROUTER_SESSION_ID,
                prompt_kind="session_router",
                body="wrong worker",
                source_id=None,
                sub_artifact_path="sub_artifact/001_first_artifact",
                previous_thread_id=WORKER_SESSION_ID,
                reassign_required=True,
            )
            write_queue_record(queue_path, record)
            pending_path = pending_dir / f"{ROUTER_SESSION_ID}_{record.trigger_fingerprint}.md"
            pending_path.write_text(
                "# ArtifactForge Issue Event\n\n"
                "## Routing\n"
                f"- target_session_id: {ROUTER_SESSION_ID}\n\n"
                "## Issue Event\n"
                f"- trigger_fingerprint: {record.trigger_fingerprint}\n",
                encoding="utf-8",
            )
            runner = FakeCodexRunner()

            result = dispatch_queue_file(
                queue_path,
                runner=runner,
                pending_dir=pending_dir,
            )
            queue_exists = queue_path.exists()

        self.assertTrue(result.skipped)
        self.assertEqual("skipped", result.status)
        self.assertEqual("reassign_handoff_already_pending", result.skip_reason)
        self.assertFalse(result.sent)
        self.assertEqual([], runner.calls)
        self.assertTrue(queue_exists)

    def test_dispatch_router_sends_only_router_prompt_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "router.md"
            pending_dir = root / "pending"
            assignment_state = root / "assignment_state.json"
            write_queue_record(
                queue_path,
                sample_record(prompt_kind="session_router", target_session_id=ROUTER_SESSION_ID),
            )
            runner = FakeCodexRunner()

            result = dispatch_queue_file(
                queue_path,
                runner=runner,
                pending_dir=pending_dir,
                assignment_state_path=assignment_state,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.router_session_id, ROUTER_SESSION_ID)
            self.assertEqual(result.worker_session_id, ROUTER_SESSION_ID)
            self.assertEqual([call[0] for call in runner.calls], ["router"])
            self.assertEqual(runner.calls[0][1], ROUTER_SESSION_ID)
            self.assertIn("- recipient_role: router", runner.calls[0][2])
            self.assertIn('"recipient_role": "router"', runner.calls[0][2])
            self.assertIn('"dispatcher_will_not_resume_worker_sessions": true', runner.calls[0][2])
            self.assertTrue((pending_dir / "router.md").exists())
            self.assertFalse(assignment_state.exists())

    def test_dispatch_queue_limit_processes_only_one_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_dir = root / "queue"
            pending_dir = root / "pending"
            write_queue_record(
                queue_dir / "001.md",
                sample_record(
                    issue_number=1,
                    prompt_kind="session_router",
                    target_session_id=ROUTER_SESSION_ID,
                    trigger_fingerprint="issue-1-body-sha256-one",
                ),
            )
            write_queue_record(
                queue_dir / "002.md",
                sample_record(
                    issue_number=2,
                    prompt_kind="session_router",
                    target_session_id=ROUTER_SESSION_ID,
                    trigger_fingerprint="issue-2-body-sha256-two",
                ),
            )
            runner = FakeCodexRunner()

            results = dispatch_queue(
                queue_dir,
                pending_dir=pending_dir,
                runner=runner,
                limit=1,
            )

            self.assertEqual(1, len(results))
            self.assertEqual(1, len(runner.calls))
            self.assertFalse((queue_dir / "001.md").exists())
            self.assertTrue((queue_dir / "002.md").exists())
            self.assertTrue((pending_dir / "001.md").exists())

    def test_pending_worker_session_does_not_block_router_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "new.md"
            pending_dir = root / "pending"
            assignment_state = root / "assignment_state.json"
            write_assignment_state(assignment_state)
            write_queue_record(
                pending_dir / "existing.md",
                sample_record(
                    trigger_fingerprint="issue-6-body-sha256-existing",
                    target_session_id=WORKER_SESSION_ID,
                ),
            )
            write_queue_record(
                queue_path,
                sample_record(
                    trigger_fingerprint="issue-7-body-sha256-new",
                    target_session_id=WORKER_SESSION_ID,
                ),
            )
            runner = FakeCodexRunner()

            result = dispatch_queue_file(
                queue_path,
                pending_dir=pending_dir,
                runner=runner,
                assignment_state_path=assignment_state,
            )

            self.assertTrue(result.sent)
            self.assertEqual(ROUTER_SESSION_ID, result.router_session_id)
            self.assertEqual(1, len(runner.calls))
            self.assertFalse(queue_path.exists())

    def test_router_session_is_deferred_when_router_pending_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "router-new.md"
            pending_dir = root / "pending"
            write_queue_record(
                pending_dir / "router-existing.md",
                sample_record(
                    prompt_kind="session_router",
                    target_session_id=ROUTER_SESSION_ID,
                    trigger_fingerprint="issue-8-body-sha256-existing",
                ),
            )
            write_queue_record(
                queue_path,
                sample_record(
                    prompt_kind="session_router",
                    target_session_id=ROUTER_SESSION_ID,
                    trigger_fingerprint="issue-9-body-sha256-new",
                ),
            )
            runner = FakeCodexRunner()

            result = dispatch_queue_file(
                queue_path,
                pending_dir=pending_dir,
                runner=runner,
            )

            self.assertTrue(result.skipped)
            self.assertEqual("session_has_unresolved_pending", result.skip_reason)
            self.assertEqual([], runner.calls)
            self.assertTrue(queue_path.exists())

    def test_dispatch_queue_batches_multiple_items_into_one_router_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_dir = root / "queue"
            pending_dir = root / "pending"
            write_queue_record(
                queue_dir / "001.md",
                sample_record(
                    issue_number=1,
                    prompt_kind="session_router",
                    trigger_fingerprint="issue-1-body-sha256-one",
                    target_session_id=ROUTER_SESSION_ID,
                ),
            )
            write_queue_record(
                queue_dir / "002.md",
                sample_record(
                    issue_number=2,
                    prompt_kind="session_router",
                    trigger_fingerprint="issue-2-body-sha256-two",
                    target_session_id=ROUTER_SESSION_ID,
                ),
            )
            runner = FakeCodexRunner()

            results = dispatch_queue(
                queue_dir,
                pending_dir=pending_dir,
                runner=runner,
                parallel=2,
            )
            summary = dispatch_module.dispatch_results_to_dict(results)

            self.assertEqual(2, len(results))
            self.assertEqual(1, len(runner.calls))
            self.assertEqual(0, summary["deferred_count"])
            self.assertTrue(results[0].sent)
            self.assertTrue(results[1].sent)
            self.assertEqual("router", summary["items"][0]["recipient_role"])
            self.assertEqual("router", summary["items"][1]["recipient_role"])
            self.assertIn("SESSION_ROUTER_ORCHESTRATOR_V1_INPUT", runner.calls[0][2])
            self.assertIn(".core_program/request_for_human", runner.calls[0][2])
            self.assertIn('"check_request_for_human_empty_before_pending": true', runner.calls[0][2])
            self.assertIn('"write_request_for_human_memo_before_user_question": true', runner.calls[0][2])
            self.assertIn('"archive_pending_after_final_comment": true', runner.calls[0][2])
            self.assertIn("mv .core_program/pending/xxx.md .core_program/archive/xxx.md", runner.calls[0][2])
            self.assertIn('"router_posts_contract_violation_bug_report": true', runner.calls[0][2])
            self.assertIn(
                '"contract_violation_bug_report_default_status": "authentication_blocked"',
                runner.calls[0][2],
            )
            self.assertIn("issue-1-body-sha256-one", runner.calls[0][2])
            self.assertIn("issue-2-body-sha256-two", runner.calls[0][2])
            self.assertFalse((queue_dir / "001.md").exists())
            self.assertFalse((queue_dir / "002.md").exists())
            self.assertTrue((pending_dir / "001.md").exists())
            self.assertTrue((pending_dir / "002.md").exists())

    def test_dispatch_queue_batches_legacy_worker_records_to_router(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_dir = root / "queue"
            pending_dir = root / "pending"
            assignment_state = root / "assignment_state.json"
            write_assignment_state(assignment_state)
            write_queue_record(
                queue_dir / "001.md",
                sample_record(
                    issue_number=1,
                    trigger_fingerprint="issue-1-body-sha256-one",
                    target_session_id=WORKER_SESSION_ID,
                ),
            )
            write_queue_record(
                queue_dir / "002.md",
                sample_record(
                    issue_number=2,
                    trigger_fingerprint="issue-2-body-sha256-two",
                    target_session_id=SELECTED_SESSION_ID,
                ),
            )
            runner = FakeCodexRunner()

            results = dispatch_queue(
                queue_dir,
                pending_dir=pending_dir,
                runner=runner,
                assignment_state_path=assignment_state,
            )

            self.assertEqual(2, len(results))
            self.assertEqual(1, len(runner.calls))
            self.assertTrue(results[0].sent)
            self.assertTrue(results[1].sent)
            self.assertIn("SESSION_ROUTER_ORCHESTRATOR_V1_INPUT", runner.calls[0][2])
            self.assertFalse((queue_dir / "001.md").exists())
            self.assertFalse((queue_dir / "002.md").exists())
            self.assertTrue((pending_dir / "001.md").exists())
            self.assertTrue((pending_dir / "002.md").exists())
            pending_text = (pending_dir / "001.md").read_text(encoding="utf-8")
            self.assertIn("- recipient_role: router", pending_text)
            self.assertIn(f"- target_session_id: {ROUTER_SESSION_ID}", pending_text)

    def test_dispatch_queue_claims_to_inflight_then_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_dir = root / "queue"
            inflight_dir = root / "inflight"
            pending_dir = root / "pending"
            locks_dir = root / "locks"
            write_queue_record(
                queue_dir / "001.md",
                sample_record(
                    prompt_kind="session_router",
                    target_session_id=ROUTER_SESSION_ID,
                ),
            )
            runner = FakeCodexRunner()

            results = dispatch_queue(
                queue_dir,
                inflight_dir=inflight_dir,
                pending_dir=pending_dir,
                locks_dir=locks_dir,
                runner=runner,
            )

            self.assertEqual(1, len(results))
            self.assertTrue(results[0].sent)
            self.assertFalse((queue_dir / "001.md").exists())
            self.assertFalse((inflight_dir / "001.md").exists())
            self.assertTrue((pending_dir / "001.md").exists())
            self.assertEqual([], sorted(locks_dir.glob("*.lock")))

    def test_dispatch_queue_restores_claim_when_session_lock_is_busy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_dir = root / "queue"
            inflight_dir = root / "inflight"
            pending_dir = root / "pending"
            locks_dir = root / "locks"
            write_queue_record(
                queue_dir / "001.md",
                sample_record(
                    prompt_kind="session_router",
                    target_session_id=ROUTER_SESSION_ID,
                ),
            )
            lock_path = acquire_session_lock(ROUTER_SESSION_ID, locks_dir=locks_dir)

            try:
                results = dispatch_queue(
                    queue_dir,
                    inflight_dir=inflight_dir,
                    pending_dir=pending_dir,
                    locks_dir=locks_dir,
                    runner=FakeCodexRunner(),
                    session_lock_timeout_seconds=0,
                )
            finally:
                release_file_lock(lock_path)

            self.assertEqual(1, len(results))
            self.assertIn("lock already held", results[0].error or "")
            self.assertTrue((queue_dir / "001.md").exists())
            self.assertFalse((inflight_dir / "001.md").exists())
            self.assertFalse((pending_dir / "001.md").exists())

    def test_claim_queue_file_uses_unique_inflight_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_file = root / "queue" / "001.md"
            inflight_dir = root / "inflight"
            locks_dir = root / "locks"
            write_queue_record(queue_file, sample_record())
            inflight_dir.mkdir(parents=True)
            (inflight_dir / "001.md").write_text("existing", encoding="utf-8")

            claim = claim_queue_file(
                queue_file,
                inflight_dir=inflight_dir,
                locks_dir=locks_dir,
            )

            self.assertIsNotNone(claim)
            assert claim is not None
            self.assertEqual(inflight_dir / "001.2.md", claim.claimed_path)
            self.assertFalse(queue_file.exists())
            self.assertTrue((inflight_dir / "001.md").exists())
            self.assertTrue((inflight_dir / "001.2.md").exists())

    def test_router_output_must_be_exactly_one_session_id_line(self) -> None:
        valid = validate_session_router_output(f"{SELECTED_SESSION_ID}\n")
        invalid = validate_session_router_output(f"{SELECTED_SESSION_ID}\nextra\n")

        self.assertTrue(valid.valid)
        self.assertEqual(valid.session_id, SELECTED_SESSION_ID)
        self.assertFalse(invalid.valid)
        self.assertEqual(invalid.error, "output must be one line")

    def test_dry_run_does_not_move_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue" / "worker.md"
            pending_dir = root / "pending"
            write_queue_record(queue_path, sample_record())

            result = dispatch_queue_file(queue_path, dry_run=True, pending_dir=pending_dir)

            self.assertEqual(result.status, "planned")
            self.assertFalse(result.queue_moved)
            self.assertTrue(queue_path.exists())
            self.assertFalse((pending_dir / "worker.md").exists())

    def test_comment_posting_is_explicit_only(self) -> None:
        runner = FakeCommentRunner()
        body = append_marker_footer(
            "Done.",
            session_id=WORKER_SESSION_ID,
            trigger_fingerprint="issue-7-body-sha256-abc123",
            status="done",
        )

        planned = post_issue_comment(
            repo="example/project",
            issue_number=7,
            body=body,
            runner=runner,
        )
        posted = post_issue_comment(
            repo="example/project",
            issue_number=7,
            body=body,
            post_comments=True,
            runner=runner,
        )

        self.assertTrue(planned.skipped)
        self.assertFalse(planned.posted)
        self.assertEqual(runner.calls, [("example/project", 7, body)])
        self.assertTrue(posted.posted)


if __name__ == "__main__":
    unittest.main()
