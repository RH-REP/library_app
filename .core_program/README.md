# .core_program Contract

`.core_program/` contains the internal engine boundary for ArtifactForge.

It owns machine-facing records only:

- issue fetch state
- `.core_program/queue/`
- `.core_program/pending/`
- `.core_program/archive/`
- `.core_program/router_session_id.txt`
- `.core_program/assignment_state.json`
- internal logs and diagnostics

It must not own user-facing artifact content. User-facing work belongs under
`main_artifact/`, `sub_artifact/`, and `issue_log/`.

## Directory Contract

```text
.core_program/
├── README.md
├── prompts/
│   ├── session_router_v1.md
│   └── worker_v1.md
├── app/
│   ├── 00_initialize_project/
│   ├── 01_fetch_issue/
│   └── 02_dispatch_queue/
├── lib/
│   └── artifactforge_dispatch_v1/
├── fixtures/
│   └── dry_run/
├── queue/
├── pending/
└── archive/
```

Reserved future files:

```text
.core_program/router_session_id.txt
.core_program/assignment_state.json
```

`router_session_id.txt` stores the visible Session_router session ID once
routing is implemented.

`assignment_state.json` is the canonical issue-to-session-to-sub-artifact
assignment state. It replaces the reference implementation name
`.core_program/artifact_session_map.json`.

Minimum schema:

```json
{
  "schema_version": 1,
  "router_session_id": "SESSION_ROUTER_SESSION_ID",
  "next_sub_artifact_number": 1,
  "assignments": [
    {
      "issue_number": 1,
      "sub_artifact_path": "sub_artifact/001_slug",
      "session_id": "WORKER_SESSION_ID",
      "status": "active",
      "summary": "human-readable workstream summary"
    }
  ]
}
```

Do not use `.core_program/artifact_session_map.json` as the ArtifactForge
contract name. That name belongs to the reference implementation and is replaced
here by `assignment_state.json`.

## Prompt Contract

The prompt source files are:

```text
.core_program/prompts/session_router_v1.md
.core_program/prompts/worker_v1.md
```

`Session_router` routes only. It does not do worker work and its stdout must be
exactly one session ID line.

`Worker` does the assigned work and writes a human-visible GitHub issue comment.
The final line must contain a `codex-agent-v1` marker. The only v1 statuses are:

```text
done
reassign_required
authentication_blocked
```

## Output Rule

`Session_router` stdout is a protocol surface. It must contain exactly one
session ID line and nothing else.

All diagnostics must go to internal logs, stderr, or operator summaries.

## Pending Rule

Dispatch does not wait for completion. After a worker prompt is sent, the event
is moved to pending. Later issue fetches inspect GitHub markers and decide
whether pending records stay pending, move to archive, or require human action.

Pending records must distinguish router pending from worker pending.

## Issue Dispatch Commands

ArtifactForge implements the issue dispatch flow with a dry-run boundary. In
dry-run, fixture JSON can be used and the commands do not:

- call GitHub
- start Codex sessions
- post GitHub comments
- create or move queue, pending, or archive files
- create `sub_artifact/` files

From the repository root:

```sh
python3 .core_program/app/01_fetch_issue/run_issue_queue.py --dry-run
python3 .core_program/app/02_dispatch_queue/run_dispatch_queue.py --dry-run
```

With a real repository:

```sh
python3 .core_program/app/01_fetch_issue/run_issue_queue.py --repo OWNER/REPO
python3 .core_program/app/02_dispatch_queue/run_dispatch_queue.py
```

The first command reports issue events, queue candidates, and pending-to-archive
plans. In normal execution it fetches open GitHub issues, writes
`.core_program/app/01_fetch_issue/data/open_issues.json`, moves completed
pending files to archive, and creates queue files.

The second command sends queued prompts to Codex. In normal execution, successful
dispatch moves queue files to pending. GitHub issue comments are not posted by
default; comment posting support exists behind an explicit caller option so the
operator can keep dispatch and posting separate.

## Project Initialization

`00_initialize_project` creates the user project repository and posts the first
GitHub issue. It checks `gh` login first. The logged-in GitHub user becomes the
default owner, and the user only needs to change owner/org when creating under
an organization. It asks for the repository name, visibility, and the README
first-issue questions:

```text
何を作りたいですか？
進め方の希望はありますか？
ゴールはなんですか？
```

Dry-run:

```sh
python3 .core_program/app/00_initialize_project/init_project.py --dry-run
```

Dry-run prints the first issue title/body, planned repository and remote
settings, planned commands, and the no-op effects. Use `--format json` when a
machine-readable payload is needed.

Real run:

```sh
python3 .core_program/app/00_initialize_project/init_project.py
```

The real run:

- checks `gh` login and uses the logged-in user as the default owner
- stops early when `origin`, `upstream`, disabled upstream push, and
  `.core_program/assignment_state.json` indicate the project is already
  initialized; use `--force` to continue anyway
- renames the current `origin` remote to `upstream` when needed
- disables push to `upstream`
- creates the user project repository with `gh repo create`
- adds the new repository as `origin`
- pushes the current branch to `origin`
- initializes `.core_program/assignment_state.json`
- creates the first GitHub issue using the README question answers
- verifies `origin`, `upstream`, `upstream` push URL, repository existence, and
  first issue existence

## Locking Rule

No global router lock is planned. Normal operation processes one issue group at
a time, and duplicate dispatch is prevented through queue, pending, and
assignment-state checks.

## Legacy Names

Top-level `artifact/` and `ticket_log/` are not ArtifactForge contract paths.
Do not introduce dependencies on either name.
