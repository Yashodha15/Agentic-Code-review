"""Shared, provider-independent models used throughout the review pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class Severity(StrEnum):
    """Impact level used for findings and repository policy decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    """Verification lifecycle for a proposed agent finding."""

    PROPOSED = "proposed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ReviewFinding(BaseModel):
    """A normalized issue proposed by an agent or deterministic tool.

    Keeping this model independent of LangChain lets adapters, tests, the API,
    and the Angular UI share one stable contract.
    """

    title: Annotated[str, Field(min_length=3, max_length=120)]
    category: Annotated[str, Field(min_length=2, max_length=50)]
    severity: Severity
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    path: Annotated[str, Field(min_length=1)]
    line: Annotated[int, Field(gt=0)]
    comment: Annotated[str, Field(min_length=5, max_length=4000)]
    evidence: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None
    source_agent: str
    status: FindingStatus = FindingStatus.PROPOSED

    @field_validator("title", mode="before")
    @classmethod
    def bound_model_generated_title(cls, value: object) -> object:
        """Keep one verbose model title from invalidating its entire batch."""

        if isinstance(value, str) and len(value) > 120:
            return value[:117].rstrip() + "..."
        return value

    @field_validator("path")
    @classmethod
    def normalize_repository_path(cls, value: str) -> str:
        """Store GitHub paths in normalized repository-relative form."""

        normalized = value.strip().replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized


class AgentFindingBatch(BaseModel):
    """Structured response expected from a specialist model invocation."""

    findings: list[ReviewFinding] = Field(default_factory=list)


class AdapterMatch(BaseModel):
    """Technology detected by a language or framework adapter."""

    name: str
    kind: str
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasons: list[str] = Field(default_factory=list)


class AgentAssignment(BaseModel):
    """One specialist team selected by the deterministic planner."""

    lead_agent: str
    subagents: list[str]
    reason: str


class ReviewPlan(BaseModel):
    """Auditable plan created before model-backed review begins."""

    adapters: list[AdapterMatch]
    assignments: list[AgentAssignment]
    risk_level: Severity
    changed_files: list[str]


class ValidationResult(BaseModel):
    """Outcome of deterministic validation performed before publication."""

    finding: ReviewFinding
    accepted: bool
    reasons: list[str] = Field(default_factory=list)
