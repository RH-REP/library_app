# ArtifactForge Contract

This document is for AI agents and ArtifactForge maintainers. Human users
normally read `README.md` and `USER_MANUAL.md` only.

`CONTRACT.md` describes ArtifactForge's repository structure and responsibility
boundaries. It does not describe the product, app, document, or software that a
user is building with ArtifactForge. Project-specific requirements belong in
`main_artifact/goal.md`.

## Human-Facing Documents

The normal human user documentation set is:

- `README.md`
- `USER_MANUAL.md`

Directory README files may exist as short entry notes for people or agents who
open that directory directly, but they are not required reading for ordinary
users.

## Project Specification Boundary

ArtifactForge is a system template and issue dispatch engine. Each cloned user
project owns its own goals, process, artifacts, and issue logs.

- ArtifactForge structural and operational contracts belong in this file and in
  `.core_program/` implementation prompts or code.
- Project/software/product specifications belong in `main_artifact/goal.md`.
- Project process and review flow belong in
  `main_artifact/development_process.md`.

Do not put a specific user's product requirements into ArtifactForge's system
contract.

## Canonical Paths

### `main_artifact/`

`main_artifact/` is the location for the completed or integrated primary
artifact, plus the canonical goal and process files that define how that primary
artifact is completed.

- `main_artifact/goal.md` is the source of truth for the project goal, scope,
  success conditions, and project-specific requirements.
- `main_artifact/development_process.md` is the source of truth for the process,
  review points, phases, and next steps needed to complete the main artifact.
- `main_artifact/.goal_template.md` and
  `main_artifact/.development_process_template.md` are agent templates, not
  places for project-specific final content.

### `sub_artifact/`

`sub_artifact/` contains intermediate outputs, parts, investigations,
prototypes, and helper work used to complete or improve the primary artifact in
`main_artifact/`.

Worker sessions initialize numbered directories such as:

```text
sub_artifact/NNN_slug/
```

The standard file set is:

```text
sub_goal.md
plan.md
work_log.md
artifact.md
```

Sub-artifacts support the main artifact. They do not replace
`main_artifact/goal.md` as the project goal source of truth.

### `issue_log/`

`issue_log/` contains human-readable issue-level decision records and work logs.
It is for explanations that should remain understandable without inspecting
`.core_program/` runtime state.

### `.core_program/`

`.core_program/` is the internal engine boundary. It owns machine-facing runtime
state, prompts, queue files, pending files, archives, assignment state, and
diagnostics.

Pending orchestration state belongs in `.core_program/pending_state.json`. It
is a machine-readable ledger used by the Session_router to distinguish unsent,
dispatched/in-progress, deferred, blocked, human-waiting, superseded, and
archived pending records.

Python fetch/reconcile owns the transition from `.core_program/pending/` to
`.core_program/archive/`. Routers, workers, and subagents must leave pending
files in place after posting or observing final markers; Python archives only
after it confirms the exact pending `trigger_fingerprint` marker on GitHub.

Normal project requirements and human-facing issue decisions do not belong in
`.core_program/`.

## Non-Contract Paths

Top-level `artifact/` and `ticket_log/` are not current ArtifactForge contract
paths. Do not introduce new dependencies on either name.

Use:

- `main_artifact/` for the primary artifact, goal, and process
- `sub_artifact/` for supporting work units
- `issue_log/` for human-readable issue logs
