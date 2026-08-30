"""Background worker that executes one queued review from start to publish."""

from __future__ import annotations

from aegis_review.adapters.base import RepositorySnapshot
from aegis_review.adapters.registry import AdapterRegistry, default_registry
from aegis_review.api.schemas import ReviewStatus, TraceStatus
from aegis_review.diff_parser import parse_unified_diff
from aegis_review.github.client import GitHubReviewClient
from aegis_review.graph import run_review
from aegis_review.planning import build_review_plan
from aegis_review.providers.base import ReviewModelProvider
from aegis_review.storage.base import ReviewRepository
from aegis_review.storage.policy import InMemoryPolicyStore, PolicyStore


SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class ReviewWorker:
    """Coordinates GitHub context, planning, LangGraph, storage, and publishing."""

    def __init__(
        self,
        *,
        repository: ReviewRepository,
        github: GitHubReviewClient,
        provider: ReviewModelProvider,
        adapters: AdapterRegistry | None = None,
        policy_store: PolicyStore | None = None,
    ) -> None:
        self.repository = repository
        self.github = github
        self.provider = provider
        self.adapters = adapters or default_registry()
        self.policies = policy_store or InMemoryPolicyStore()

    def process(self, review_id: str) -> None:
        review = self.repository.get(review_id)
        if review is None:
            raise KeyError(review_id)
        if review.status not in {ReviewStatus.QUEUED, ReviewStatus.FAILED}:
            raise ValueError(
                f"Review {review_id} cannot run from status {review.status.value}."
            )

        self.repository.update_status(review_id, ReviewStatus.RUNNING)
        self.repository.append_trace(
            review_id, "worker", TraceStatus.RUNNING, "Review worker started."
        )

        try:
            context = self.github.fetch_context(review)
            parsed_diff = parse_unified_diff(context.diff_text)
            snapshot = RepositorySnapshot(
                changed_files=tuple(parsed_diff.changed_files),
                manifests=context.manifests,
            )
            adapter_matches = self.adapters.detect(snapshot)
            plan = build_review_plan(parsed_diff.changed_files, adapter_matches)
            policy = self.policies.get()
            assignments = []
            remaining_subagents = policy.limits.maximum_subagents
            for assignment in plan.assignments[: policy.limits.maximum_specialist_agents]:
                selected_subagents = assignment.subagents[:remaining_subagents]
                remaining_subagents -= len(selected_subagents)
                assignments.append(
                    assignment.model_copy(update={"subagents": selected_subagents})
                )
            plan = plan.model_copy(update={"assignments": assignments})
            self.repository.append_trace(
                review_id,
                "planning",
                TraceStatus.COMPLETED,
                f"Selected {len(plan.assignments)} specialist team(s) and "
                f"{len(plan.adapters)} adapter(s); risk={plan.risk_level.value}.",
            )

            result = run_review(
                diff_text=context.diff_text,
                plan=plan,
                provider=self.provider,
            )
            self._record_agent_traces(review_id, result)
            minimum = SEVERITY_ORDER[policy.minimum_severity.value]
            publication_findings = [
                finding
                for finding in result["verified_findings"]
                if SEVERITY_ORDER[finding.severity.value] >= minimum
            ][: policy.limits.maximum_comments]
            completed = self.repository.save_result(
                review_id,
                findings=publication_findings,
                completed_agents=result["completed_agents"],
                errors=result["errors"],
            )
            self.github.publish_review(
                completed, publication_findings, result["errors"]
            )
            self.repository.append_trace(
                review_id,
                "publish",
                TraceStatus.COMPLETED,
                f"Published {len(publication_findings)} verified finding(s).",
            )
        except Exception as error:
            message = f"Worker failed: {type(error).__name__}: {error}"
            self.repository.update_status(
                review_id, ReviewStatus.FAILED, errors=[message]
            )
            self.repository.append_trace(
                review_id, "worker", TraceStatus.FAILED, message
            )
            raise

    def _record_agent_traces(self, review_id: str, result: dict) -> None:
        failed_agents = {
            error.split(":", 1)[0] for error in result.get("errors", [])
        }
        for agent in result.get("completed_agents", []):
            status = TraceStatus.FAILED if agent in failed_agents else TraceStatus.COMPLETED
            detail = (
                next(error for error in result["errors"] if error.startswith(f"{agent}:"))
                if agent in failed_agents
                else "Specialist analysis completed."
            )
            self.repository.append_trace(review_id, agent, status, detail)
        for agent in result.get("skipped_agents", []):
            self.repository.append_trace(
                review_id,
                agent,
                TraceStatus.SKIPPED,
                "The review plan did not select this specialist.",
            )
        for subagent in result.get("executed_subagents", []):
            failed = next(
                (
                    error
                    for error in result.get("errors", [])
                    if error.startswith(f"{subagent}:")
                ),
                None,
            )
            self.repository.append_trace(
                review_id,
                subagent,
                TraceStatus.FAILED if failed else TraceStatus.COMPLETED,
                failed or "Delegated investigation completed.",
            )
