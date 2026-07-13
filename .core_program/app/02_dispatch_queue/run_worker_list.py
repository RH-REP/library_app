#!/usr/bin/env python3
"""List ArtifactForge worker sessions with indexes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[2]
LIB_DIR = CORE_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.worker_list import (  # noqa: E402
    REPO_ROOT,
    collect_worker_session_catalog,
    human_summary,
    worker_session_catalog_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show the current managed worker sessions with indexes."
    )
    parser.add_argument("--repo-dir", default=str(REPO_ROOT))
    parser.add_argument(
        "--assignment-state",
        default=None,
        help="override assignment_state.json; defaults to .core_program/assignment_state.json under repo-dir",
    )
    parser.add_argument(
        "--pending-dir",
        default=None,
        help="override the pending directory; defaults to .core_program/pending under repo-dir",
    )
    parser.add_argument("--human-wating-dir", default=None)
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
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog = collect_worker_session_catalog(
        repo_dir=args.repo_dir,
        assignment_state_path=args.assignment_state,
        pending_dir=args.pending_dir,
        request_for_human_dir=args.request_for_human_dir,
        human_waiting_dir=args.human_wating_dir,
        pending_state_path=args.pending_state,
    )
    summary = worker_session_catalog_to_dict(catalog)
    summary["mode"] = "compact" if args.compact else "human"
    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(human_summary(catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
