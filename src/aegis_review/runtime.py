"""Environment-driven application wiring for local and container deployment."""

from __future__ import annotations

from aegis_review.api.app import create_app
from aegis_review.settings import database_path, required_environment
from aegis_review.storage.sqlite import SQLiteReviewJobQueue, SQLiteReviewRepository
from aegis_review.storage.policy import SQLitePolicyStore

def create_runtime_app():
    """Create the durable API application used by Uvicorn."""

    path = database_path()
    repository = SQLiteReviewRepository(path)
    queue = SQLiteReviewJobQueue(path)
    policies = SQLitePolicyStore(path)
    return create_app(
        webhook_secret=required_environment("GITHUB_WEBHOOK_SECRET"),
        repository=repository,
        jobs=queue,
        policy_store=policies,
    )


app = create_runtime_app()
