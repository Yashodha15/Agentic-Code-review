"""Deterministic guardrails applied to model-generated findings."""

from __future__ import annotations

from pathlib import PurePosixPath

from aegis_review.diff_parser import PullRequestDiff
from aegis_review.models import FindingStatus, ReviewFinding, ValidationResult


def validate_finding(finding: ReviewFinding, diff: PullRequestDiff) -> ValidationResult:
    """Check that a finding can safely become a GitHub inline comment."""

    reasons: list[str] = []
    path = PurePosixPath(finding.path)

    if path.is_absolute() or ".." in path.parts:
        reasons.append("Finding path must be repository-relative and cannot traverse directories.")

    changed_file = diff.by_path().get(finding.path)
    if changed_file is None:
        reasons.append("Finding path is not a changed destination file in this pull request.")
    elif finding.line not in changed_file.publishable_lines:
        reasons.append("Finding line is not an added or modified line in the pull request.")

    accepted = not reasons
    validated = finding.model_copy(
        update={"status": FindingStatus.VERIFIED if accepted else FindingStatus.REJECTED}
    )
    return ValidationResult(finding=validated, accepted=accepted, reasons=reasons)


def finding_fingerprint(finding: ReviewFinding) -> str:
    """Return a stable key used to suppress repeated findings across commits."""

    normalized_title = " ".join(finding.title.lower().split())
    return f"{finding.path}:{finding.line}:{finding.category.lower()}:{normalized_title}"


def deduplicate_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """Keep the highest-confidence instance of each stable finding."""

    selected: dict[str, ReviewFinding] = {}
    for finding in findings:
        key = finding_fingerprint(finding)
        existing = selected.get(key)
        if existing is None or finding.confidence > existing.confidence:
            selected[key] = finding
    return list(selected.values())

