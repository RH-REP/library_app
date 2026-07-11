# issue_log

`issue_log/` is the only user-facing issue-work log name in ArtifactForge.
This README is a short entry note for people or AI agents who open this
directory directly. Human users normally read the root `README.md` and
`USER_MANUAL.md` only.

It owns human-readable notes about issue-driven work, review gates, and
operator decisions that should remain understandable without opening
`.core_program/`.

It does not own:

- fetched GitHub issue snapshots
- queue records
- pending records
- archive records
- router stdout
- assignment state

Those machine-facing records belong under `.core_program/`.

`ticket_log/` is not part of this repository contract.
