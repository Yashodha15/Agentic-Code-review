"""Provider-neutral contract for invoking a code-review model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aegis_review.models import ReviewFinding


@dataclass(frozen=True)
class AgentRequest:
    """Complete, auditable input passed to one specialist lead agent."""

    lead_agent: str
    agent_name: str
    parent_agent: str | None
    subagents: tuple[str, ...]
    system_instructions: str
    diff_text: str
    changed_files: tuple[str, ...]
    supporting_context: str = ""


class ReviewModelProvider(Protocol):
    """Interface implemented by real and deterministic test providers."""

    def review(self, request: AgentRequest) -> list[ReviewFinding]:
        """Analyze one specialist request and return structured findings."""
