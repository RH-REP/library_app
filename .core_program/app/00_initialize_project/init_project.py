#!/usr/bin/env python3
"""Initialize a user project repository from ArtifactForge.

The command is intentionally interactive by default. It asks for the new
project repository name and the README first-issue questions, then creates the
GitHub repository, configures remotes, initializes local runtime state, and
posts the first issue.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    # 日本語などの対話編集を安定させるため。
    import readline  # noqa: F401
except ImportError:
    pass


REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = REPO_ROOT / ".core_program"
ASSIGNMENT_STATE_PATH = CORE_DIR / "assignment_state.json"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
PROJECT_TRACKING_IGNORE_PATTERNS = {"sub_artifact/*", "issue_log/*"}
PROJECT_GITIGNORE_COMMIT_MESSAGE = "Enable ArtifactForge project artifact tracking"


class InitError(RuntimeError):
    pass


@dataclass(frozen=True)
class FirstIssueAnswers:
    what: str
    process: str
    goal: str
    option_why: str = ""
    option_materials: str = ""
    option_avoid: str = ""


def run_command(
    args: list[str],
    *,
    cwd: Path = REPO_ROOT,
    input_text: str | None = None,
) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise InitError(f"command failed: {' '.join(args)}\n{detail}")
    return result.stdout.strip()


def prompt_text(label: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    return ""


def prompt_required(label: str, *, default: str | None = None) -> str:
    while True:
        value = prompt_text(label, default=default)
        if value:
            return value
        print("入力してください。")


def confirm(label: str, *, default_yes: bool = True, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    suffix = "[Y/n]" if default_yes else "[y/N]"
    value = input(f"{label} {suffix}: ").strip().lower()
    if not value:
        return default_yes
    return value in {"y", "yes"}


def normalize_repo_name(value: str) -> str:
    cleaned = value.strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", cleaned):
        raise InitError(
            "project name must contain only letters, numbers, dot, underscore, or hyphen"
        )
    return cleaned


def normalize_owner(value: str) -> str:
    cleaned = value.strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", cleaned):
        raise InitError(
            "GitHub owner/org must contain only letters, numbers, dot, underscore, or hyphen"
        )
    return cleaned


def github_https_url(owner: str, project_name: str) -> str:
    return f"https://github.com/{owner}/{project_name}"


def repo_full_name(owner: str, project_name: str) -> str:
    return f"{owner}/{project_name}"


def remote_names() -> set[str]:
    output = run_command(["git", "remote"])
    return {line.strip() for line in output.splitlines() if line.strip()}


def get_remote_url(name: str, *, push: bool = False) -> str | None:
    args = ["git", "remote", "get-url"]
    if push:
        args.append("--push")
    args.append(name)
    result = subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def initialization_state() -> dict[str, object]:
    names = remote_names()
    origin_url = get_remote_url("origin") if "origin" in names else None
    upstream_url = get_remote_url("upstream") if "upstream" in names else None
    upstream_push = get_remote_url("upstream", push=True) if "upstream" in names else None
    assignment_state_exists = ASSIGNMENT_STATE_PATH.exists()
    initialized = bool(
        origin_url
        and upstream_url
        and upstream_push == "DISABLED"
        and assignment_state_exists
    )
    return {
        "initialized": initialized,
        "origin": origin_url,
        "upstream": upstream_url,
        "upstream_push": upstream_push,
        "assignment_state_exists": assignment_state_exists,
    }


def print_initialization_state(state: dict[str, object]) -> None:
    print("ArtifactForge initialization: already initialized")
    print(f"  origin: {state['origin']}")
    print(f"  upstream: {state['upstream']}")
    print(f"  upstream push: {state['upstream_push']}")
    print(f"  assignment_state: {ASSIGNMENT_STATE_PATH}")
    print()
    print("No repository, remote, assignment_state, or first issue changes were made.")


def current_branch() -> str:
    branch = run_command(["git", "branch", "--show-current"])
    if not branch:
        raise InitError("current git branch could not be detected")
    return branch


def read_worktree_status() -> str:
    return run_command(["git", "status", "--short"])


def assignment_state_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "router_session_id": None,
        "next_sub_artifact_number": 1,
        "assignments": [],
    }


def optional_answer(value: str) -> str:
    return value.strip() or "未記入"


def build_first_issue_body(answers: FirstIssueAnswers) -> str:
    return f"""# 作りたいアーティファクト

