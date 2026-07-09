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

`assignment_state.json` is the future canonical issue-to-session-to-sub-artifact
assignment state. Its schema is intentionally deferred to Stage 1.

Do not use `.core_program/artifact_session_map.json` as the ArtifactForge
contract name. That name belongs to the reference implementation and is replaced
here by `assignment_state.json`.

## Output Rule

`Session_router` stdout is a protocol surface. It must contain exactly one
session ID line and nothing else.

All diagnostics must go to internal logs, stderr, or operator summaries.

## Pending Rule

Dispatch does not wait for completion. After a worker prompt is sent, the event
is moved to pending. Later issue fetches inspect GitHub markers and decide
whether pending records stay pending, move to archive, or require human action.

Pending records must distinguish router pending from worker pending.

## Locking Rule

No global router lock is planned. Normal operation processes one issue group at
a time, and duplicate dispatch is prevented through queue, pending, and
assignment-state checks.

## Legacy Names

Top-level `artifact/` and `ticket_log/` are not ArtifactForge contract paths.
Do not introduce dependencies on either name.
