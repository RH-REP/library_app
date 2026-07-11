# sub_artifact

`sub_artifact/` contains intermediate outputs, parts, investigations,
prototypes, and helper work used to complete or improve the primary artifact in
`main_artifact/`.
This README is a short entry note for people or AI agents who open this
directory directly. Human users normally read the root `README.md` and
`USER_MANUAL.md` only.

Workers create numbered sub-artifact directories on first real work:

```text
sub_artifact/NNN_slug/
```

Each initialized sub-artifact contains:

```text
sub_goal.md
plan.md
work_log.md
artifact.md
```

The first worker that owns a new assignment initializes these files. Re-running
the same assignment must be idempotent and must not create a second path for the
same current assignment.

`sub_artifact/` does not own the main production goal, repository process, issue
log, queue state, pending state, or router diagnostics.

The future `artifact.md` file is scoped inside a numbered sub-artifact
directory. It is not a dependency on a legacy top-level `artifact/` directory.
