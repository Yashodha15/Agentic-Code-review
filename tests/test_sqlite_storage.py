from datetime import UTC, datetime

from aegis_review.api.schemas import ReviewRecord, ReviewStatus, TraceStatus
from aegis_review.models import ReviewFinding, Severity
from aegis_review.storage.sqlite import SQLiteReviewJobQueue, SQLiteReviewRepository
from aegis_review.storage.policy import SQLitePolicyStore


def review(review_id: str = "review-1", delivery: str = "delivery-1") -> ReviewRecord:
    now = datetime.now(UTC)
    return ReviewRecord(
        id=review_id,
        delivery_id=delivery,
        repository="northstar/platform-api",
        pull_request_number=12,
        installation_id=42,
        head_sha="a" * 40,
        base_sha="b" * 40,
        status=ReviewStatus.QUEUED,
        created_at=now,
        updated_at=now,
    )


def finding() -> ReviewFinding:
    return ReviewFinding(
        title="Authorization bypass",
        category="security",
        severity=Severity.HIGH,
        confidence=0.94,
        path="src/access.py",
        line=10,
        comment="Run authorization before returning the cached object.",
        source_agent="security",
        status="verified",
    )


def test_sqlite_repository_persists_reviews_traces_and_findings(tmp_path) -> None:
    path = tmp_path / "aegis.db"
    first = SQLiteReviewRepository(path)
    stored, created = first.create_if_absent(review())
    assert created is True
    first.append_trace(stored.id, "worker", TraceStatus.RUNNING, "Started")
    first.save_result(
        stored.id,
        findings=[finding()],
        completed_agents=["security"],
        errors=[],
    )
    first.close()

    reopened = SQLiteReviewRepository(path)
    persisted = reopened.get("review-1")

    assert persisted is not None
    assert persisted.status == "completed"
    assert persisted.finding_count == 1
    assert reopened.list_findings("review-1")[0].title == "Authorization bypass"
    assert reopened.list_traces("review-1")[0].detail == "Started"
    reopened.close()


def test_sqlite_repository_enforces_delivery_idempotency(tmp_path) -> None:
    repository = SQLiteReviewRepository(tmp_path / "aegis.db")

    original, created = repository.create_if_absent(review())
    duplicate, created_again = repository.create_if_absent(
        review(review_id="different-id", delivery="delivery-1")
    )

    assert created is True
    assert created_again is False
    assert duplicate.id == original.id
    assert len(repository.list()) == 1
    repository.close()


def test_sqlite_job_queue_claims_each_job_once_and_persists_state(tmp_path) -> None:
    path = tmp_path / "aegis.db"
    queue = SQLiteReviewJobQueue(path)
    queue.enqueue("review-1")
    queue.enqueue("review-1")

    assert queue.claim_next() == "review-1"
    assert queue.claim_next() is None
    queue.complete("review-1")
    queue.close()

    reopened = SQLiteReviewJobQueue(path)
    assert reopened.claim_next() is None
    reopened.close()


def test_sqlite_policy_store_persists_configuration(tmp_path) -> None:
    path = tmp_path / "aegis.db"
    store = SQLitePolicyStore(path)
    policy = store.get().model_copy(update={"minimum_severity": Severity.HIGH})
    store.save(policy)

    reopened = SQLitePolicyStore(path)

    assert reopened.get().minimum_severity == "high"
