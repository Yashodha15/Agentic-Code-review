from pathlib import Path

from aegis_review.diff_parser import parse_unified_diff
from aegis_review.models import ReviewFinding, Severity
from aegis_review.validation import deduplicate_findings, validate_finding


def make_finding(**updates: object) -> ReviewFinding:
    values = {
        "title": "Authorization check bypassed",
        "category": "security",
        "severity": Severity.HIGH,
        "confidence": 0.91,
        "path": "src/access.py",
        "line": 10,
        "comment": "Run the access policy before returning the cached resource.",
        "evidence": ["The new cached branch returns before require_access."],
        "source_agent": "authorization-investigator",
    }
    values.update(updates)
    return ReviewFinding.model_validate(values)


def load_diff():
    fixture = Path(__file__).parent / "fixtures" / "sample_pr.diff"
    return parse_unified_diff(fixture.read_text(encoding="utf-8"))


def test_finding_on_changed_line_is_accepted() -> None:
    result = validate_finding(make_finding(), load_diff())

    assert result.accepted is True
    assert result.finding.status == "verified"


def test_finding_on_context_line_is_rejected() -> None:
    result = validate_finding(make_finding(line=8), load_diff())

    assert result.accepted is False
    assert "not an added or modified line" in result.reasons[0]


def test_path_traversal_and_unknown_file_are_rejected() -> None:
    result = validate_finding(make_finding(path="../secrets.txt"), load_diff())

    assert result.accepted is False
    assert len(result.reasons) == 2


def test_deduplication_keeps_the_highest_confidence_finding() -> None:
    result = deduplicate_findings(
        [make_finding(confidence=0.72), make_finding(confidence=0.96)]
    )

    assert len(result) == 1
    assert result[0].confidence == 0.96


def test_normalizes_overlong_model_generated_title() -> None:
    """A verbose title must not discard an otherwise valid model response."""
    finding = make_finding(title="A" * 140)

    assert len(finding.title) == 120
    assert finding.title.endswith("...")
