# Dispatch v1 Contract

Role rules:
- If `recipient_role` is `worker`, process the supplied issue thread update as the assigned worker.
- If `recipient_role` is `router`, route the supplied issue thread update and hand it off to exactly one correct worker.
- If the current Codex session ID is not `target_session_id`, do not perform the work.

Worker role:
- Perform the requested project work in the assigned ArtifactForge repository.
- Treat the supplied issue body/comment range as one combined thread update.
- Read `main_artifact/goal.md` and `main_artifact/development_process.md` when they exist.
- If this is the first real work for a new assignment, initialize one `sub_artifact/NNN_slug/` directory.
- The standard first-work file set is `sub_goal.md`, `plan.md`, `work_log.md`, and `artifact.md`.
- Use a concrete `NNN_slug` based on the issue title/body and the actual deliverable or workstream.
- Do not create vague names like `001_artifact`, `001_task`, or `001_feature`.
- Post a human-visible GitHub issue comment to the supplied issue.
- Put `codex-agent-v1` marker footer(s) at the very end of the comment.
- Use only these marker statuses: `done`, `reassign_required`, `authentication_blocked`.
- Commit the intended work if repository files changed, then push committed work to `origin`.
- Do not push to `upstream`.

Router role:
- Do not perform worker implementation work.
- Read `.core_program/assignment_state.json` as the canonical issue-to-session-to-sub-artifact assignment state.
- Prefer an existing active worker if the issue appears to belong to that worker.
- If uncertain, ask the candidate worker session to confirm whether it accepts this issue.
- If `reassign_required` is true, avoid `previous_thread_id`.
- If an existing worker accepts, send a worker-mode ArtifactForge Dispatch Prompt v1 to that worker exactly once.
- If no existing worker accepts, start one new visible worker session in a terminal and send the worker-mode dispatch prompt exactly once.
- Update `.core_program/assignment_state.json` with the assigned worker session ID and `sub_artifact/NNN_slug/` path.
- Output exactly one worker session ID line.
- Do not output JSON, reasons, confidence, prose, Markdown, labels, or extra lines.

For `authentication_blocked`, include this human-facing message:

`Session ID SESSION_IDを開いて、許可を出してください`

Completion marker format:

```md
<!-- codex-agent-v1: {"thread_id":"SESSION_ID","trigger_fingerprint":"TRIGGER_FINGERPRINT","status":"done"} -->
```
