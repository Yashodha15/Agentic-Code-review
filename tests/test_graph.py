from pathlib import Path

from aegis_review.adapters.base import RepositorySnapshot
from aegis_review.adapters.registry import default_registry
from aegis_review.graph import run_review
from aegis_review.models import ReviewFinding, Severity
from aegis_review.planning import build_review_plan
from aegis_review.providers.fake import FakeReviewProvider


FIXTURE = Path(__file__).parent / "fixtures" / "sample_pr.diff"


def make_finding(
    *,
    title: str = "Cached result bypasses access policy",
    line: int = 10,
    confidence: float = 0.92,
) -> ReviewFinding:
    return ReviewFinding(
        title=title,
        category="security",
        severity=Severity.HIGH,
        confidence=confidence,
        path="src/access.py",
        line=line,
        comment="Run the access policy before returning a cached resource.",
        evidence=["The new branch returns before require_access is called."],
        source_agent="fixture",
    )


def build_sensitive_plan():
    changed_files = ["src/access.py", "src/new_name.py"]
    snapshot = RepositorySnapshot(
        changed_files=tuple(changed_files),
        manifests={"requirements.txt": "fastapi"},
    )
    return build_review_plan(changed_files, default_registry().detect(snapshot))


def test_graph_runs_only_selected_specialists_and_verifies_findings() -> None:
    provider = FakeReviewProvider(
        {
            "security": [make_finding()],
            "correctness": [],
            "testing": [],
        }
    )

    result = run_review(
        diff_text=FIXTURE.read_text(encoding="utf-8"),
        plan=build_sensitive_plan(),
        provider=provider,
    )

    assert {
        request.lead_agent
        for request in provider.requests
        if request.parent_agent is None
    } == {
        "security",
        "correctness",
        "testing",
    }
    assert set(result["skipped_agents"]) == {"frontend", "architecture"}
    assert len(result["verified_findings"]) == 1
    assert result["verified_findings"][0].source_agent == "security"
    assert result["errors"] == []


def test_graph_rejects_a_model_finding_on_an_unchanged_line() -> None:
    provider = FakeReviewProvider({"security": [make_finding(line=8)]})

    result = run_review(
        diff_text=FIXTURE.read_text(encoding="utf-8"),
        plan=build_sensitive_plan(),
        provider=provider,
    )

    assert result["verified_findings"] == []
    assert len(result["rejected_findings"]) == 1
    assert "not an added or modified line" in result["rejected_findings"][0].reasons[0]


def test_graph_preserves_partial_results_when_one_provider_call_fails() -> None:
    provider = FakeReviewProvider(
        {
            "security": RuntimeError("temporary model failure"),
            "correctness": [make_finding(title="Incorrect cached branch")],
            "testing": [],
        }
    )

    result = run_review(
        diff_text=FIXTURE.read_text(encoding="utf-8"),
        plan=build_sensitive_plan(),
        provider=provider,
    )

    assert len(result["verified_findings"]) == 1
    assert result["verified_findings"][0].source_agent == "correctness"
    assert result["errors"] == [
        "security: RuntimeError: temporary model failure"
    ]


def test_graph_deduplicates_equivalent_cross_agent_findings() -> None:
    lower_confidence = make_finding(confidence=0.70)
    higher_confidence = make_finding(confidence=0.97)
    provider = FakeReviewProvider(
        {
            "security": [lower_confidence],
            "correctness": [higher_confidence],
        }
    )

    result = run_review(
        diff_text=FIXTURE.read_text(encoding="utf-8"),
        plan=build_sensitive_plan(),
        provider=provider,
    )

    assert len(result["verified_findings"]) == 1
    assert result["verified_findings"][0].confidence == 0.97
    assert result["verified_findings"][0].source_agent == "correctness"


def test_selected_leads_execute_real_subagents_before_consolidation() -> None:
    provider = FakeReviewProvider(
        {
            "security.authorization": [make_finding()],
            "security": [make_finding()],
        }
    )

    result = run_review(
        diff_text=FIXTURE.read_text(encoding="utf-8"),
        plan=build_sensitive_plan(),
        provider=provider,
    )

    request_names = {request.agent_name for request in provider.requests}
    assert "security.authorization" in request_names
    assert "security" in request_names
    lead_request = next(request for request in provider.requests if request.agent_name == "security")
    assert "Cached result bypasses access policy" in lead_request.supporting_context
    assert "security.authorization" in result["executed_subagents"]
