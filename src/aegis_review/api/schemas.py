"""Validated request and response contracts exposed by the platform API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewStatus(StrEnum):
    """Lifecycle persisted for an asynchronous pull-request review."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TraceStatus(StrEnum):
    """Execution state of one observable review step."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class GitHubRepositoryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(min_length=3)


class GitHubInstallationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)


class GitReferencePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sha: str = Field(min_length=7, max_length=64)


class GitHubPullRequestPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int = Field(gt=0)
    head: GitReferencePayload
    base: GitReferencePayload


class PullRequestWebhookPayload(BaseModel):
    """Minimal GitHub payload required to enqueue a review safely."""

    model_config = ConfigDict(extra="ignore")

    action: str
    repository: GitHubRepositoryPayload
    installation: GitHubInstallationPayload
    pull_request: GitHubPullRequestPayload


class ReviewRecord(BaseModel):
    """Public and persistent review state consumed by the Angular UI."""

    id: str
    delivery_id: str
    repository: str
    pull_request_number: int
    installation_id: int
    head_sha: str
    base_sha: str
    status: ReviewStatus
    created_at: datetime
    updated_at: datetime
    finding_count: int = 0
    completed_agents: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ReviewTraceEvent(BaseModel):
    """Append-only event displayed by the Angular agent-trace viewer."""

    sequence: int
    review_id: str
    stage: str
    status: TraceStatus
    detail: str
    created_at: datetime


class WebhookReceipt(BaseModel):
    """Stable webhook response returned for new and repeated deliveries."""

    accepted: bool
    duplicate: bool = False
    review_id: str | None = None
    reason: str | None = None


class HealthResponse(BaseModel):
    status: str

