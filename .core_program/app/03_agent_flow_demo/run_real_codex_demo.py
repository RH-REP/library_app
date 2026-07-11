#!/usr/bin/env python3
"""Prepare and optionally dispatch the real-Codex ArtifactForge agent-flow demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional


CORE_DIR = Path(__file__).resolve().parents[2]
LIB_DIR = CORE_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.agent_flow_demo import (  # noqa: E402
    DEFAULT_REAL_CODEX_FIXTURE_PATH,
    DEFAULT_REAL_CODEX_WORK_DIR,
    real_codex_human_summary,
    run_real_codex_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an isolated real-Codex demo for router/worker permission flow."
    )
    parser.add_argument(
        "--fixture",
        default=str(DEFAULT_REAL_CODEX_FIXTURE_PATH),
        help="local issue fixture used to create the demo queue",
    )
    parser.add_argument(
        "--work-dir",
        default=str(DEFAULT_REAL_CODEX_WORK_DIR),
        help="isolated demo state directory for queue/pending/archive/assignment_state",
    )
    parser.add_argument(
        "--router-session-id",
        default=None,
        help="existing visible Session_router ID to use",
    )
    parser.add_argument(
        "--bootstrap-router",
        action="store_true",
        help="start a visible Session_router if assignment_state has no router_session_id",
    )
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help="send the prepared queue to real Codex",
    )
    parser.add_argument(
        "--dry-run-dispatch",
        action="store_true",
        help="plan dispatch without sending to Codex",
    )
    parser.add_argument(
        "--overwrite-queue",
        action="store_true",
        help="overwrite an existing demo queue file",
    )
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    parser.add_argument("--json", action="store_true", help="print pretty JSON")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_real_codex_demo(
        fixture_path=args.fixture,
        work_dir=args.work_dir,
        router_session_id=args.router_session_id,
        bootstrap_router=args.bootstrap_router,
        dispatch=args.dispatch or args.dry_run_dispatch,
        dry_run_dispatch=args.dry_run_dispatch,
        overwrite_queue=args.overwrite_queue,
        codex_bin=args.codex_bin,
    )
    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(real_codex_human_summary(summary))
    return 0 if summary.get("status") != "router_session_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
