"""Review-ingestion service and background-job publishing contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from aegis_review.api.schemas import (
    PullRequestWebhookPayload,
    ReviewRecord,
    ReviewStatus,
    TraceStatus,
    WebhookReceipt,
)
from aegis_review.storage.base import ReviewRepository


class ReviewJobPublisher(Protocol):
    """Queue boundary replaced by Redis or a durable workflow system later."""

    def enqueue(self, review_id: str) -> None: ...


class InMemoryReviewJobPublisher:
    """Inspectable queue used by API tests and local development."""

    def __init__(self) -> None:
        self.review_ids: list[str] = []

    def enqueue(self, review_id: str) -> None:
        self.review_ids.append(review_id)


class ReviewIngestionService:
    """Create an idempotent review record and enqueue its execution."""

    def __init__(self, repository: ReviewRepository, jobs: ReviewJobPublisher) -> None:
        self.repository = repository
        self.jobs = jobs

    def ingest(
        self, delivery_id: str, payload: PullRequestWebhookPayload
    ) -> WebhookReceipt:
        now = datetime.now(UTC)
        candidate = ReviewRecord(
            id=str(uuid4()),
            delivery_id=delivery_id,
            repository=payload.repository.full_name,
            pull_request_number=payload.pull_request.number,
            installation_id=payload.installation.id,
            head_sha=payload.pull_request.head.sha,
            base_sha=payload.pull_request.base.sha,
            status=ReviewStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        review, created = self.repository.create_if_absent(candidate)

        if not created:
            return WebhookReceipt(
                accepted=True, duplicate=True, review_id=review.id
            )

        self.repository.append_trace(
            review.id,
            "webhook",
            TraceStatus.COMPLETED,
            f"Accepted {payload.action} event for {payload.repository.full_name} "
            f"PR #{payload.pull_request.number}.",
        )

        try:
            self.jobs.enqueue(review.id)
        except Exception as error:
            message = f"Job enqueue failed: {type(error).__name__}: {error}"
            self.repository.update_status(review.id, ReviewStatus.FAILED, errors=[message])
            self.repository.append_trace(
                review.id, "queue", TraceStatus.FAILED, message
            )
            raise

        self.repository.append_trace(
            review.id, "queue", TraceStatus.QUEUED, "Review execution was queued."
        )
        return WebhookReceipt(accepted=True, review_id=review.id)

