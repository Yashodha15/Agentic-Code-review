"""FastAPI application factory for GitHub ingestion and Angular read APIs."""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Query, Request, status
from pydantic import ValidationError

from aegis_review.api.schemas import (
    HealthResponse,
    PullRequestWebhookPayload,
    ReviewRecord,
    ReviewTraceEvent,
    WebhookReceipt,
)
from aegis_review.config import ReviewPolicy
from aegis_review.github.webhooks import InvalidWebhookSignature, verify_webhook_signature
from aegis_review.models import ReviewFinding
from aegis_review.services.reviews import (
    InMemoryReviewJobPublisher,
    ReviewIngestionService,
    ReviewJobPublisher,
)
from aegis_review.storage.base import ReviewRepository
from aegis_review.storage.memory import InMemoryReviewRepository
from aegis_review.storage.policy import InMemoryPolicyStore, PolicyStore


SUPPORTED_PULL_REQUEST_ACTIONS = {"opened", "reopened", "synchronize", "ready_for_review"}
MAX_WEBHOOK_BYTES = 2 * 1024 * 1024


def create_app(
    *,
    webhook_secret: str,
    repository: ReviewRepository | None = None,
    jobs: ReviewJobPublisher | None = None,
    policy_store: PolicyStore | None = None,
) -> FastAPI:
    """Build an application with injectable storage and queue dependencies."""

    if not webhook_secret.strip():
        raise ValueError("A non-empty GitHub webhook secret is required.")

    review_repository = repository or InMemoryReviewRepository()
    job_publisher = jobs or InMemoryReviewJobPublisher()
    policies = policy_store or InMemoryPolicyStore()
    ingestion = ReviewIngestionService(review_repository, job_publisher)

    app = FastAPI(
        title="Aegis Review API",
        version="0.1.0",
        description="GitHub ingestion and maintenance API for multi-agent reviews.",
    )

    # Dependencies are exposed on app.state for worker wiring and focused tests;
    # endpoints still interact through explicit service contracts.
    app.state.review_repository = review_repository
    app.state.job_publisher = job_publisher

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post(
        "/api/v1/github/webhooks",
        response_model=WebhookReceipt,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["github"],
    )
    async def github_webhook(request: Request) -> WebhookReceipt:
        body = await request.body()
        if len(body) > MAX_WEBHOOK_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Webhook payload exceeds the configured size limit.",
            )

        try:
            verify_webhook_signature(
                body,
                request.headers.get("x-hub-signature-256"),
                webhook_secret,
            )
        except InvalidWebhookSignature as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
            ) from error

        event_name = request.headers.get("x-github-event")
        delivery_id = request.headers.get("x-github-delivery", "").strip()
        if not delivery_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-GitHub-Delivery header.",
            )
        if len(delivery_id) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-GitHub-Delivery header is too long.",
            )

        if event_name != "pull_request":
            return WebhookReceipt(
                accepted=False,
                reason=f"Event type {event_name or 'unknown'} is not handled.",
            )

        try:
            raw_payload = json.loads(body)
            payload = PullRequestWebhookPayload.model_validate(raw_payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Webhook body is not a valid pull-request payload.",
            ) from error

        if payload.action not in SUPPORTED_PULL_REQUEST_ACTIONS:
            return WebhookReceipt(
                accepted=False,
                reason=f"Pull-request action {payload.action} does not start a review.",
            )

        try:
            return ingestion.ingest(delivery_id, payload)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Review could not be queued.",
            ) from error

    @app.get(
        "/api/v1/reviews",
        response_model=list[ReviewRecord],
        tags=["reviews"],
    )
    def list_reviews(limit: int = Query(default=50, ge=1, le=200)) -> list[ReviewRecord]:
        return review_repository.list(limit=limit)

    @app.get(
        "/api/v1/reviews/{review_id}",
        response_model=ReviewRecord,
        tags=["reviews"],
    )
    def get_review(review_id: str) -> ReviewRecord:
        review = review_repository.get(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found.")
        return review

    @app.get(
        "/api/v1/reviews/{review_id}/traces",
        response_model=list[ReviewTraceEvent],
        tags=["reviews"],
    )
    def get_review_traces(review_id: str) -> list[ReviewTraceEvent]:
        try:
            return review_repository.list_traces(review_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Review not found.") from error

    @app.get(
        "/api/v1/reviews/{review_id}/findings",
        response_model=list[ReviewFinding],
        tags=["reviews"],
    )
    def get_review_findings(review_id: str) -> list[ReviewFinding]:
        try:
            return review_repository.list_findings(review_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Review not found.") from error

    @app.get("/api/v1/policy", response_model=ReviewPolicy, tags=["configuration"])
    def get_policy() -> ReviewPolicy:
        return policies.get()

    @app.put("/api/v1/policy", response_model=ReviewPolicy, tags=["configuration"])
    def update_policy(policy: ReviewPolicy) -> ReviewPolicy:
        return policies.save(policy)

    return app
