# Development Process Log

This log records the initial split of the ArtifactForge development process.

Created decisions:

- Development is split into six implementation stages plus Stage 0 setup.
- Three review gates are required:
  - Review 1: structure and naming
  - Review 2: routing contract
  - Review 3: end-to-end operation
- `issue_log/` is the local issue-work log name.
- `.core_program/queue/`, `.core_program/pending/`, and
  `.core_program/archive/` are the reserved internal lifecycle directories.
- `.core_program/router_session_id.txt` is the reserved router session config.
- `.core_program/assignment_state.json` is the reserved assignment state file.
- Completion is detected asynchronously by later issue fetches.
- No legacy `artifact/` or `ticket_log/` migration is included for this repository.

Primary process document:

- `main_artifact/development_process.md`
