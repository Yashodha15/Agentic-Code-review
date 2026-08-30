from datetime import UTC, datetime
from pathlib import Path

import pytest

from aegis_review.api.schemas import ReviewRecord, ReviewStatus
from aegis_review.github.client import FakeGitHubReviewClient, PullRequestContext
from aegis_review.models import ReviewFinding, Severity
from aegis_review.providers.fake import FakeReviewProvider
from aegis_review.storage.memory import InMemoryReviewRepository
from aegis_review.worker import ReviewWorker


FIXTURE = Path(__file__).parent / "fixtures" / "sample_pr.diff"


def queued_review() -> ReviewRecord:
    now = datetime.now(UTC)
    return ReviewRecord(
        id="review-1",
        delivery_id="delivery-1",
        repository="northstar/platform-api",
        pull_request_number=482,
        installation_id=42,
        head_sha="a" * 40,
        base_sha="b" * 40,
        status=ReviewStatus.QUEUED,
        created_at=now,
        updated_at=now,
    )


def verified_finding() -> ReviewFinding:
    return ReviewFinding(
        title="Cached access policy bypass",
        category="security",
        severity=Severity.HIGH,
        confidence=0.95,
        path="src/access.py",
        line=10,
        comment="Run the access check before returning the cached object.",
        evidence=["The cached path returns before require_access."],
        source_agent="fixture",
    )


def setup_worker(*, publish_error: Exception | None = None):
    repository = InMemoryReviewRepository()
    repository.create_if_absent(queued_review())
    github = FakeGitHubReviewClient(
        PullRequestContext(
            diff_text=FIXTURE.read_text(encoding="utf-8"),
            manifests={"requirements.txt": "fastapi"},
        ),
        publish_error=publish_error,
    )
    provider = FakeReviewProvider(
        {
            "security": [verified_finding()],
            "correctness": [],
            "testing": [],
        }
    )
    worker = ReviewWorker(
        repository=repository,
        github=github,
        provider=provider,
    )
    return worker, repository, github, provider


def test_worker_completes_review_persists_findings_and_publishes() -> None:
    worker, repository, github, provider = setup_worker()

    worker.process("review-1")

    stored = repository.get("review-1")
    assert stored is not None
    assert stored.status == "completed"
    assert stored.finding_count == 1
    assert set(stored.completed_agents) == {"security", "correctness", "testing"}
    assert repository.list_findings("review-1")[0].status == "verified"
    assert len(github.published) == 1
    assert {
        request.lead_agent
        for request in provider.requests
        if request.parent_agent is None
    } == {
        "security",
        "correctness",
        "testing",
    }
    stages = [event.stage for event in repository.list_traces("review-1")]
    assert stages[0:2] == ["worker", "planning"]
    assert stages[-1] == "publish"


def test_worker_marks_review_failed_when_github_context_fails() -> None:
    worker, repository, github, _ = setup_worker()

    def fail_fetch(review):
        raise RuntimeError("GitHub unavailable")

    github.fetch_context = fail_fetch

    with pytest.raises(RuntimeError, match="GitHub unavailable"):
        worker.process("review-1")

    stored = repository.get("review-1")
    assert stored is not None
    assert stored.status == "failed"
    assert "GitHub unavailable" in stored.errors[0]
    assert repository.list_traces("review-1")[-1].status == "failed"


def test_worker_retains_findings_but_marks_failure_when_publish_fails() -> None:
    worker, repository, _, _ = setup_worker(
        publish_error=RuntimeError("review API unavailable")
    )

    with pytest.raises(RuntimeError, match="review API unavailable"):
        worker.process("review-1")

    stored = repository.get("review-1")
    assert stored is not None
    assert stored.status == "failed"
    assert stored.finding_count == 1
    assert len(repository.list_findings("review-1")) == 1


def test_worker_rejects_unknown_or_already_completed_reviews() -> None:
    worker, repository, _, _ = setup_worker()

    with pytest.raises(KeyError):
        worker.process("missing")

    repository.update_status("review-1", ReviewStatus.COMPLETED)
    with pytest.raises(ValueError, match="cannot run"):
        worker.process("review-1")