## 何を作りたいですか？

{answers.what}

## 進め方の希望はありますか？

{answers.process}

## ゴールはなんですか？

{answers.goal}

---

## option: なぜ作りたいですか？

{optional_answer(answers.option_why)}

## option: すでにある材料はありますか？

{optional_answer(answers.option_materials)}

## option: 作業で避けたいことはありますか？

{optional_answer(answers.option_avoid)}

---

## AI agent 向けコメント

この issue は、この ArtifactForge project の最初の相談です。

まず、この issue の回答から次の2ファイルを作成または更新してください。

- `main_artifact/goal.md`
- `main_artifact/development_process.md`

作成時は、必要に応じて次のテンプレートを参照してください。

- `main_artifact/.goal_template.md`
- `main_artifact/.development_process_template.md`

ユーザーの回答が不足している場合は、推測で確定せず、仮置きの内容と確認事項を分けてください。
最初から細かく作り込みすぎず、次にユーザーが判断しやすい工程にしてください。
"""


def collect_inputs(
    args: argparse.Namespace,
    *,
    default_owner: str | None = None,
) -> tuple[str, str, str, FirstIssueAnswers]:
    project_name = args.project_name
    owner = args.owner
    visibility = args.visibility
    what = args.what
    process = args.process
    goal = args.goal
    option_why = args.option_why
    option_materials = args.option_materials
    option_avoid = args.option_avoid

    if args.yes:
        owner = owner or default_owner
        missing = [
            name
            for name, value in (
                ("--project-name", project_name),
                ("--what", what),
                ("--process", process),
                ("--goal", goal),
            )
            if not value
        ]
        if not owner:
            missing.append("--owner")
        if missing:
            raise InitError(f"--yes requires: {', '.join(missing)}")
        visibility = visibility or "private"
    else:
        print("ArtifactForge initialization")
        print()
        project_name = project_name or prompt_required("Project repository name")
        owner = owner or prompt_required("GitHub owner / organization", default=default_owner)
        visibility = visibility or prompt_required("Visibility", default="private")
        print()
        print("README の最初の3問に答えて、first issue を作ります。")
        what = what or prompt_required("何を作りたいですか？")
        process = process or prompt_required("進め方の希望はありますか？")
        goal = goal or prompt_required("ゴールはなんですか？")
        print()
        print("option の質問です。空欄のままでも構いません。")
        option_why = option_why if option_why is not None else prompt_text(
            "option: なぜ作りたいですか？"
        )
        option_materials = (
            option_materials
            if option_materials is not None
            else prompt_text("option: すでにある材料はありますか？")
        )
        option_avoid = option_avoid if option_avoid is not None else prompt_text(
            "option: 作業で避けたいことはありますか？"
        )

    normalized_project = normalize_repo_name(project_name)
    normalized_owner = normalize_owner(owner)
    if visibility not in {"private", "public", "internal"}:
        raise InitError("visibility must be private, public, or internal")
    return (
        normalized_project,
        normalized_owner,
        visibility,
        FirstIssueAnswers(
            what=what,
            process=process,
            goal=goal,
            option_why=option_why or "",
            option_materials=option_materials or "",
            option_avoid=option_avoid or "",
        ),
    )


def planned_commands(owner: str, project_name: str, visibility: str) -> list[list[str]]:
    full_name = repo_full_name(owner, project_name)
    visibility_flag = f"--{visibility}"
    return [
        ["gh", "auth", "status"],
        ["gh", "api", "user", "--jq", ".login"],
        ["git", "remote", "rename", "origin", "upstream"],
        ["git", "remote", "set-url", "--push", "upstream", "DISABLED"],
        ["git", "add", ".gitignore"],
        ["git", "commit", "-m", PROJECT_GITIGNORE_COMMIT_MESSAGE],
        [
            "gh",
            "repo",
            "create",
            full_name,
            visibility_flag,
            "--source=.",
            "--remote=origin",
            "--push",
        ],
        ["gh", "issue", "create", "--repo", full_name, "--title", "作りたいアーティファクト", "--body-file", "-"],
        ["git", "remote", "-v"],
        ["git", "remote", "get-url", "origin"],
        ["git", "remote", "get-url", "upstream"],
        ["git", "remote", "get-url", "--push", "upstream"],
        ["gh", "repo", "view", full_name, "--json", "nameWithOwner,url"],
    ]


def build_dry_run_payload(
    *,
    owner: str,
    project_name: str,
    visibility: str,
    issue_body: str,
) -> dict[str, object]:
    full_name = repo_full_name(owner, project_name)
    return {
        "mode": "dry-run",
        "project_repository": full_name,
        "visibility": visibility,
        "origin": github_https_url(owner, project_name),
        "upstream_push": "DISABLED",
        "assignment_state_path": str(ASSIGNMENT_STATE_PATH),
        "assignment_state_initial_content": assignment_state_payload(),
        "first_issue": {
            "title": "作りたいアーティファクト",
            "body": issue_body,
        },
        "planned_commands": [" ".join(command) for command in planned_commands(owner, project_name, visibility)],
        "effects": {
            "github_repository": "not created",
            "git_remotes": "not changed",
            "project_gitignore": "not written; real run removes sub_artifact/* and issue_log/* before first push",
            "git_push": "not run",
            "assignment_state": "not written",
            "github_issue": "not created",
        },
    }


def print_text_dry_run(payload: dict[str, object]) -> None:
    first_issue = payload["first_issue"]
    effects = payload["effects"]
    print("ArtifactForge initialization dry-run")
    print()
    print("No GitHub repository, Git remote, commit, push, file write, or issue will be changed.")
    print()
    print("Repository")
    print(f"  project repository: {payload['project_repository']}")
    print(f"  visibility: {payload['visibility']}")
    print(f"  origin: {payload['origin']}")
    print(f"  upstream push URL: {payload['upstream_push']}")
    print()
    print("First GitHub issue to create")
    print(f"  title: {first_issue['title']}")
    print()
    print("----- BEGIN ISSUE BODY -----")
    print(first_issue["body"].rstrip())
    print("----- END ISSUE BODY -----")
    print()
    print("Initial assignment state to write on real run")
    print(f"  path: {payload['assignment_state_path']}")
    print(json.dumps(payload["assignment_state_initial_content"], ensure_ascii=False, indent=2))
    print()
    print("Planned commands")
    for command in payload["planned_commands"]:
        print(f"  $ {command}")
    print()
    print("Dry-run effects")
    for name, value in effects.items():
        print(f"  {name}: {value}")
    print()
    print("Use --format json for the machine-readable dry-run payload.")


def print_dry_run(
    *,
    owner: str,
    project_name: str,
    visibility: str,
    issue_body: str,
    output_format: str,
) -> None:
    payload = build_dry_run_payload(
        owner=owner,
        project_name=project_name,
        visibility=visibility,
        issue_body=issue_body,
    )
    if output_format == "text":
        print_text_dry_run(payload)
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def ensure_clean_enough(*, allow_dirty: bool) -> None:
    status = read_worktree_status()
    if status and not allow_dirty:
        raise InitError(
            "working tree has local changes. Commit/stash them first, or rerun with --allow-dirty.\n"
            + status
        )


def ensure_github_login() -> str:
    print("Checking GitHub login with `gh auth status`...")
    try:
        run_command(["gh", "auth", "status"])
        login = run_command(["gh", "api", "user", "--jq", ".login"]).strip()
    except FileNotFoundError as exc:
        raise InitError(
            "GitHub CLI `gh` was not found.\n"
            "Install GitHub CLI, then run `gh auth login` and rerun this command."
        ) from exc
    except InitError as exc:
        raise InitError(
            "GitHub login: not authenticated.\n"
            "Run `gh auth login`, then rerun this command.\n\n"
            f"{exc}"
        ) from exc
    if not login:
        raise InitError(
            "GitHub login: authenticated, but the login name could not be detected.\n"
            "Pass --owner OWNER explicitly and rerun this command."
        )
    print(f"GitHub login: OK ({login})")
    return login


def project_gitignore_text(source_text: str) -> str:
    """Return the user-project .gitignore variant.

    ArtifactForge source keeps generated artifact directories ignored. Once a
    user initializes a project repository, those project artifact files should
    be tracked normally while .core_program runtime state stays ignored.
    """
    lines = source_text.splitlines()
    output: list[str] = []
    removed: list[str] = []
    for line in lines:
        if line.strip() in PROJECT_TRACKING_IGNORE_PATTERNS:
            removed.append(line.strip())
            continue
        output.append(line)

    text = "\n".join(output).rstrip() + "\n"
    notice = (
        "# ArtifactForge project initialization:\n"
        "# sub_artifact/* and issue_log/* are tracked in initialized user projects.\n"
    )
    if removed and notice not in text:
        marker = "# Runtime state generated by future non-dry-run execution.\n"
        if marker in text:
            text = text.replace(marker, notice + "\n" + marker, 1)
        else:
            text = text.rstrip() + "\n\n" + notice
    return text


def write_project_gitignore() -> bool:
    current = GITIGNORE_PATH.read_text(encoding="utf-8")
    updated = project_gitignore_text(current)
    if updated == current:
        return False
    GITIGNORE_PATH.write_text(updated, encoding="utf-8")
    return True


def commit_project_gitignore_if_changed(changed: bool) -> bool:
    if not changed:
        return False
    run_command(["git", "add", ".gitignore"])
    run_command(["git", "commit", "-m", PROJECT_GITIGNORE_COMMIT_MESSAGE])
    return True


def configure_remotes(owner: str, project_name: str) -> None:
    names = remote_names()
    target_url = github_https_url(owner, project_name)
    if "upstream" not in names:
        if "origin" not in names:
            raise InitError("cannot find origin remote to rename to upstream")
        run_command(["git", "remote", "rename", "origin", "upstream"])
        names = remote_names()
    run_command(["git", "remote", "set-url", "--push", "upstream", "DISABLED"])

    if "origin" in names:
        origin_url = get_remote_url("origin")
        if origin_url != target_url and origin_url != f"{target_url}.git":
            raise InitError(
                f"origin already exists and does not match target repo: {origin_url}"
            )


def create_repo(owner: str, project_name: str, visibility: str) -> None:
    full_name = repo_full_name(owner, project_name)
    visibility_flag = f"--{visibility}"
    if "origin" in remote_names():
        run_command(["gh", "repo", "view", full_name, "--json", "nameWithOwner,url"])
        run_command(["git", "push", "-u", "origin", current_branch()])
        return
    run_command(
        [
            "gh",
            "repo",
            "create",
            full_name,
            visibility_flag,
            "--source=.",
            "--remote=origin",
            "--push",
        ]
    )


def write_assignment_state() -> None:
    if ASSIGNMENT_STATE_PATH.exists():
        return
    ASSIGNMENT_STATE_PATH.write_text(
        json.dumps(assignment_state_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_first_issue(owner: str, project_name: str, issue_body: str) -> str:
    full_name = repo_full_name(owner, project_name)
    output = run_command(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            full_name,
            "--title",
            "作りたいアーティファクト",
            "--body-file",
            "-",
        ],
        input_text=issue_body,
    )
    return output.strip()


def verify_setup(owner: str, project_name: str, issue_url: str) -> dict[str, object]:
    full_name = repo_full_name(owner, project_name)
    origin_url = get_remote_url("origin")
    upstream_url = get_remote_url("upstream")
    upstream_push = get_remote_url("upstream", push=True)
    repo_json = json.loads(
        run_command(["gh", "repo", "view", full_name, "--json", "nameWithOwner,url"])
    )
    issue_number_match = re.search(r"/issues/(\d+)$", issue_url)
    issue_summary: dict[str, object] = {"url": issue_url}
    if issue_number_match:
        issue_summary = json.loads(
            run_command(
                [
                    "gh",
                    "issue",
                    "view",
                    issue_number_match.group(1),
                    "--repo",
                    full_name,
                    "--json",
                    "number,title,url",
                ]
            )
        )
    return {
        "origin": origin_url,
        "upstream": upstream_url,
        "upstream_push": upstream_push,
        "repository": repo_json,
        "first_issue": issue_summary,
        "assignment_state_exists": ASSIGNMENT_STATE_PATH.exists(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a user project repo from ArtifactForge and post the first issue."
    )
    parser.add_argument("--project-name", help="new GitHub repository name")
    parser.add_argument(
        "--owner",
        help="GitHub owner or organization; real run defaults to the logged-in gh user",
    )
    parser.add_argument(
        "--visibility",
        choices=("private", "public", "internal"),
        default=None,
        help="new GitHub repository visibility; defaults to private",
    )
    parser.add_argument("--what", help="answer for README question: 何を作りたいですか？")
    parser.add_argument("--process", help="answer for README question: 進め方の希望はありますか？")
    parser.add_argument("--goal", help="answer for README question: ゴールはなんですか？")
    parser.add_argument("--option-why", help="optional answer: なぜ作りたいですか？")
    parser.add_argument("--option-materials", help="optional answer: すでにある材料はありますか？")
    parser.add_argument("--option-avoid", help="optional answer: 作業で避けたいことはありますか？")
    parser.add_argument("--yes", action="store_true", help="run non-interactively")
    parser.add_argument("--dry-run", action="store_true", help="show planned actions only")
    parser.add_argument(
        "--force",
        action="store_true",
        help="continue even when local initialization state already exists",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="dry-run output format",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow initialization even when the working tree has local changes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    default_owner = None
    if not args.dry_run:
        default_owner = ensure_github_login()
        state = initialization_state()
        if state["initialized"] and not args.force:
            print_initialization_state(state)
            return 0
    project_name, owner, visibility, answers = collect_inputs(
        args,
        default_owner=default_owner,
    )
    issue_body = build_first_issue_body(answers)
    if args.dry_run:
        print_dry_run(
            owner=owner,
            project_name=project_name,
            visibility=visibility,
            issue_body=issue_body,
            output_format=args.format,
        )
        return 0

    print()
    print(f"Create GitHub repository `{repo_full_name(owner, project_name)}` and post first issue.")
    if not confirm("Proceed?", assume_yes=args.yes):
        print("cancelled")
        return 1

    ensure_clean_enough(allow_dirty=args.allow_dirty)
    configure_remotes(owner, project_name)
    project_gitignore_changed = write_project_gitignore()
    commit_project_gitignore_if_changed(project_gitignore_changed)
    create_repo(owner, project_name, visibility)
    write_assignment_state()
    issue_url = create_first_issue(owner, project_name, issue_body)
    verification = verify_setup(owner, project_name, issue_url)
    print(json.dumps({"status": "ok", "verification": verification}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InitError, KeyboardInterrupt) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
