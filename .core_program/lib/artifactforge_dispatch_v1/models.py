"""Shared models for ArtifactForge issue dispatch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IssueComment:
    comment_id: str
    author: str | None
    body: str
    created_at: str
    updated_at: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class IssueSnapshot:
    issue_number: int
    issue_state: str
    issue_url: str
    title: str
    body: str
    created_at: str | None = None
    updated_at: str | None = None
    comments: tuple[IssueComment, ...] = ()


@dataclass(frozen=True)
class IssueEvent:
    issue_number: int
    issue_url: str
    issue_title: str
    event_type: str
    trigger_fingerprint: str
    body: str
    source_id: str | None = None
    source_url: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class AgentMarker:
    thread_id: str | None
    trigger_fingerprint: str
    status: str
    issue_number: int
    created_at: str | None = None
    comment_id: str | None = None


@dataclass(frozen=True)
class QueueRecord:
    issue_number: int
    issue_url: str
    issue_title: str
    event_type: str
    trigger_fingerprint: str
    target_session_id: str
    prompt_kind: str
    body: str
    source_id: str | None
    sub_artifact_path: str | None = None
    previous_thread_id: str | None = None
    reassign_required: bool = False


@dataclass(frozen=True)
class PendingRecord:
    session_id: str
    trigger_fingerprint: str
    path: str
