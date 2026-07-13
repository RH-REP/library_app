#!/usr/bin/env python3
"""Resume a selected worker session by index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[2]
LIB_DIR = CORE_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from artifactforge_dispatch_v1.session_resume import DEFAULT_CODEX_BIN, REPO_ROOT  # noqa: E402
from artifactforge_dispatch_v1.worker_list import (  # noqa: E402
    collect_worker_session_catalog,
    human_summary as worker_list_human_summary,
)
from artifactforge_dispatch_v1.worker_resume import (  # noqa: E402
    plan_worker_resume_by_index,
    resume_worker_session,
    human_summary,
    worker_resume_plan_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resume a managed worker session selected by index."
    )
    parser.add_argument("--repo-dir", default=str(REPO_ROOT))
    parser.add_argument("--codex-bin", default=str(DEFAULT_CODEX_BIN))
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
    parser.add_argument(
        "--index",
        type=int,
        default=None,
        help="1-based worker list index to resume",
    )
    parser.add_argument("--dry-run", action="store_true", help="show the selected plan only")
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    return parser


def _resolve_index(args: argparse.Namespace, catalog_summary: str) -> int:
    if args.index is not None:
        return args.index
    if args.compact:
        raise SystemExit("--index is required when --compact is set")
    print(catalog_summary)
    if not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
        raise SystemExit("worker index is required when stdin is not interactive")
    raw = input("Select worker index to resume: ").strip()
    if not raw:
        raise SystemExit("worker index is required")
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"invalid worker index: {raw}") from exc


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
    selected_index = _resolve_index(args, worker_list_human_summary(catalog))
    plan = plan_worker_resume_by_index(
        index=selected_index,
        repo_dir=args.repo_dir,
        assignment_state_path=args.assignment_state,
        pending_dir=args.pending_dir,
        request_for_human_dir=args.request_for_human_dir,
        human_waiting_dir=args.human_wating_dir,
        pending_state_path=args.pending_state,
        codex_bin=args.codex_bin,
        catalog=catalog,
    )
    summary = worker_resume_plan_to_dict(plan)
    summary["mode"] = "dry-run" if args.dry_run else "real"
    summary["effects"] = {
        "codex_sessions": "not_started"
        if args.dry_run
        else "resumed",
        "selection": "worker_index",
    }

    resume_result = None
    if not args.dry_run:
        resume_result = resume_worker_session(
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
        print(human_summary(plan))

    if resume_result is not None and not getattr(resume_result, "ok", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
