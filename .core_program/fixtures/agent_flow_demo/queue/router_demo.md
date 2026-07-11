# ArtifactForge Issue Event

## Routing
- prompt_kind: session_router
- recipient_role: router
- target_session_id: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa
- reassign_required: false
- sub_artifact_path: sub_artifact/001_agent_flow_demo_software

## Issue Event
- issue_number: 1
- issue_title: Agent flow demo software
- issue_url: https://github.example.test/acme/demo/issues/1
- event_type: thread_update
- source_id: body..comment-demo
- trigger_fingerprint: issue-1-thread-body-comment-demo-sha256-0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

## Body

## Issue body
- author: demo-user
- created_at: 2026-07-11T00:00:00Z

ArtifactForge の agent hierarchy を確認するため、最小の demo software を作り、
worker_A が subagent_A1 に実装、subagent_A2 に検証を依頼してください。
subagent_A1 がファイル作成権限を必要とする場合は、Session_router 経由で確認してください。

