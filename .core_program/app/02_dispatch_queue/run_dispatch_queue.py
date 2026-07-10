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
    DEFAULT_PENDING_DIR,
    DEFAULT_QUEUE_DIR,
    DEFAULT_ASSIGNMENT_STATE_PATH,
    REPO_ROOT,
    dispatch_queue,
    dispatch_results_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dispatch .core_program queue files.")
    parser.add_argument("--queue-dir", default=str(DEFAULT_QUEUE_DIR))
    parser.add_argument("--pending-dir", default=str(DEFAULT_PENDING_DIR))
    parser.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR))
    parser.add_argument("--repo-dir", default=str(REPO_ROOT))
    parser.add_argument("--codex-bin", default=str(DEFAULT_CODEX_BIN))
    parser.add_argument(
        "--assignment-state",
        default=str(DEFAULT_ASSIGNMENT_STATE_PATH),
        help="Compatibility option; router-role sessions update assignment_state.json",
    )
    parser.add_argument("--limit", type=int, default=None, help="dispatch at most this many queue files")
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
        pending_dir=args.pending_dir,
        archive_dir=args.archive_dir,
        repo_dir=args.repo_dir,
        codex_bin=args.codex_bin,
        dry_run=args.dry_run,
        move_to_pending=not args.keep_queue,
        assignment_state_path=None if args.dry_run else args.assignment_state,
        limit=args.limit,
    )
    summary = dispatch_results_to_dict(results)
    summary["mode"] = "dry-run" if args.dry_run else "real"
    summary["effects"] = {
        "codex_sessions": "not_started" if args.dry_run else "prompt_sent_when_successful",
        "queue_files": "not_moved" if args.dry_run or args.keep_queue else "moved_to_pending_when_successful",
        "assignment_state": "not_written_by_dispatcher",
        "github_comments": "not_posted",
    }
    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if any(result.error for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
