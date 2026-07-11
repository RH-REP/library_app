# .core_program Contract

`.core_program/` contains the internal engine boundary for ArtifactForge.
This README is an entry note for AI agents, maintainers, and operators who open
the internal engine directory directly. Human users normally read the root
`README.md` and `USER_MANUAL.md` only.

It owns machine-facing records only:

- issue fetch state
- `.core_program/queue/`
- `.core_program/pending/`
- `.core_program/archive/`
- `.core_program/assignment_state.json`
- internal logs and diagnostics

It must not own user-facing artifact content. User-facing work belongs under
`main_artifact/`, `sub_artifact/`, and `issue_log/`.

## Directory Contract

```text
.core_program/
├── README.md
├── prompts/
│   ├── session_router_bootstrap_v1.md
│   ├── dispatch_v1.md
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

Runtime state files:

```text
.core_program/assignment_state.json
```

`assignment_state.json` is advisory issue-to-session-to-sub-artifact routing
state for the Session_router. It remembers prior routing decisions, but pending
records, known active prompts, and worker responses may override stale entries.
It replaces the reference implementation name
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
.core_program/prompts/dispatch_v1.md
.core_program/prompts/session_router_v1.md
.core_program/prompts/session_router_bootstrap_v1.md
.core_program/prompts/worker_v1.md
```

Normal dispatch uses `dispatch_v1.md`, but Python is only the mechanical issue
boundary. It fetches GitHub issues/comments, de-dupes them against valid
`codex-agent-v1` markers and existing state, creates queue records, moves
unresolved queue records to `.core_program/pending/`, and invokes or wakes the
single visible Session_router. Python does not choose worker sessions, send
worker prompts, ask permission questions, post final issue comments, or
commit/push project changes.

Every queue or pending record represents one issue thread update. A thread
update is the combined issue body/comment range since the latest valid
`codex-agent-v1` marker. Records use `event_type: thread_update`, `source_id`
values such as `body`, `body..C12B`, or `C2..C3`, and fingerprints like
`issue-N-thread-FIRST-LAST-sha256-...`. Dispatch prompts declare
`recipient_role: router` or `recipient_role: worker` and the target session ID
at the top.

`recipient_role: worker` performs the assigned work, commits and pushes
repository changes to `origin`, and posts a human-visible GitHub issue comment.
The final line of the posted comment must contain a `codex-agent-v1` marker. The
only v1 statuses are:

```text
done
reassign_required
authentication_blocked
```

`recipient_role: router` is the single visible Session_router. It routes only;
it does not do worker implementation work. It reads `.core_program/pending/`,
uses `pending_state.json` as the machine-readable pending ledger, uses
`assignment_state.json` as advisory routing state, prefers existing workers,
avoids `previous_thread_id` on `reassign_required`, starts a new worker only
when no existing worker accepts, dispatches the worker-mode prompt directly to
the selected worker, prevents concurrent prompts to the same worker, and
updates `assignment_state.json` with the worker session, sub-artifact path,
status, and concise workstream summary.

The Session_router is the user's human-facing permission gateway. Worker and
subagent sessions are non-visible by default. A visible child session is used
only when non-visible execution is unsuitable, debug observation is necessary,
or the user explicitly asks for visibility; the router records the reason when
that happens. If a subagent hits login, approval, permission, TTY, model
escalation, or other interactive requirements, the request must be surfaced
through the Session_router instead of asking the user to open that subagent
session directly. Workers and subagents may receive permissions/capabilities the
Session_router already has when the pending task needs them and the action stays
within this repository/project scope; new permissions or broader capabilities
still require user approval through the Session_router. Workers and subagents
use GPT-5.4-high by default and escalate to GPT-5.5-high only when the work
justifies the stronger model.

Normal final GitHub issue comments are posted by the assigned worker. The
exception is a contract-violation bug report: if the Session_router discovers
that ArtifactForge's routing, permission, concurrency, marker, pending/archive,
or worker-responsibility contract has been violated, the Session_router posts a
concise bug report comment to the relevant issue itself. That bug report ends
with a `codex-agent-v1` marker using an existing status, usually
`authentication_blocked` unless the violation is specifically a wrong-session
assignment (`reassign_required`). Posting the bug report does not by itself
archive the pending file.

If the Session_router needs a human judgment, it writes a resumption memo under
`.core_program/request_for_human/` before asking the question. On each wake-up,
the Session_router checks that folder before processing `.core_program/pending/`
so interrupted questions can be resumed cleanly. Memo template:

```text
日時:
Pending fingerprints:
Worker session ID:
問い合わせ内容:
```

The bootstrap prompt starts the first visible Session_router when
`assignment_state.json` has `router_session_id: null`; its expected response is
exactly `SESSION_ROUTER_READY`. The CLI caller launches bootstrap in a visible
Terminal session, discovers the started session ID from local Codex session
records, and saves it to `assignment_state.json`.

## Output Rule

`Session_router` bootstrap stdout is a protocol surface and must contain exactly
`SESSION_ROUTER_READY`. Normal Session_router activity is user/operator-facing:
it should concisely report pending records that were dispatched, deferred, or
blocked, and ask any required user questions from the visible router session.

