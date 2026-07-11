# Agent Flow Demo Fixture

This fixture is for the local fake-runner demo:

```sh
python3 .core_program/app/03_agent_flow_demo/run_agent_flow_demo.py
```

The default sample queue is `queue/router_demo.md`. It targets the visible
`Session_router`. The demo runner then simulates one handoff to non-visible
`worker_A`, a pair of non-visible subagents, and a permission request that is
granted through the router. It does not call real GitHub or real Codex.

To see the blocked path:

```sh
python3 .core_program/app/03_agent_flow_demo/run_agent_flow_demo.py --permission deny
```
