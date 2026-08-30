"""Durable SQLite persistence for a complete single-node deployment."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from aegis_review.api.schemas import ReviewRecord, ReviewStatus, ReviewTraceEvent, TraceStatus
from aegis_review.models import ReviewFinding


class SQLiteReviewRepository:
    """Durable repository implementing the same contract as PostgreSQL will use.

    SQLite is intentionally the default local deployment: it provides real
    restart durability without requiring infrastructure. The storage contract
    keeps migration to PostgreSQL isolated from the API and worker.
    """

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _migrate(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                PRAGMA journal_mode = WAL;
                PRAGMA busy_timeout = 5000;
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    delivery_id TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_traces (
                    review_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (review_id, sequence),
                    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS review_findings (
                    review_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (review_id, position),
                    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _review_from_row(row: sqlite3.Row | None) -> ReviewRecord | None:
        return ReviewRecord.model_validate_json(row["payload_json"]) if row else None

    def create_if_absent(self, review: ReviewRecord) -> tuple[ReviewRecord, bool]:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO reviews (id, delivery_id, payload_json) VALUES (?, ?, ?)",
                (review.id, review.delivery_id, review.model_dump_json()),
            )
            if cursor.rowcount == 1:
                return review.model_copy(deep=True), True
            row = self._connection.execute(
                "SELECT payload_json FROM reviews WHERE delivery_id = ?",
                (review.delivery_id,),
            ).fetchone()
            existing = self._review_from_row(row)
            if existing is None:  # Defensive guard for unexpected database corruption.
                raise RuntimeError("Delivery index exists without a review record.")
            return existing, False

    def get(self, review_id: str) -> ReviewRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json FROM reviews WHERE id = ?", (review_id,)
            ).fetchone()
            return self._review_from_row(row)

    def get_by_delivery(self, delivery_id: str) -> ReviewRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json FROM reviews WHERE delivery_id = ?", (delivery_id,)
            ).fetchone()
            return self._review_from_row(row)

    def list(self, *, limit: int = 50) -> list[ReviewRecord]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload_json FROM reviews ORDER BY rowid DESC LIMIT ?", (limit,)
            ).fetchall()
            return [ReviewRecord.model_validate_json(row["payload_json"]) for row in rows]

    def _replace_review(self, review: ReviewRecord) -> None:
        self._connection.execute(
            "UPDATE reviews SET payload_json = ? WHERE id = ?",
            (review.model_dump_json(), review.id),
        )

    def update_status(
        self, review_id: str, status: ReviewStatus, *, errors: list[str] | None = None
    ) -> ReviewRecord:
        with self._lock, self._connection:
            current = self.get(review_id)
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
            self._replace_review(updated)
            return updated.model_copy(deep=True)

    def save_result(
        self,
        review_id: str,
        *,
        findings: list[ReviewFinding],
        completed_agents: list[str],
        errors: list[str],
    ) -> ReviewRecord:
        with self._lock, self._connection:
            current = self.get(review_id)
            if current is None:
                raise KeyError(review_id)
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
            self._replace_review(updated)
            self._connection.execute(
                "DELETE FROM review_findings WHERE review_id = ?", (review_id,)
            )
            self._connection.executemany(
                "INSERT INTO review_findings (review_id, position, payload_json) VALUES (?, ?, ?)",
                [
                    (review_id, position, finding.model_dump_json())
                    for position, finding in enumerate(findings)
                ],
            )
            return updated.model_copy(deep=True)

    def list_findings(self, review_id: str) -> list[ReviewFinding]:
        with self._lock:
            if self.get(review_id) is None:
                raise KeyError(review_id)
            rows = self._connection.execute(
                "SELECT payload_json FROM review_findings WHERE review_id = ? ORDER BY position",
                (review_id,),
            ).fetchall()
            return [ReviewFinding.model_validate_json(row["payload_json"]) for row in rows]

    def append_trace(
        self, review_id: str, stage: str, status: TraceStatus, detail: str
    ) -> ReviewTraceEvent:
        with self._lock, self._connection:
            if self.get(review_id) is None:
                raise KeyError(review_id)
            row = self._connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS maximum FROM review_traces WHERE review_id = ?",
                (review_id,),
            ).fetchone()
            event = ReviewTraceEvent(
                sequence=int(row["maximum"]) + 1,
                review_id=review_id,
                stage=stage,
                status=status,
                detail=detail,
                created_at=datetime.now(UTC),
            )
            self._connection.execute(
                "INSERT INTO review_traces (review_id, sequence, payload_json) VALUES (?, ?, ?)",
                (review_id, event.sequence, event.model_dump_json()),
            )
            return event

    def list_traces(self, review_id: str) -> list[ReviewTraceEvent]:
        with self._lock:
            if self.get(review_id) is None:
                raise KeyError(review_id)
            rows = self._connection.execute(
                "SELECT payload_json FROM review_traces WHERE review_id = ? ORDER BY sequence",
                (review_id,),
            ).fetchall()
            return [ReviewTraceEvent.model_validate_json(row["payload_json"]) for row in rows]


class SQLiteReviewJobQueue:
    """Durable single-node queue with explicit claim and completion states."""

    def __init__(self, database_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        with self._connection:
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_jobs (
                    review_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def enqueue(self, review_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO review_jobs
                    (review_id, status, attempts, created_at, updated_at)
                VALUES (?, 'queued', 0, ?, ?)
                ON CONFLICT(review_id) DO NOTHING
                """,
                (review_id, now, now),
            )

    def claim_next(self) -> str | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT review_id FROM review_jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            review_id = str(row["review_id"])
            self._connection.execute(
                """
                UPDATE review_jobs
                SET status = 'running', attempts = attempts + 1, updated_at = ?
                WHERE review_id = ? AND status = 'queued'
                """,
                (datetime.now(UTC).isoformat(), review_id),
            )
            return review_id

    def complete(self, review_id: str) -> None:
        self._set_terminal(review_id, "completed", None)

    def fail(self, review_id: str, error: str) -> None:
        self._set_terminal(review_id, "failed", error)

    def _set_terminal(self, review_id: str, status: str, error: str | None) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE review_jobs SET status = ?, last_error = ?, updated_at = ? WHERE review_id = ?",
                (status, error, datetime.now(UTC).isoformat(), review_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(review_id)


class SQLiteWorkerRunner:
    """Claims one durable job and delegates its execution to a review worker."""

    def __init__(self, queue: SQLiteReviewJobQueue, worker) -> None:
        self.queue = queue
        self.worker = worker

    def run_once(self) -> bool:
        review_id = self.queue.claim_next()
        if review_id is None:
            return False
        try:
            self.worker.process(review_id)
        except Exception as error:
            self.queue.fail(review_id, f"{type(error).__name__}: {error}")
            return True
        self.queue.complete(review_id)
        return True
