# ArtifactForge

ArtifactForge is a repository for turning one main production goal and GitHub
issue requests into coordinated AI worker sessions.

This repository starts from the new directory contract. The canonical
user-facing names are:

```text
main_artifact/  # primary goal, process, and human-facing product direction
sub_artifact/   # worker-owned production units created from routed issues
issue_log/      # human-facing issue-work log
.core_program/  # internal automation contracts, queues, state, and diagnostics
```

There is no top-level `artifact/` directory contract and no `ticket_log/`
contract in this repository.

## Stage 0 Contract

Stage 0 fixes names and boundaries only. It does not implement issue routing,
GitHub fetching, or worker dispatch.

| Path | Responsibility |
| --- | --- |
| `main_artifact/goal.md` | The one human-facing production goal. |
| `main_artifact/development_process.md` | Stage plan and review gates. |
| `sub_artifact/` | Future worker-owned units, one directory per current assignment. |
| `issue_log/` | Human-facing issue history and review notes. |
| `.core_program/` | Machine-facing engine state, prompts, queues, and diagnostics. |

The internal lifecycle names reserved under `.core_program/` are:

| Name | Path |
| --- | --- |
| Queue | `.core_program/queue/` |
| Pending | `.core_program/pending/` |
| Archive | `.core_program/archive/` |
| Router session | `.core_program/router_session_id.txt` |
| Assignment state | `.core_program/assignment_state.json` |

The router session and assignment state files are reserved names. Later stages
will define their exact schemas and behavior.