All diagnostics must go to internal logs, stderr, or operator summaries.

## Pending Rule

Python dispatch does not wait for completion. It moves unresolved queue records
to pending before invoking the Session_router. The Session_router checks
`.core_program/request_for_human/` first, then reads `.core_program/pending/`
and `.core_program/pending_state.json`, and processes pending records in
deterministic path order until no dispatchable pending record remains. It does
not stop after one pending item unless all remaining records are deferred,
blocked, human-waiting, superseded, archived, or already
dispatched/in-progress.

Pending state is stored in `.core_program/pending_state.json` with
machine-readable records containing `pending_path`, `trigger_fingerprint`,
`worker_session_id`, `status`, timestamps, and a reason where relevant. Valid
statuses are:

```text
unsent
router_notified
dispatched
deferred
blocked
human_waiting
superseded
archived
```

When the pending work is resolved and the final GitHub issue comment with the
required
`codex-agent-v1` marker has been posted, the corresponding pending file is
moved to archive with the same filename:

```sh
mv .core_program/pending/xxx.md .core_program/archive/xxx.md
```

Blocked, deferred, human-waiting, or in-progress records stay in
`.core_program/pending/`.

Older pending files that are covered by a newer `thread_update` starting at the
same issue/comment source are superseded. They must not be dispatched as
independent current work; when safe, they are moved to archive and marked
`superseded` in `pending_state.json`.

Pending records must distinguish router-visible unresolved work from worker
work that has already been dispatched. The Session_router uses pending state to
avoid sending concurrent prompts to the same worker. If multiple pending
records map to the same worker, the router dispatches one and leaves the rest
deferred until that worker resolves the active record.

Before reading pending records, the Session_router checks
`.core_program/request_for_human/` for unresolved human request memos.

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

### Agent Flow Demo Utility

The local demo utility lives at:

```sh
python3 .core_program/app/03_agent_flow_demo/run_agent_flow_demo.py
```

It uses the fixture queue and a fake runner. It does not call real GitHub or
Codex, and it demonstrates the intended flow where the Session_router is
visible, worker and subagent sessions are non-visible, subagent permission
or interactive requirements are routed back through the Session_router, and a
tiny demo software file is implemented and verified.

To prepare the same flow for real Codex sessions without touching GitHub:

```sh
python3 .core_program/app/03_agent_flow_demo/run_real_codex_demo.py --bootstrap-router
python3 .core_program/app/03_agent_flow_demo/run_real_codex_demo.py --dry-run-dispatch
python3 .core_program/app/03_agent_flow_demo/run_real_codex_demo.py --dispatch
```

The real-Codex demo stores its isolated queue, pending files, assignment state,
and summary under `.core_program/dry_run_output/real_codex_demo/`. It only uses
the local fixture in `.core_program/fixtures/agent_flow_demo/` and its dispatch
payload explicitly forbids GitHub calls, issue comments, commits, and pushes.

With a real repository:

```sh
python3 .core_program/app/01_fetch_issue/run_issue_queue.py
python3 .core_program/app/02_dispatch_queue/run_dispatch_queue.py
```

The first command reports issue thread updates, queue candidates, and
pending-to-archive plans. It infers `OWNER/REPO` from the `origin` Git remote;
pass `--repo OWNER/REPO` to override that. In normal execution it fetches open
GitHub issues, writes
`.core_program/app/01_fetch_issue/data/open_issues.json`, moves completed
pending files to archive, and creates queue files. If
`assignment_state.json` has no `router_session_id`, normal execution bootstraps
the first Session_router by opening a visible Terminal session, then saves that
ID before queue files are created; dry-run reports the bootstrap as planned
without starting Codex.

### Manual Router Bootstrap Recovery

If automatic Session_router bootstrap fails, start or resume the Session_router
manually, copy its Codex session ID, and rerun issue fetch with:

```sh
python3 .core_program/app/01_fetch_issue/run_issue_queue.py --router-session-id SESSION_ID
```

The provided `SESSION_ID` is saved to `.core_program/assignment_state.json` and
reused by later runs.

The second command moves queued records into `.core_program/pending/` and
invokes or wakes the single visible Session_router. It does not send worker
prompts and does not perform worker busy checks. The Session_router reads
pending records, assigns work, starts or resumes non-visible workers by
default, and treats every worker session ID as a single-lane resource. If a
visible worker is necessary, the router records why. If pending state or known
active prompt state shows unresolved work for a target worker, the router
defers additional prompts for that worker.

The dispatcher itself does not post comments, commit, or push. The worker-role
prompt requires the assigned worker to commit intended repository changes, push
to `origin`, and post the final GitHub issue comment with the marker footer
unless a local demo contract explicitly forbids external side effects.

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

There is one visible Session_router. No separate global router lock is planned.
Duplicate dispatch is prevented through queue, pending, and advisory
assignment-state checks. The Session_router also enforces a per-worker
single-lane rule: never send concurrent prompts to the same worker session.

## Legacy Names

Top-level `artifact/` and `ticket_log/` are not ArtifactForge contract paths.
Do not introduce dependencies on either name.
