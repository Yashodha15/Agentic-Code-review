"""Repository policy persistence for the maintenance API."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol

from aegis_review.config import ReviewPolicy


class PolicyStore(Protocol):
    def get(self) -> ReviewPolicy: ...

    def save(self, policy: ReviewPolicy) -> ReviewPolicy: ...


class InMemoryPolicyStore:
    def __init__(self, policy: ReviewPolicy | None = None) -> None:
        self._policy = (policy or ReviewPolicy()).model_copy(deep=True)

    def get(self) -> ReviewPolicy:
        return self._policy.model_copy(deep=True)

    def save(self, policy: ReviewPolicy) -> ReviewPolicy:
        self._policy = policy.model_copy(deep=True)
        return self.get()


class SQLitePolicyStore:
    """Stores the active versioned policy in the local deployment database."""

    def __init__(self, database_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._lock = RLock()
        with self._connection:
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS platform_policy (id INTEGER PRIMARY KEY CHECK (id = 1), payload_json TEXT NOT NULL)"
            )

    def get(self) -> ReviewPolicy:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json FROM platform_policy WHERE id = 1"
            ).fetchone()
            return ReviewPolicy.model_validate_json(row[0]) if row else ReviewPolicy()

    def save(self, policy: ReviewPolicy) -> ReviewPolicy:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO platform_policy (id, payload_json) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (policy.model_dump_json(),),
            )
            return policy.model_copy(deep=True)

