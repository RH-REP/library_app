# issue_log Contract

`issue_log/` is the only user-facing issue-work log name in ArtifactForge.

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
