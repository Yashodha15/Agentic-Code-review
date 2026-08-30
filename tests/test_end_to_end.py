"""Complete local path: GitHub webhook -> durable queue -> graph -> API results."""

import hashlib
import hmac
import json
from pathlib import Path

from fastapi.testclient import TestClient

from aegis_review.api.app import create_app
from aegis_review.github.client import FakeGitHubReviewClient, PullRequestContext
from aegis_review.models import ReviewFinding, Severity
from aegis_review.providers.fake import FakeReviewProvider
from aegis_review.storage.policy import SQLitePolicyStore
from aegis_review.storage.sqlite import (
    SQLiteReviewJobQueue,
    SQLiteReviewRepository,
    SQLiteWorkerRunner,
)
from aegis_review.worker import ReviewWorker


SECRET = "end-to-end-secret"
FIXTURE = Path(__file__).parent / "fixtures" / "sample_pr.diff"


def test_complete_local_review_lifecycle(tmp_path) -> None:
    database = tmp_path / "aegis.db"
    repository = SQLiteReviewRepository(database)
    queue = SQLiteReviewJobQueue(database)
    policies = SQLitePolicyStore(database)
    app = create_app(
        webhook_secret=SECRET,
        repository=repository,
        jobs=queue,
        policy_store=policies,
    )
    client = TestClient(app)
    github = FakeGitHubReviewClient(
        PullRequestContext(
            diff_text=FIXTURE.read_text(encoding="utf-8"),
            manifests={"requirements.txt": "fastapi"},
        )
    )
    finding = ReviewFinding(
        title="Cached access policy bypass",
        category="security",
        severity=Severity.HIGH,
        confidence=0.96,
        path="src/access.py",
        line=10,
        comment="Authorize the caller before returning a cached resource.",
        source_agent="fixture",
    )
    provider = FakeReviewProvider({"security": [finding]})
    worker = ReviewWorker(
        repository=repository,
        github=github,
        provider=provider,
        policy_store=policies,
    )
    runner = SQLiteWorkerRunner(queue, worker)

    payload = {
        "action": "opened",
        "repository": {"full_name": "northstar/platform-api"},
        "installation": {"id": 42},
        "pull_request": {
            "number": 482,
            "head": {"sha": "a" * 40},
            "base": {"sha": "b" * 40},
        },
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    response = client.post(
        "/api/v1/github/webhooks",
        content=body,
        headers={
            "X-Hub-Signature-256": f"sha256={signature}",
            "X-GitHub-Delivery": "e2e-delivery",
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    review_id = response.json()["review_id"]

    assert response.status_code == 202
    assert runner.run_once() is True
    assert runner.run_once() is False

    review = client.get(f"/api/v1/reviews/{review_id}").json()
    findings = client.get(f"/api/v1/reviews/{review_id}/findings").json()
    traces = client.get(f"/api/v1/reviews/{review_id}/traces").json()

    assert review["status"] == "completed"
    assert review["finding_count"] == 1
    assert findings[0]["status"] == "verified"
    assert traces[0]["stage"] == "webhook"
    assert traces[-1]["stage"] == "publish"
    assert len(github.published) == 1

