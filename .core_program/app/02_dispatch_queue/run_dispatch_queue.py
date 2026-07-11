#!/usr/bin/env python3
"""Dispatch ArtifactForge queue files to Codex sessions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[2]
LIB_DIR = CORE_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.dispatch import (  # noqa: E402
    DEFAULT_ARCHIVE_DIR,
    DEFAULT_CODEX_BIN,
    DEFAULT_INFLIGHT_DIR,
    DEFAULT_LOCKS_DIR,
    DEFAULT_PENDING_DIR,
    DEFAULT_PENDING_STATE_PATH,
    DEFAULT_QUEUE_DIR,
    DEFAULT_ASSIGNMENT_STATE_PATH,
    REPO_ROOT,
    dispatch_queue,
    dispatch_results_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dispatch .core_program queue files.")
    parser.add_argument("--queue-dir", default=str(DEFAULT_QUEUE_DIR))
    parser.add_argument("--inflight-dir", default=str(DEFAULT_INFLIGHT_DIR))
    parser.add_argument("--pending-dir", default=str(DEFAULT_PENDING_DIR))
    parser.add_argument("--pending-state", default=str(DEFAULT_PENDING_STATE_PATH))
    parser.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR))
    parser.add_argument("--locks-dir", default=str(DEFAULT_LOCKS_DIR))
    parser.add_argument("--repo-dir", default=str(REPO_ROOT))
    parser.add_argument("--codex-bin", default=str(DEFAULT_CODEX_BIN))
    parser.add_argument(
        "--assignment-state",
        default=str(DEFAULT_ASSIGNMENT_STATE_PATH),
        help="assignment_state.json path used to read the visible Session_router ID",
    )
    parser.add_argument("--limit", type=int, default=None, help="dispatch at most this many queue files")
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="compatibility option; router dispatch remains serialized",
    )
    parser.add_argument("--dry-run", action="store_true", help="show dispatch plan only")
    parser.add_argument(
        "--keep-queue",
        action="store_true",
        help="send prompts but do not move queue files to pending",
    )
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = dispatch_queue(
        args.queue_dir,
        inflight_dir=args.inflight_dir,
        pending_dir=args.pending_dir,
        pending_state_path=args.pending_state,
        archive_dir=args.archive_dir,
        locks_dir=args.locks_dir,
        repo_dir=args.repo_dir,
        codex_bin=args.codex_bin,
        dry_run=args.dry_run,
        move_to_pending=not args.keep_queue,
        assignment_state_path=args.assignment_state,
        limit=args.limit,
        parallel=args.parallel,
    )
    summary = dispatch_results_to_dict(results)
    summary["mode"] = "dry-run" if args.dry_run else "real"
    summary["effects"] = {
        "codex_sessions": "not_started"
        if args.dry_run
        else "visible_session_router_prompt_sent_when_successful",
        "queue_files": "not_moved"
        if args.dry_run or args.keep_queue
        else "moved_to_pending_before_router_send_when_successful",
        "inflight_files": "not_used" if args.dry_run else "claimed_before_dispatch",
        "session_busy_guard": "checked",
        "session_locks": "not_used" if args.dry_run else "router_session_id_serialized",
        "router_invocations": "planned_one_per_run" if args.dry_run else "one_per_run_default",
        "assignment_state": "read_for_router_target",
        "github_comments": "not_posted",
    }
    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if any(result.error for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
