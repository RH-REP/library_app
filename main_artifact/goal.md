# ArtifactForge Goal

ArtifactForge is a local program for turning a user-written production goal and
GitHub issues into coordinated AI worker sessions.

The user-facing repository layout starts from:

```text
main_artifact/goal.md
sub_artifact/001_slug/
issue_log/
```

`.core_program` is the internal engine. It owns routing state, queue state,
pending state, archive state, router session configuration, and session
assignment records.

## Core Flow

1. The user writes the production goal in `main_artifact/goal.md`.
2. GitHub issues describe work requests.
3. `.core_program` fetches issue events and queues work that needs an AI worker.
4. `Session_router` reads the goal, issue event, and assignment state.
5. `Session_router` returns exactly one session ID line.
6. The dispatcher sends the worker prompt to that session and moves the event to pending.
7. Completion is not waited on synchronously. The next issue fetch detects worker markers and updates pending state.
8. A worker initializes its own `sub_artifact/001_slug/` area on first real work.

## Fixed Decisions

- The canonical issue-to-session-to-sub-artifact assignment state lives inside `.core_program`.
- The reserved assignment state path is `.core_program/assignment_state.json`.
- The reserved router session path is `.core_program/router_session_id.txt`.
- Router stdout is a protocol surface and must contain only one session ID line.
- Logs, diagnostics, and state records must not be mixed into router stdout.
- Global locking is not planned because the dispatcher is expected to process one issue group at a time.
- Duplicate prevention is handled by queue, pending, and assignment-state checks.
- `ticket_log/` is not used. The user-facing issue work log is `issue_log/`.
- Completion is detected by later issue fetches, not by waiting during dispatch.
- This repository starts from the new layout, so no legacy top-level `artifact/`
  or `ticket_log/` migration path is required.
