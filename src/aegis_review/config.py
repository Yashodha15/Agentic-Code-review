"""Validated platform configuration with conservative defaults."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis_review.models import Severity


class ReviewLimits(BaseModel):
    """Hard execution ceilings enforced by the coordinator and worker."""

    maximum_specialist_agents: int = Field(default=6, ge=1, le=20)
    maximum_subagents: int = Field(default=12, ge=1, le=50)
    maximum_delegation_depth: int = Field(default=2, ge=1, le=4)
    maximum_runtime_seconds: int = Field(default=900, ge=30, le=3600)
    maximum_comments: int = Field(default=12, ge=1, le=50)
    maximum_cost_usd: float = Field(default=3.0, gt=0, le=100)


class ReviewPolicy(BaseModel):
    """Repository-level publication and verification behavior."""

    minimum_severity: Severity = Severity.MEDIUM
    require_verified_findings: bool = True
    block_on_critical_findings: bool = True
    allow_reproduction_tests: bool = True
    ignored_paths: list[str] = Field(
        default_factory=lambda: ["**/node_modules/**", "**/dist/**", "**/build/**"]
    )
    limits: ReviewLimits = Field(default_factory=ReviewLimits)

