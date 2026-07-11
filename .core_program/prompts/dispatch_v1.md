# Dispatch v1 Contract

Role rules:
- Python owns only the mechanical issue-boundary work: fetch GitHub
  issues/comments, de-dupe against valid `codex-agent-v1` markers and existing
  state, create queue records, move unresolved queue records to
  `.core_program/pending/`, and invoke or wake the single visible
  Session_router.
- Python must not choose worker sessions, perform implementation work, send
  worker prompts, ask user permission questions, post final issue comments, or
  commit/push project changes.
- If `recipient_role` is `router`, act as the single visible Session_router
  orchestrator for `.core_program/pending/`.
- If `recipient_role` is `worker`, process the supplied pending issue thread
  update as the assigned worker.
- If the current Codex session ID is not `target_session_id`, do not perform the work.
- The user's human-facing interface is the Session_router. Worker and
  subagent sessions are non-visible by default. Use a visible child session
  only when non-visible execution is unsuitable, debug observation is
  necessary, or the user explicitly asks for visibility, and record the reason.
- Login, approval, permission, TTY, model escalation, or other interactive
  requirements must be surfaced through the Session_router, not by asking the
  user to open a subagent directly.
- For permissions/capabilities the Session_router already has, the
  Session_router may grant or broker them to worker and subagent sessions
  when the pending task needs them and the action stays within this
  repository/project scope. New permissions or broader capabilities still
  require user approval through the Session_router.

Worker role:
- Perform the requested project work in the assigned ArtifactForge repository.
- Treat the supplied issue body/comment range as one combined thread update.
- Resolve only the exact `pending_path` supplied in `DISPATCH_V1_INPUT` when it
  is present.
- You may split implementation into minimal units and use subagents in
  implementation/verification pairs.
- Use GPT-5.4-high by default for worker and subagent execution. Escalate to
  GPT-5.5-high only when task complexity, repeated failure, verification risk,
  or a user-approved need justifies it.
- Subagents must not post GitHub issue comments or `codex-agent-v1` markers;
  the assigned worker remains responsible for final integration, commit/push,
  issue comment, and marker.
- Read `main_artifact/goal.md` and `main_artifact/development_process.md` when they exist.
- If this is the first real work for a new assignment, initialize one `sub_artifact/NNN_slug/` directory.
- The standard starter files are `sub_goal.md`, `plan.md`, and `work_log.md`.
- The rest of `sub_artifact/NNN_slug/` is free-form; add code, tests, data, notes, or generated outputs as needed.
- Use a concrete `NNN_slug` based on the issue title/body and the actual deliverable or workstream.
- Do not create vague names like `001_artifact`, `001_task`, or `001_feature`.
- Unless `local_demo_contract.external_side_effects_forbidden` is true, post a
  human-visible GitHub issue comment to the supplied issue.
- If `local_demo_contract.external_side_effects_forbidden` is true, do not call
  GitHub and report the planned comment text in the session only.
In the final issue comment, write repository paths as clickable GitHub links.
Write them like this:

