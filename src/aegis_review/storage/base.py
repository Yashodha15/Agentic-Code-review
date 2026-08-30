"""Persistence boundary used by the API and future background workers."""

from __future__ import annotations

from typing import Protocol

from aegis_review.api.schemas import ReviewRecord, ReviewStatus, ReviewTraceEvent, TraceStatus
from aegis_review.models import ReviewFinding


class ReviewRepository(Protocol):
    """Storage operations required by the current review lifecycle."""

    def create_if_absent(self, review: ReviewRecord) -> tuple[ReviewRecord, bool]: ...

    def get(self, review_id: str) -> ReviewRecord | None: ...

    def get_by_delivery(self, delivery_id: str) -> ReviewRecord | None: ...

    def list(self, *, limit: int = 50) -> list[ReviewRecord]: ...

    def update_status(
        self, review_id: str, status: ReviewStatus, *, errors: list[str] | None = None
    ) -> ReviewRecord: ...

    def save_result(
        self,
        review_id: str,
        *,
        findings: list[ReviewFinding],
        completed_agents: list[str],
        errors: list[str],
    ) -> ReviewRecord: ...

    def list_findings(self, review_id: str) -> list[ReviewFinding]: ...

    def append_trace(
        self, review_id: str, stage: str, status: TraceStatus, detail: str
    ) -> ReviewTraceEvent: ...

    def list_traces(self, review_id: str) -> list[ReviewTraceEvent]: ...
