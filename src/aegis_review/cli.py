"""Operational commands for the API and durable review worker."""

from __future__ import annotations

import argparse
import os
import time

import uvicorn

from pathlib import Path

from aegis_review.github.client import (
    GitHubAppTokenProvider,
    HttpGitHubReviewClient,
    StaticTokenProvider,
)
from aegis_review.providers.anthropic import AnthropicReviewProvider
from aegis_review.settings import database_path, required_environment
from aegis_review.storage.sqlite import (
    SQLiteReviewJobQueue,
    SQLiteReviewRepository,
    SQLiteWorkerRunner,
)
from aegis_review.storage.policy import SQLitePolicyStore
from aegis_review.worker import ReviewWorker


def build_worker_runner() -> SQLiteWorkerRunner:
    """Wire a production worker from environment-controlled integrations."""

    # ChatAnthropic reads ANTHROPIC_API_KEY itself, but checking it here avoids
    # claiming a job before discovering a deployment configuration error.
    required_environment("ANTHROPIC_API_KEY")
    path = database_path()
    repository = SQLiteReviewRepository(path)
    queue = SQLiteReviewJobQueue(path)
    policies = SQLitePolicyStore(path)
    github_api_url = os.getenv("GITHUB_API_URL", "https://api.github.com")
    static_token = os.getenv("GITHUB_TOKEN", "").strip()
    if static_token:
        token_provider = StaticTokenProvider(static_token)
    else:
        private_key_path = Path(required_environment("GITHUB_APP_PRIVATE_KEY_PATH"))
        token_provider = GitHubAppTokenProvider(
            app_id=required_environment("GITHUB_APP_ID"),
            private_key=private_key_path.read_text(encoding="utf-8"),
            base_url=github_api_url,
        )
    github = HttpGitHubReviewClient(token_provider, base_url=github_api_url)
    provider = AnthropicReviewProvider(model=required_environment("AEGIS_MODEL"))
    worker = ReviewWorker(
        repository=repository,
        github=github,
        provider=provider,
        policy_store=policies,
    )
    return SQLiteWorkerRunner(queue, worker)


def run_worker_loop(poll_seconds: float) -> None:
    runner = build_worker_runner()
    while True:
        processed = runner.run_once()
        if not processed:
            time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Code Review operational commands")
    subcommands = parser.add_subparsers(dest="command", required=True)
    api = subcommands.add_parser("api", help="Start the FastAPI server")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8000)
    subcommands.add_parser("worker-once", help="Process at most one queued review")
    worker = subcommands.add_parser("worker", help="Continuously process queued reviews")
    worker.add_argument("--poll-seconds", type=float, default=2.0)
    arguments = parser.parse_args()

    if arguments.command == "api":
        uvicorn.run(
            "aegis_review.runtime:app",
            host=arguments.host,
            port=arguments.port,
            factory=False,
        )
    elif arguments.command == "worker-once":
        build_worker_runner().run_once()
    else:
        run_worker_loop(max(0.25, arguments.poll_seconds))


if __name__ == "__main__":
    main()
