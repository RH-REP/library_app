#!/usr/bin/env python3
"""Run the local ArtifactForge router/worker/subagent demo."""

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
    DEFAULT_DEMO_QUEUE_PATH,
    human_summary,
    run_agent_flow_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local fake-runner demo of ArtifactForge agent flow."
    )
    parser.add_argument(
        "--queue-file",
        default=str(DEFAULT_DEMO_QUEUE_PATH),
        help="sample queue markdown to execute",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="directory for demo queue, pending, assignment_state, and transcript",
    )
    parser.add_argument(
        "--permission",
        choices=("grant", "deny"),
        default="grant",
        help="simulate whether Session_router grants the subagent permission",
    )
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    parser.add_argument("--json", action="store_true", help="print pretty JSON")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_agent_flow_demo(
        queue_file=args.queue_file,
        work_dir=args.work_dir,
        permission_mode=args.permission,
    )
    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(human_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
