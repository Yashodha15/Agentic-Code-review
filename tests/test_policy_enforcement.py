"""Tests for deterministic policy enforcement helpers."""

from time import monotonic

import pytest

from aegis_review.policy_enforcement import (
    BudgetedReviewProvider,
    PolicyLimitExceeded,
    blocking_reasons,
    filter_ignored_diff,
)
from aegis_review.models import FindingStatus, ReviewFinding, Severity
from aegis_review.providers.base import AgentRequest
from aegis_review.providers.fake import FakeReviewProvider


def finding(severity: Severity = Severity.HIGH) -> ReviewFinding:
    return ReviewFinding(
        title="Unsafe behavior changed",
        category="correctness",
        severity=severity,
        confidence=0.9,
        path="src/app.py",
        line=1,
        comment="The changed behavior can return an invalid result.",
        source_agent="correctness",
        status=FindingStatus.VERIFIED,
    )


def request() -> AgentRequest:
    return AgentRequest(
        lead_agent="correctness",
        agent_name="correctness",
        parent_agent=None,
        subagents=(),
        system_instructions="Review correctness.",
        diff_text="",
        changed_files=(),
    )


def test_ignored_diff_removes_complete_matching_file_section() -> None:
    diff = (
        "diff --git a/dist/app.js b/dist/app.js\n--- a/dist/app.js\n+++ b/dist/app.js\n@@ -0,0 +1 @@\n+ignored\n"
        "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -0,0 +1 @@\n+kept\n"
    )
    filtered = filter_ignored_diff(diff, ["**/dist/**", "dist/**"])
    assert "dist/app.js" not in filtered
    assert "src/app.py" in filtered


def test_budgeted_provider_stops_calls_beyond_cost_ceiling() -> None:
    guarded = BudgetedReviewProvider(
        FakeReviewProvider(),
        maximum_cost_usd=0.25,
        deadline=monotonic() + 60,
        estimated_call_cost_usd=0.25,
    )
    guarded.review(request())
    with pytest.raises(PolicyLimitExceeded, match="cost limit"):
        guarded.review(request())


def test_critical_finding_blocks_only_when_enabled() -> None:
    from aegis_review.config import ReviewPolicy

    critical = finding(Severity.CRITICAL)
    assert blocking_reasons(ReviewPolicy(), [critical], [])
    policy = ReviewPolicy(block_on_critical_findings=False)
    assert blocking_reasons(policy, [critical], []) == []
