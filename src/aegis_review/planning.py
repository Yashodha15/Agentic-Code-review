"""Deterministic first-pass planning for specialist agent teams."""

from __future__ import annotations

from aegis_review.models import AdapterMatch, AgentAssignment, ReviewPlan, Severity


SECURITY_PATH_TERMS = (
    "access",
    "auth",
    "permission",
    "policy",
    "secret",
    "token",
    "session",
)
DATA_PATH_TERMS = ("migration", "database", "repository", "model", "schema")
TEST_PATH_TERMS = ("test", "spec")


def _contains_term(paths: list[str], terms: tuple[str, ...]) -> bool:
    return any(term in path.lower() for path in paths for term in terms)


def build_review_plan(
    changed_files: list[str], adapter_matches: list[AdapterMatch]
) -> ReviewPlan:
    """Select specialist teams before the LLM coordinator refines the plan.

    This deterministic baseline guarantees that critical reviewers cannot be
    skipped solely because of a model decision. A later coordinator node may
    add specialists, but repository policy controls whether it may remove them.
    """

    assignments: list[AgentAssignment] = [
        AgentAssignment(
            lead_agent="correctness",
            subagents=["control-flow", "boundary-cases", "error-handling"],
            reason="Every behavioral change receives a correctness review.",
        )
    ]
    adapter_names = {match.name for match in adapter_matches}

    if _contains_term(changed_files, SECURITY_PATH_TERMS):
        assignments.append(
            AgentAssignment(
                lead_agent="security",
                subagents=["authentication", "authorization", "input-validation"],
                reason="Security-sensitive file names or paths changed.",
            )
        )

    if adapter_names & {"angular", "react"}:
        framework = "angular" if "angular" in adapter_names else "react"
        subagents = (
            ["rxjs-lifecycle", "template-safety", "change-detection", "accessibility"]
            if framework == "angular"
            else ["hooks-lifecycle", "rendering", "browser-security", "accessibility"]
        )
        assignments.append(
            AgentAssignment(
                lead_agent="frontend",
                subagents=subagents,
                reason=f"The {framework} framework adapter matched the changed repository.",
            )
        )

    if _contains_term(changed_files, DATA_PATH_TERMS):
        assignments.append(
            AgentAssignment(
                lead_agent="architecture",
                subagents=["api-contract", "data-migration", "dependency-boundaries"],
                reason="Data models, persistence, or public contracts may be affected.",
            )
        )

    if not changed_files or not all(
        _contains_term([path], TEST_PATH_TERMS) for path in changed_files
    ):
        assignments.append(
            AgentAssignment(
                lead_agent="testing",
                subagents=["coverage-gaps", "edge-case-design", "regression-tests"],
                reason="Production code changes require targeted test analysis.",
            )
        )

    high_risk = any(item.lead_agent == "security" for item in assignments)
    medium_risk = len(changed_files) >= 10 or any(
        item.lead_agent == "architecture" for item in assignments
    )
    risk = Severity.HIGH if high_risk else Severity.MEDIUM if medium_risk else Severity.LOW

    return ReviewPlan(
        adapters=adapter_matches,
        assignments=assignments,
        risk_level=risk,
        changed_files=changed_files,
    )
