#!/usr/bin/env python3
"""Resume the best matching ArtifactForge router or worker session."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[2]
LIB_DIR = CORE_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.session_resume import (  # noqa: E402
    REPO_ROOT,
    DEFAULT_CODEX_BIN,
    DEFAULT_PENDING_DIR,
    human_waiting_dir_for,
    plan_session_resume,
    resume_session,
    session_resume_plan_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select a router or worker session and resume it with Codex."
    )
    parser.add_argument("--repo-dir", default=str(REPO_ROOT))
    parser.add_argument("--codex-bin", default=str(DEFAULT_CODEX_BIN))
    parser.add_argument("--pending-dir", default=str(DEFAULT_PENDING_DIR))
    parser.add_argument(
        "--human-wating-dir",
        default=None,
        help="override the human_wating directory; defaults to sibling of pending-dir",
    )
    parser.add_argument(
        "--request-for-human-dir",
        default=None,
        help="override the request_for_human directory; defaults to .core_program/request_for_human",
    )
    parser.add_argument(
        "--pending-state",
        default=None,
        help="optional pending_state.json used to enrich human_wating summaries",
    )
    parser.add_argument("--dry-run", action="store_true", help="show the selected plan only")
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    return parser


def human_summary(summary: dict[str, object]) -> str:
    lines = [
        "ArtifactForge session resume",
        f"mode: {summary.get('mode')}",
        f"selected_session_id: {summary.get('selected_session_id') or '(none)'}",
        f"recipient_role: {summary.get('recipient_role') or '(none)'}",
        f"session_visibility: {summary.get('session_visibility') or '(none)'}",
        f"source_kind: {summary.get('source_kind')}",
        f"reason: {summary.get('reason')}",
        f"request_for_human_count: {summary.get('request_for_human_count')}",
        f"human_waiting_count: {summary.get('human_waiting_count')}",
        f"pending_count: {summary.get('pending_count')}",
    ]
    if summary.get("selected_pending_path"):
        lines.append(f"selected_pending_path: {summary['selected_pending_path']}")
    if summary.get("worker_session_ids"):
        lines.append(
            "worker_session_ids: " + ", ".join(summary["worker_session_ids"])
        )
    if summary.get("command"):
        lines.append("command: " + " ".join(summary["command"]))
    if summary.get("prompt_preview"):
        lines.append("")
        lines.append("prompt_preview:")
        lines.append(str(summary["prompt_preview"]))
    if summary.get("resume_returncode") is not None:
        lines.append(f"resume_returncode: {summary['resume_returncode']}")
    if summary.get("resume_stderr"):
        lines.append(f"resume_stderr: {summary['resume_stderr']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    human_wating_dir = (
        args.human_wating_dir
        if args.human_wating_dir is not None
        else str(human_waiting_dir_for(args.pending_dir))
    )
    plan = plan_session_resume(
        repo_dir=args.repo_dir,
        pending_dir=args.pending_dir,
        request_for_human_dir=args.request_for_human_dir,
        human_waiting_dir=human_wating_dir,
        pending_state_path=args.pending_state,
        codex_bin=args.codex_bin,
    )
    summary = session_resume_plan_to_dict(plan)
    summary["mode"] = "dry-run" if args.dry_run else "real"
    summary["effects"] = {
        "codex_sessions": "not_started" if args.dry_run or plan.session_id is None else "resumed",
        "selection": plan.recipient_role or "none",
    }

    resume_result = None
    if not args.dry_run and plan.session_id is not None and plan.prompt is not None:
        resume_result = resume_session(
            plan,
            repo_dir=args.repo_dir,
            codex_bin=args.codex_bin,
        )
        summary["resume_returncode"] = getattr(resume_result, "returncode", None)
        summary["resume_stdout"] = getattr(resume_result, "stdout", "")
        summary["resume_stderr"] = getattr(resume_result, "stderr", "")
        summary["effects"]["codex_sessions"] = "resumed" if getattr(resume_result, "ok", False) else "failed"

    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(human_summary(summary))

    if resume_result is not None and not getattr(resume_result, "ok", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

