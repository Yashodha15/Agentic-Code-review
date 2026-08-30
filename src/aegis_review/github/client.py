"""GitHub pull-request context and review publication clients."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Protocol

import httpx
import jwt

from aegis_review.api.schemas import ReviewRecord
from aegis_review.models import ReviewFinding


MANIFEST_PATHS = (
    "package.json",
    "angular.json",
    "tsconfig.json",
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "manage.py",
)


def _review_event(errors: list[str]) -> str:
    """Fail closed when any selected review step did not complete."""

    return "REQUEST_CHANGES" if errors else "COMMENT"


@dataclass(frozen=True)
class PullRequestContext:
    """Repository data required by adapters and review agents."""

    diff_text: str
    manifests: dict[str, str] = field(default_factory=dict)


class GitHubTokenProvider(Protocol):
    """Provides a short-lived installation token without exposing its source."""

    def installation_token(self, installation_id: int) -> str: ...


class GitHubReviewClient(Protocol):
    """GitHub operations required by the background review worker."""

    def fetch_context(self, review: ReviewRecord) -> PullRequestContext: ...

    def publish_review(
        self,
        review: ReviewRecord,
        findings: list[ReviewFinding],
        errors: list[str],
    ) -> None: ...


class StaticTokenProvider:
    """Token source suitable for local development, never browser clients."""

    def __init__(self, token: str) -> None:
        if not token.strip():
            raise ValueError("A non-empty GitHub token is required.")
        self._token = token

    def installation_token(self, installation_id: int) -> str:
        return self._token


class GitHubAppTokenProvider:
    """Creates and caches short-lived GitHub App installation tokens."""

    def __init__(
        self,
        *,
        app_id: str,
        private_key: str,
        base_url: str = "https://api.github.com",
        timeout_seconds: float = 20.0,
    ) -> None:
        if not app_id.strip() or not private_key.strip():
            raise ValueError("GitHub App ID and private key are required.")
        self._app_id = app_id
        self._private_key = private_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._cache: dict[int, tuple[str, datetime]] = {}
        self._lock = RLock()

    def installation_token(self, installation_id: int) -> str:
        with self._lock:
            cached = self._cache.get(installation_id)
            now = datetime.now(UTC)
            if cached is not None and cached[1] > now + timedelta(minutes=2):
                return cached[0]

            app_jwt = jwt.encode(
                {
                    "iat": int((now - timedelta(seconds=30)).timestamp()),
                    "exp": int((now + timedelta(minutes=9)).timestamp()),
                    "iss": self._app_id,
                },
                self._private_key,
                algorithm="RS256",
            )
            response = httpx.post(
                f"{self._base_url}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            expires_at = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
            token = str(payload["token"])
            self._cache[installation_id] = (token, expires_at)
            return token


class HttpGitHubReviewClient:
    """GitHub REST implementation using installation-scoped credentials."""

    def __init__(
        self,
        token_provider: GitHubTokenProvider,
        *,
        base_url: str = "https://api.github.com",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._tokens = token_provider
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def _headers(self, review: ReviewRecord, *, accept: str) -> dict[str, str]:
        token = self._tokens.installation_token(review.installation_id)
        return {
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def fetch_context(self, review: ReviewRecord) -> PullRequestContext:
        headers = self._headers(
            review, accept="application/vnd.github.v3.diff"
        )
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(
                f"{self._base_url}/repos/{review.repository}/pulls/"
                f"{review.pull_request_number}",
                headers=headers,
            )
            response.raise_for_status()
            manifests = self._fetch_manifests(client, review)
            return PullRequestContext(diff_text=response.text, manifests=manifests)

    def _fetch_manifests(
        self, client: httpx.Client, review: ReviewRecord
    ) -> dict[str, str]:
        headers = self._headers(review, accept="application/vnd.github+json")
        manifests: dict[str, str] = {}
        for path in MANIFEST_PATHS:
            response = client.get(
                f"{self._base_url}/repos/{review.repository}/contents/{path}",
                headers=headers,
                params={"ref": review.head_sha},
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
            if payload.get("encoding") != "base64" or not payload.get("content"):
                continue
            manifests[path] = base64.b64decode(payload["content"]).decode(
                "utf-8", errors="replace"
            )
        return manifests

    def publish_review(
        self,
        review: ReviewRecord,
        findings: list[ReviewFinding],
        errors: list[str],
    ) -> None:
        comments = [
            {
                "path": finding.path,
                "line": finding.line,
                "side": "RIGHT",
                "body": (
                    f"### Aegis · {finding.severity.value.title()} · {finding.title}\n\n"
                    f"{finding.comment}\n\nConfidence: {finding.confidence:.0%}"
                ),
            }
            for finding in findings
        ]
        body = f"Aegis completed review with {len(findings)} verified finding(s)."
        if errors:
            body += (
                f" {len(errors)} specialist step(s) reported errors. "
                "Review is incomplete; merge must remain blocked until a clean rerun."
            )
        payload = {
            "commit_id": review.head_sha,
            "event": _review_event(errors),
            "body": body,
            "comments": comments,
        }
        headers = self._headers(review, accept="application/vnd.github+json")
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self._base_url}/repos/{review.repository}/pulls/"
                f"{review.pull_request_number}/reviews",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()


class FakeGitHubReviewClient:
    """Deterministic GitHub client for worker and end-to-end fixture tests."""

    def __init__(
        self,
        context: PullRequestContext,
        *,
        publish_error: Exception | None = None,
    ) -> None:
        self.context = context
        self.publish_error = publish_error
        self.fetched_reviews: list[str] = []
        self.published: list[tuple[ReviewRecord, list[ReviewFinding], list[str]]] = []

    def fetch_context(self, review: ReviewRecord) -> PullRequestContext:
        self.fetched_reviews.append(review.id)
        return self.context

    def publish_review(
        self,
        review: ReviewRecord,
        findings: list[ReviewFinding],
        errors: list[str],
    ) -> None:
        if self.publish_error is not None:
            raise self.publish_error
        self.published.append(
            (
                review.model_copy(deep=True),
                [item.model_copy(deep=True) for item in findings],
                list(errors),
            )
        )
