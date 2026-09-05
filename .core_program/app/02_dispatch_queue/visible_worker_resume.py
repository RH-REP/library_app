#!/usr/bin/env python3
"""Resume a visible Codex worker session with a queue-state worker prompt."""

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
    DEFAULT_CODEX_BIN,
    REPO_ROOT,
    SESSION_ID_RE,
    build_worker_prompt,
    launch_visible_codex_session,
    read_queue_record,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send one ArtifactForge pending/human_wating worker prompt to a visible Codex session."
    )
    parser.add_argument("--pending-path", required=True, help="Pending or human_wating markdown record to dispatch")
    parser.add_argument("--session-id", required=True, help="Target Codex worker session ID")
    parser.add_argument("--role", default="visible_worker_resume", help="Visible launch role label")
    parser.add_argument("--repo-dir", default=str(REPO_ROOT), help="Repository root")
    parser.add_argument("--codex-bin", default=str(DEFAULT_CODEX_BIN), help="Codex executable")
    parser.add_argument(
        "--extra-instructions",
        default="",
        help="Additional router instructions appended to the generated worker prompt",
    )
    parser.add_argument("--compact", action="store_true", help="Print compact JSON")
    return parser


def _resolve_pending_path(value: str, repo_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo_dir / path
    path = path.resolve()
    allowed_dirs = {
        (repo_dir / ".core_program" / "pending").resolve(),
        (repo_dir / ".core_program" / "human_wating").resolve(),
    }
    if path.parent not in allowed_dirs:
        allowed_text = ", ".join(str(item) for item in sorted(allowed_dirs))
        raise SystemExit(f"record path must be directly under one of {allowed_text}: {path}")
    if not path.exists():
        raise SystemExit(f"pending path does not exist: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_dir = Path(args.repo_dir).expanduser().resolve()
    session_id = args.session_id.strip()
    if not SESSION_ID_RE.fullmatch(session_id):
        raise SystemExit(f"invalid session ID: {session_id}")

    pending_path = _resolve_pending_path(args.pending_path, repo_dir)
    record = read_queue_record(pending_path)
    prompt = build_worker_prompt(record, session_id=session_id, repo_dir=repo_dir)
    if args.extra_instructions.strip():
        prompt = (
            f"{prompt.rstrip()}\n\n"
            "ROUTER_ADDITIONAL_WORKER_INSTRUCTIONS\n"
            "```md\n"
            f"{args.extra_instructions.strip()}\n"
            "```\n"
        )
    result = launch_visible_codex_session(
        prompt,
        repo_dir=repo_dir,
        codex_bin=args.codex_bin,
        role=args.role,
        session_id=session_id,
    )
    summary = {
        "ok": result.ok,
        "pending_path": str(pending_path),
        "returncode": result.returncode,
        "session_id": session_id,
        "stderr": result.stderr,
        "stdout": result.stdout,
    }
    if args.compact:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.ok else result.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
