# ArtifactForge Development Process

This document is the initial development process for building ArtifactForge from
an empty repository. It is intentionally split into small stages so each contract
can be reviewed before later code depends on it.

## Stage 0: Repository Contract

Create the initial user-facing and internal layout contracts.

Deliverables:

- `main_artifact/goal.md`
- `main_artifact/README.md`
- `sub_artifact/README.md`
- `issue_log/README.md`
- `issue_log/`
- `.core_program` directory contract
- documented names for queue, pending, archive, router session, and assignment state

Reserved `.core_program` names:

```text
.core_program/queue/
.core_program/pending/
.core_program/archive/
.core_program/router_session_id.txt
.core_program/assignment_state.json
```

Acceptance:

- The repo has one clear user-facing goal location.
- Internal engine files are separated under `.core_program`.
- `issue_log/` is the only user-facing issue log name.
- No top-level `artifact/` or `ticket_log/` path is part of the contract.

## Review 1: Structure And Naming Review

Review after Stage 0 and before implementing routing logic.

Questions:

- Are user-facing files separated from `.core_program` internals?
- Are `main_artifact`, `sub_artifact`, and `issue_log` names final?
- Is there any accidental legacy dependency on `artifact/` or `ticket_log/`?

Exit condition:

- The directory contract is accepted as the base for implementation.
- Stage 1 routing state, GitHub fetch, and worker dispatch implementation have
  not started.

## Stage 1: Assignment State

Define the canonical `.core_program` assignment record for:

- issue number or issue URL
- trigger fingerprint
- session ID
- `sub_artifact/NNN_slug/` path
- assignment status
- whether the record is current
- router decision source

Acceptance:

- A returned session ID can always be traced to one current assignment record.
- Historical reassignment can be represented without making current routing ambiguous.
- The state can distinguish router pending from worker pending.

## Stage 2: Issue Fetch And Queue

Implement the issue fetch and queue builder.

Rules:

- AI marker comments are ignored as new work.
- A done marker prevents requeueing the same trigger fingerprint.
- A blocked marker prevents automatic dispatch until later human action.
- A reassign marker routes the issue back through `Session_router`.
- If a trigger fingerprint already exists in queue or pending, it is not queued again.

Acceptance:

- The queue is deterministic from a given issue snapshot.
- The same issue group is not dispatched concurrently by normal operation.
- The lack of a global lock is backed by queue and pending duplicate checks.

## Stage 3: Session_router Contract

Implement the router prompt, router call, and output validation.

Rules:

- Router output is exactly one session ID line.
- JSON, Markdown, prose, confidence, and diagnostics are invalid stdout.
- Existing candidate sessions are asked whether the issue belongs to them.
- If a candidate denies the issue and another candidate exists, ask the next candidate.
- If no valid candidate accepts the issue, create a new worker session.
- When reassigning, do not route back to the rejecting previous session.

Acceptance:

- Invalid router output stops dispatch and produces an internal diagnostic.
- A valid router output is recorded before the worker prompt is sent.
- New session creation never returns a placeholder ID.

## Review 2: Routing Contract Review

Review after Stage 3 and before implementing worker initialization.

Questions:

- Does router stdout remain machine-safe as a one-line protocol?
- Can each router decision be audited in `.core_program` without reading stdout diagnostics?
- Does the no-global-lock assumption still hold with the queue and pending checks?
- Does reassignment avoid retrying the same rejecting session?

Exit condition:

- Router output, assignment state, and pending state are accepted as stable contracts.

## Stage 4: Dispatch And Pending Lifecycle

Implement dispatch from queue to worker session.

Rules:

- Worker prompt send success moves the event to pending.
- Dispatch does not wait for completion.
- The next issue fetch checks GitHub markers and archives or keeps pending records.
- Long-lived pending records are visible as operational warnings.

Acceptance:

- Pending records show what was sent, to which session, and why.
- Router pending and worker pending are distinguishable.
- A failed send does not masquerade as worker pending.

## Stage 5: Worker Sub-artifact Initialization

Implement the worker first-work contract.

On first real work, the worker creates:

```text
sub_artifact/NNN_slug/sub_goal.md
sub_artifact/NNN_slug/plan.md
sub_artifact/NNN_slug/work_log.md
sub_artifact/NNN_slug/artifact.md
```

Rules:

- Initialization is idempotent.
- Existing files are not overwritten silently.
- The files identify the issue, session ID, and sub-artifact path.
- Slug/index reuse means the work belongs to the same current sub-artifact, not a collision to resolve.

Acceptance:

- Partial initialization is detectable.
- Re-running the worker does not create a second path for the same assignment.
- The assignment record and sub-artifact files agree.

## Stage 6: End-to-end Operation

Connect fetch, queue, router, dispatch, pending follow-up, and worker
initialization into the normal cycle.

Acceptance:

- A new issue can be routed to an existing session or a new session.
- A worker can initialize a sub-artifact and leave a GitHub marker.
- A later fetch can detect done, blocked, or reassign status.
- Operator-facing summaries are separate from router stdout.

## Review 3: End-to-end Operational Review

Review after Stage 6 and before treating the system as usable for real work.

Questions:

- Can an issue be traced through fetch, queue, router, dispatch, pending, and marker detection?
- Are pending records enough to notice worker initialization failure?
- Are user-facing artifacts understandable without opening `.core_program` internals?
- Is the first real workflow recoverable after router invalid output, send failure, blocked status, and reassignment?

Exit condition:

- The system can run a dry end-to-end issue lifecycle with no ambiguous state.
