from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from aegis_review.api.app import create_app
from aegis_review.services.reviews import InMemoryReviewJobPublisher
from aegis_review.storage.memory import InMemoryReviewRepository


SECRET = "integration-test-webhook-secret"


def pull_request_payload(action: str = "opened") -> dict:
    return {
        "action": action,
        "repository": {"full_name": "northstar/platform-api"},
        "installation": {"id": 42},
        "pull_request": {
            "number": 482,
            "head": {"sha": "a" * 40},
            "base": {"sha": "b" * 40},
        },
    }


def signed_headers(body: bytes, *, delivery: str = "delivery-1", event: str = "pull_request") -> dict[str, str]:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {
        "X-Hub-Signature-256": f"sha256={digest}",
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": event,
        "Content-Type": "application/json",
    }


def make_client():
    repository = InMemoryReviewRepository()
    jobs = InMemoryReviewJobPublisher()
    app = create_app(webhook_secret=SECRET, repository=repository, jobs=jobs)
    return TestClient(app), repository, jobs


class FailingJobPublisher:
    def enqueue(self, review_id: str) -> None:
        raise RuntimeError("queue unavailable")


def post_payload(client: TestClient, payload: dict, **header_options):
    body = json.dumps(payload, separators=(",", ":")).encode()
    return client.post(
        "/api/v1/github/webhooks",
        content=body,
        headers=signed_headers(body, **header_options),
    )


def test_health_endpoint() -> None:
    client, _, _ = make_client()

    assert client.get("/health").json() == {"status": "ok"}


def test_application_requires_a_webhook_secret() -> None:
    import pytest

    with pytest.raises(ValueError, match="webhook secret"):
        create_app(webhook_secret="  ")


def test_valid_pull_request_delivery_creates_and_queues_review() -> None:
    client, repository, jobs = make_client()

    response = post_payload(client, pull_request_payload())

    assert response.status_code == 202
    receipt = response.json()
    assert receipt["accepted"] is True
    assert receipt["duplicate"] is False
    assert jobs.review_ids == [receipt["review_id"]]

    review = repository.get(receipt["review_id"])
    assert review is not None
    assert review.repository == "northstar/platform-api"
    assert review.status == "queued"
    assert [event.stage for event in repository.list_traces(review.id)] == [
        "webhook",
        "queue",
    ]


def test_repeated_delivery_is_idempotent_and_not_queued_twice() -> None:
    client, _, jobs = make_client()

    first = post_payload(client, pull_request_payload(), delivery="same-delivery")
    second = post_payload(client, pull_request_payload(), delivery="same-delivery")

    assert second.status_code == 202
    assert second.json()["duplicate"] is True
    assert second.json()["review_id"] == first.json()["review_id"]
    assert jobs.review_ids == [first.json()["review_id"]]


def test_invalid_signature_is_rejected_before_payload_processing() -> None:
    client, repository, jobs = make_client()

    response = client.post(
        "/api/v1/github/webhooks",
        content=b"not-json",
        headers={
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Delivery": "bad-delivery",
            "X-GitHub-Event": "pull_request",
        },
    )

    assert response.status_code == 401
    assert repository.list() == []
    assert jobs.review_ids == []


def test_unhandled_event_and_action_do_not_create_reviews() -> None:
    client, repository, jobs = make_client()
    body = json.dumps({"zen": "hello"}).encode()

    event_response = client.post(
        "/api/v1/github/webhooks",
        content=body,
        headers=signed_headers(body, delivery="ping-1", event="ping"),
    )
    action_response = post_payload(
        client, pull_request_payload("closed"), delivery="closed-1"
    )

    assert event_response.json()["accepted"] is False
    assert action_response.json()["accepted"] is False
    assert repository.list() == []
    assert jobs.review_ids == []


def test_review_and_trace_endpoints_return_created_data() -> None:
    client, _, _ = make_client()
    receipt = post_payload(client, pull_request_payload()).json()

    reviews = client.get("/api/v1/reviews").json()
    review = client.get(f"/api/v1/reviews/{receipt['review_id']}").json()
    traces = client.get(f"/api/v1/reviews/{receipt['review_id']}/traces").json()
    findings = client.get(f"/api/v1/reviews/{receipt['review_id']}/findings").json()

    assert len(reviews) == 1
    assert review["pull_request_number"] == 482
    assert [trace["stage"] for trace in traces] == ["webhook", "queue"]
    assert findings == []


def test_unknown_review_returns_not_found() -> None:
    client, _, _ = make_client()

    assert client.get("/api/v1/reviews/missing").status_code == 404
    assert client.get("/api/v1/reviews/missing/traces").status_code == 404
    assert client.get("/api/v1/reviews/missing/findings").status_code == 404


def test_policy_can_be_read_and_updated() -> None:
    client, _, _ = make_client()
    policy = client.get("/api/v1/policy").json()
    policy["minimum_severity"] = "high"
    policy["limits"]["maximum_comments"] = 5

    response = client.put("/api/v1/policy", json=policy)

    assert response.status_code == 200
    assert client.get("/api/v1/policy").json()["minimum_severity"] == "high"
    assert client.get("/api/v1/policy").json()["limits"]["maximum_comments"] == 5


def test_queue_failure_marks_review_failed_and_returns_service_unavailable() -> None:
    repository = InMemoryReviewRepository()
    app = create_app(
        webhook_secret=SECRET,
        repository=repository,
        jobs=FailingJobPublisher(),
    )
    client = TestClient(app)

    response = post_payload(client, pull_request_payload())

    assert response.status_code == 503
    stored = repository.list()
    assert len(stored) == 1
    assert stored[0].status == "failed"
    assert "queue unavailable" in stored[0].errors[0]
    assert repository.list_traces(stored[0].id)[-1].status == "failed"
