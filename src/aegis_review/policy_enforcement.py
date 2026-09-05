"""Deterministic enforcement helpers for repository review policy."""

from __future__ import annotations

import fnmatch
import math
import os
import signal
from contextlib import contextmanager
from dataclasses import dataclass
from time import monotonic
from typing import Iterator

from aegis_review.config import ReviewPolicy
from aegis_review.models import ReviewFinding
from aegis_review.providers.base import AgentRequest, ReviewModelProvider


def path_is_ignored(path: str, patterns: list[str]) -> bool:
    """Return whether a repository-relative path matches an ignored glob."""

    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def filter_ignored_diff(diff_text: str, patterns: list[str]) -> str:
    """Remove complete unified-diff file sections matching ignored patterns."""

    sections: list[list[str]] = []
    current: list[str] = []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith("diff --git ") and current:
            sections.append(current)
            current = []
        current.append(line)
    if current:
        sections.append(current)

    kept: list[str] = []
    for section in sections:
        header = section[0].strip().split(" ", 3)
        path = header[3][2:] if len(header) == 4 and header[3].startswith("b/") else ""
        if not path or not path_is_ignored(path, patterns):
            kept.extend(section)
    return "".join(kept)


class PolicyLimitExceeded(RuntimeError):
    """Raised when a configured execution ceiling stops model work."""


@dataclass
class BudgetedReviewProvider:
    """Guard provider calls with runtime and conservative cost ceilings.

    Providers do not currently expose billing data through the shared contract,
    so cost is enforced as a conservative per-invocation allowance. Deployments
    can tune the estimate using ``AEGIS_ESTIMATED_CALL_COST_USD``.
    """

    provider: ReviewModelProvider
    maximum_cost_usd: float
    deadline: float
    estimated_call_cost_usd: float = 0.25
    calls: int = 0

    @classmethod
    def from_policy(cls, provider: ReviewModelProvider, policy: ReviewPolicy) -> "BudgetedReviewProvider":
        estimate = float(os.getenv("AEGIS_ESTIMATED_CALL_COST_USD", "0.25"))
        if estimate <= 0:
            raise ValueError("AEGIS_ESTIMATED_CALL_COST_USD must be positive.")
        return cls(
            provider=provider,
            maximum_cost_usd=policy.limits.maximum_cost_usd,
            deadline=monotonic() + policy.limits.maximum_runtime_seconds,
            estimated_call_cost_usd=estimate,
        )

    def review(self, request: AgentRequest) -> list[ReviewFinding]:
        if monotonic() >= self.deadline:
            raise PolicyLimitExceeded("maximum review runtime exceeded")
        maximum_calls = max(1, math.floor(self.maximum_cost_usd / self.estimated_call_cost_usd))
        if self.calls >= maximum_calls:
            raise PolicyLimitExceeded(
                f"estimated model cost limit reached after {self.calls} invocation(s)"
            )
        self.calls += 1
        return self.provider.review(request)


@contextmanager
def runtime_limit(seconds: int) -> Iterator[None]:
    """Interrupt the synchronous worker when its total runtime limit expires."""

    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def timeout_handler(signum, frame):  # noqa: ARG001
        raise PolicyLimitExceeded(f"maximum review runtime of {seconds}s exceeded")

    previous = signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def blocking_reasons(
    policy: ReviewPolicy,
    findings: list[ReviewFinding],
    errors: list[str],
) -> list[str]:
    """Return policy reasons that must produce a failed GitHub check."""

    reasons = list(errors)
    if policy.block_on_critical_findings and any(
        finding.severity.value == "critical" for finding in findings
    ):
        reasons.append("A verified critical finding blocks merge by policy.")
    if policy.require_verified_findings and any(
        finding.status.value != "verified" for finding in findings
    ):
        reasons.append("An unverified finding was selected for publication.")
    return reasons
