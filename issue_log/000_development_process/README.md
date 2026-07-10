# Development Process Log

This log records the initial split of the ArtifactForge development process.

Created decisions:

- Development is split into six implementation stages plus Stage 0 setup.
- Three review gates are required:
  - Review 1: structure and naming
  - Review 2: routing contract
  - Review 3: end-to-end operation
- `README.md` gives the user a first-issue template with three core questions
  and optional supporting questions.
- `README.md` includes an AI-agent comment block that users paste into the first issue.
- `main_artifact/.goal_template.md` is the source template for project-specific `goal.md`.
- `main_artifact/.development_process_template.md` is the source template for project-specific `development_process.md`.
- `main_artifact/goal.md` and `main_artifact/development_process.md` are project-specific data and should not be pushed to ArtifactForge upstream.
- `issue_log/` is the local issue-work log name.
- `.core_program/queue/`, `.core_program/pending/`, and
  `.core_program/archive/` are the reserved internal lifecycle directories.
- `.core_program/router_session_id.txt` is the reserved router session config.
- `.core_program/assignment_state.json` is the reserved assignment state file.
- Completion is detected asynchronously by later issue fetches.
- No legacy `artifact/` or `ticket_log/` migration is included for this repository.

Source process template:

- `main_artifact/.development_process_template.md`

Generated project process document:

- `main_artifact/development_process.md`
