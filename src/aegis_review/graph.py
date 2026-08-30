"""LangGraph orchestration for one multi-agent pull-request review."""

from __future__ import annotations

import operator
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from aegis_review.agents.catalog import SPECIALIST_NAMES, get_specialist
from aegis_review.diff_parser import PullRequestDiff, parse_unified_diff
from aegis_review.models import ReviewFinding, ReviewPlan, ValidationResult
from aegis_review.providers.base import AgentRequest, ReviewModelProvider
from aegis_review.validation import deduplicate_findings, validate_finding


class ReviewGraphState(TypedDict):
    """Shared graph state with reducers for parallel specialist writes."""

    diff_text: str
    parsed_diff: PullRequestDiff
    plan: ReviewPlan
    proposed_findings: Annotated[list[ReviewFinding], operator.add]
    verified_findings: list[ReviewFinding]
    rejected_findings: list[ValidationResult]
    completed_agents: Annotated[list[str], operator.add]
    executed_subagents: Annotated[list[str], operator.add]
    skipped_agents: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]


def _assignment_for(state: ReviewGraphState, lead_agent: str):
    return next(
        (
            assignment
            for assignment in state["plan"].assignments
            if assignment.lead_agent == lead_agent
        ),
        None,
    )


def _specialist_node(
    lead_agent: str, provider: ReviewModelProvider
) -> Callable[[ReviewGraphState], dict]:
    """Create a node that skips unselected teams without invoking a model."""

    specialist = get_specialist(lead_agent)

    def run(state: ReviewGraphState) -> dict:
        assignment = _assignment_for(state, lead_agent)
        if assignment is None:
            return {"skipped_agents": [lead_agent]}

        subagent_findings: list[ReviewFinding] = []
        subagent_errors: list[str] = []
        executed_subagents: list[str] = []

        def investigate(subagent: str) -> tuple[str, list[ReviewFinding]]:
            agent_name = f"{lead_agent}.{subagent}"
            request = AgentRequest(
                lead_agent=lead_agent,
                agent_name=agent_name,
                parent_agent=lead_agent,
                subagents=(),
                system_instructions=(
                    f"You are the {subagent} investigator reporting to the "
                    f"{lead_agent} lead. Investigate only that concern, cite "
                    "concrete changed code, and omit speculative findings."
                ),
                diff_text=state["diff_text"],
                changed_files=tuple(state["plan"].changed_files),
            )
            return agent_name, provider.review(request)

        if assignment.subagents:
            with ThreadPoolExecutor(max_workers=min(4, len(assignment.subagents))) as pool:
                futures = {
                    pool.submit(investigate, subagent): subagent
                    for subagent in assignment.subagents
                }
                for future in as_completed(futures):
                    subagent = futures[future]
                    agent_name = f"{lead_agent}.{subagent}"
                    executed_subagents.append(agent_name)
                    try:
                        _, findings = future.result()
                        subagent_findings.extend(findings)
                    except Exception as error:
                        subagent_errors.append(
                            f"{agent_name}: {type(error).__name__}: {error}"
                        )

        request = AgentRequest(
            lead_agent=lead_agent,
            agent_name=lead_agent,
            parent_agent=None,
            subagents=tuple(assignment.subagents),
            system_instructions=specialist.instructions,
            diff_text=state["diff_text"],
            changed_files=tuple(state["plan"].changed_files),
            supporting_context=json.dumps(
                [finding.model_dump(mode="json") for finding in subagent_findings],
                indent=2,
            ),
        )

        try:
            findings = provider.review(request)
        except Exception as error:  # Provider errors become visible partial failures.
            return {
                "completed_agents": [lead_agent],
                "executed_subagents": executed_subagents,
                "errors": subagent_errors
                + [f"{lead_agent}: {type(error).__name__}: {error}"],
            }

        normalized = [
            finding.model_copy(update={"source_agent": lead_agent}) for finding in findings
        ]
        return {
            "proposed_findings": normalized,
            "completed_agents": [lead_agent],
            "executed_subagents": executed_subagents,
            "errors": subagent_errors,
        }

    return run


def _verify_node(state: ReviewGraphState) -> dict:
    """Deduplicate findings and enforce deterministic publication guardrails."""

    unique_findings = deduplicate_findings(state.get("proposed_findings", []))
    results = [
        validate_finding(finding, state["parsed_diff"]) for finding in unique_findings
    ]
    return {
        "verified_findings": [result.finding for result in results if result.accepted],
        "rejected_findings": [result for result in results if not result.accepted],
    }


def create_review_graph(provider: ReviewModelProvider):
    """Compile the review graph with parallel specialists and one true join."""

    builder = StateGraph(ReviewGraphState)
    for specialist_name in SPECIALIST_NAMES:
        builder.add_node(
            specialist_name,
            _specialist_node(specialist_name, provider),
        )
        builder.add_edge(START, specialist_name)

    builder.add_node("verify", _verify_node)

    # A list of start nodes creates a barrier: verification begins only after
    # every selected or skipped specialist branch has completed.
    builder.add_edge(list(SPECIALIST_NAMES), "verify")
    builder.add_edge("verify", END)
    return builder.compile()


def run_review(
    *, diff_text: str, plan: ReviewPlan, provider: ReviewModelProvider
) -> ReviewGraphState:
    """Run one review from parsed diff through deterministic verification."""

    parsed_diff = parse_unified_diff(diff_text)
    initial_state: ReviewGraphState = {
        "diff_text": diff_text,
        "parsed_diff": parsed_diff,
        "plan": plan,
        "proposed_findings": [],
        "verified_findings": [],
        "rejected_findings": [],
        "completed_agents": [],
        "executed_subagents": [],
        "skipped_agents": [],
        "errors": [],
    }
    return create_review_graph(provider).invoke(initial_state)
