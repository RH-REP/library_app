# main_artifact Contract

`main_artifact/` is the primary human-facing artifact area.

It owns:

- the production goal in `goal.md`
- the staged implementation plan in `development_process.md`
- review-gate decisions that change repository-level product direction

It does not own internal queue files, pending records, router diagnostics, or
session assignment state. Those belong under `.core_program/`.

It also does not replace `sub_artifact/`. Worker-owned production units belong
under `sub_artifact/NNN_slug/` after routing and worker initialization are
implemented in later stages.
