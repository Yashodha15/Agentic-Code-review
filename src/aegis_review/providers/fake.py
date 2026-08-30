"""Deterministic provider used by graph tests and local demonstrations."""

from __future__ import annotations

from collections.abc import Callable

from aegis_review.models import ReviewFinding
from aegis_review.providers.base import AgentRequest


FakeResponse = list[ReviewFinding] | Exception | Callable[[AgentRequest], list[ReviewFinding]]


class FakeReviewProvider:
    """Return predefined responses without making network or model calls."""

    def __init__(self, responses: dict[str, FakeResponse] | None = None) -> None:
        self.responses = responses or {}
        self.requests: list[AgentRequest] = []

    def review(self, request: AgentRequest) -> list[ReviewFinding]:
        self.requests.append(request)
        # Explicit sub-agent keys make hierarchical tests precise. Missing
        # sub-agent fixtures return no findings instead of accidentally replaying
        # their parent's response.
        response = self.responses.get(request.agent_name, [])

        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response(request)
        return [finding.model_copy(deep=True) for finding in response]
