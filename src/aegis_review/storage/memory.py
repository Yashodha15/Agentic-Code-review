"""Thread-safe in-memory persistence for tests and local development."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock

from aegis_review.api.schemas import ReviewRecord, ReviewStatus, ReviewTraceEvent, TraceStatus
from aegis_review.models import ReviewFinding


class InMemoryReviewRepository:
    """Implements storage semantics without requiring a database service."""

    def __init__(self) -> None:
        self._reviews: dict[str, ReviewRecord] = {}
        self._delivery_index: dict[str, str] = {}
        self._traces: dict[str, list[ReviewTraceEvent]] = {}
        self._findings: dict[str, list[ReviewFinding]] = {}
        self._lock = RLock()

    def create_if_absent(self, review: ReviewRecord) -> tuple[ReviewRecord, bool]:
        with self._lock:
            existing_id = self._delivery_index.get(review.delivery_id)
            if existing_id is not None:
                return self._reviews[existing_id].model_copy(deep=True), False

            self._reviews[review.id] = review.model_copy(deep=True)
            self._delivery_index[review.delivery_id] = review.id
            self._traces[review.id] = []
            self._findings[review.id] = []
            return review.model_copy(deep=True), True

    def get(self, review_id: str) -> ReviewRecord | None:
        with self._lock:
            review = self._reviews.get(review_id)
            return review.model_copy(deep=True) if review else None

    def get_by_delivery(self, delivery_id: str) -> ReviewRecord | None:
        with self._lock:
            review_id = self._delivery_index.get(delivery_id)
            return self.get(review_id) if review_id else None

    def list(self, *, limit: int = 50) -> list[ReviewRecord]:
        with self._lock:
            ordered = sorted(
                self._reviews.values(), key=lambda item: item.created_at, reverse=True
            )
            return [item.model_copy(deep=True) for item in ordered[:limit]]

    def update_status(
        self, review_id: str, status: ReviewStatus, *, errors: list[str] | None = None
    ) -> ReviewRecord:
        with self._lock:
            current = self._reviews.get(review_id)
            if current is None:
                raise KeyError(review_id)
            updated = current.model_copy(
                update={
                    "status": status,
                    "errors": list(errors if errors is not None else current.errors),
                    "updated_at": datetime.now(UTC),
                },
                deep=True,
            )
            self._reviews[review_id] = updated
            return updated.model_copy(deep=True)

    def save_result(
        self,
        review_id: str,
        *,
        findings: list[ReviewFinding],
        completed_agents: list[str],
        errors: list[str],
    ) -> ReviewRecord:
        with self._lock:
            current = self._reviews.get(review_id)
            if current is None:
                raise KeyError(review_id)
            self._findings[review_id] = [item.model_copy(deep=True) for item in findings]
            updated = current.model_copy(
                update={
                    "status": ReviewStatus.COMPLETED,
                    "finding_count": len(findings),
                    "completed_agents": list(completed_agents),
                    "errors": list(errors),
                    "updated_at": datetime.now(UTC),
                },
                deep=True,
            )
            self._reviews[review_id] = updated
            return updated.model_copy(deep=True)

    def list_findings(self, review_id: str) -> list[ReviewFinding]:
        with self._lock:
            if review_id not in self._reviews:
                raise KeyError(review_id)
            return [item.model_copy(deep=True) for item in self._findings[review_id]]

    def append_trace(
        self, review_id: str, stage: str, status: TraceStatus, detail: str
    ) -> ReviewTraceEvent:
        with self._lock:
            if review_id not in self._reviews:
                raise KeyError(review_id)
            traces = self._traces[review_id]
            event = ReviewTraceEvent(
                sequence=len(traces) + 1,
                review_id=review_id,
                stage=stage,
                status=status,
                detail=detail,
                created_at=datetime.now(UTC),
            )
            traces.append(event)
            return event.model_copy(deep=True)

    def list_traces(self, review_id: str) -> list[ReviewTraceEvent]:
        with self._lock:
            if review_id not in self._reviews:
                raise KeyError(review_id)
            return [event.model_copy(deep=True) for event in self._traces[review_id]]