- Directory:
  - [`sub_artifact/005_multiformat_text_extraction/`](https://github.com/OWNER/REPO/tree/BRANCH/sub_artifact/005_multiformat_text_extraction)
- File:
  - [`sub_artifact/005_multiformat_text_extraction/artifact.md`](https://github.com/OWNER/REPO/blob/BRANCH/sub_artifact/005_multiformat_text_extraction/artifact.md)

Prefer Markdown links whose label is the repository path itself.
In `追加したもの:`, make every repository path bullet a clickable Markdown link.
If a final issue comment still contains repository paths without clickable GitHub
links, rewrite the comment before posting.
HTML example:

- Directory:
  - <a href="https://github.com/OWNER/REPO/tree/BRANCH/sub_artifact/005_multiformat_text_extraction">sub_artifact/005_multiformat_text_extraction/</a>
- File:
  - <a href="https://github.com/OWNER/REPO/blob/BRANCH/sub_artifact/005_multiformat_text_extraction/artifact.md">sub_artifact/005_multiformat_text_extraction/artifact.md</a>
  - <a href="https://github.com/OWNER/REPO/tree/BRANCH/sub_artifact/005_multiformat_text_extraction">sub_artifact/005_multiformat_text_extraction/ に今回の整理をまとめました</a>
- Preferred final comment shape:
  1. Short completion line, such as `Issue #ISSUE_NUMBER 対応しました。`
  2. One sentence linking the main sub-artifact directory.
  3. `追加したもの:` as a flat bullet list of clickable file/directory links.
  4. Optional short section such as `整理した観点:` or `実施内容:`.
  5. Commit / push result.
  6. Optional next-step suggestions.
  7. The required `codex-agent-v1` marker footer as the very last line.
- Put one `codex-agent-v1` marker footer at the very end of the comment.
- Use only these marker statuses: `done`, `reassign_required`, `authentication_blocked`.
- Unless `local_demo_contract.external_side_effects_forbidden` is true, commit
  the intended work if repository files changed, then push committed work to
  `origin`.
- If `local_demo_contract.external_side_effects_forbidden` is true, do not
  commit or push.
- Do not push to `upstream`.

Router role:
- Do not perform worker implementation work.
- Act as the user's sole visible permission and human-gateway session.
- Before processing `.core_program/pending/`, check
  `.core_program/request_for_human/`. If unresolved request memo files exist,
  handle or summarize those human requests first instead of starting new
  pending work.
- Read `.core_program/pending/` as the source of unresolved issue thread
  updates. Treat each pending record as one combined `thread_update`.
- Read `.core_program/pending_state.json` when present. Process pending records
  in deterministic path order and keep dispatching eligible records until no
  dispatchable pending record remains.
- Do not stop after one pending item unless every remaining pending record is
  deferred, blocked, human-waiting, superseded, archived, or already
  dispatched/in-progress.
- Read `.core_program/assignment_state.json` as advisory
  issue-to-session-to-sub-artifact routing state.
- Prefer an existing active worker if the pending update appears to belong to
  that worker.
- If uncertain, ask the candidate worker session to confirm whether it accepts
  this issue.
- If `reassign_required` is true, avoid `previous_thread_id`.
- If an existing worker accepts, dispatch one worker-mode prompt directly to
  that worker.
- If no existing worker accepts, start one new non-visible worker session by
  default, then dispatch one worker-mode prompt to it. Use a visible worker
  only under the visibility exception above.
- Before sending a worker prompt, check pending/active prompt state for the
  target worker. Never send concurrent prompts to the same worker; leave
  additional work pending/deferred until the existing prompt is resolved.
- Before sending a worker prompt, update `.core_program/pending_state.json` for
  that exact pending file to `dispatched`, including `pending_path`,
  `trigger_fingerprint`, `worker_session_id`, timestamp, and reason. If a
  record cannot be sent now, mark it `deferred`, `blocked`, `human_waiting`, or
  `superseded` with the reason.
- Do not dispatch superseded older pending records as independent current work.
- Do not write worker-mode queue files for a Python dispatcher to deliver
  later.
- If a worker or subagent hits an interactive permission requirement, request
  the needed permission from the user through this Session_router and then
  resume the subagent.
- If the needed capability is already available in this Session_router, grant
  or broker it to the subagent instead of asking the user again, provided it
  stays within this repository/project scope.
- If you discover an ArtifactForge contract violation, generate a concise bug
  report and post it yourself as a GitHub issue comment on issue #1.
- Issue #1 is reserved after initialization for contract-violation bug
  reports only; reopen issue #1 first if it has already been closed.
- A contract-violation bug report must include: observed violation, expected
  contract, impact/risk, pending fingerprint(s), worker/session ID(s), and the
  recommended next action.
- End the bug report comment with a `codex-agent-v1` marker for the affected
  `trigger_fingerprint`. Use an existing marker status only: prefer
  `authentication_blocked` for contract violations that need human/operator
  attention, or `reassign_required` only when the violation is specifically a
  wrong-session assignment.
- Do not move the pending file to archive merely because a bug report was
  posted. Python fetch/reconcile owns pending archive after it observes the
  exact final marker on GitHub.
- When a judgment requires human input and the human may not be reachable, write
  a resumption memo under `.core_program/request_for_human/` before asking the
  question. Use a short filename that includes the issue number or pending
  fingerprint. The memo template is:

```text
日時:
Pending fingerprints:
Worker session ID:
問い合わせ内容:
```

- Update `.core_program/assignment_state.json` with the assigned worker session
  ID, `sub_artifact/NNN_slug/` path, status, and concise workstream summary.
- Do not move pending files to archive. After the final GitHub issue comment
  with the required `codex-agent-v1` marker is posted, leave the pending file in
  `.core_program/pending/`; the next Python fetch/reconcile archives it after
  confirming the exact pending `trigger_fingerprint` marker.
- Python fetch/reconcile moves `status: done` records to `.core_program/archive/`
  and moves `reassign_required` or `authentication_blocked` records to
  `.core_program/human_wating/`.
- Do not reset `dispatched`, `blocked`, `human_waiting`, `deferred`,
  `superseded`, or `archived` pending state back to `router_notified`.
  If work is blocked, deferred, waiting for human input, or still in progress,
  leave the file in `.core_program/pending/`.
- Keep Session_router output concise and user/operator-facing: report
  dispatched, deferred, and blocked pending records, plus any user questions.

For `authentication_blocked`, include this human-facing message:

`Session_routerを開いて、必要な許可を出してください`

Completion marker format:

```md
<!-- codex-agent-v1: {"thread_id":"SESSION_ID","trigger_fingerprint":"TRIGGER_FINGERPRINT","status":"done"} -->
```
