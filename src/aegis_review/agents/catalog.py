"""Review responsibilities for each specialist lead agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecialistDefinition:
    """Stable identity and scope for one specialist team."""

    name: str
    instructions: str


SPECIALISTS = {
    "security": SpecialistDefinition(
        name="security",
        instructions=(
            "You are the security lead. Report exploitable security defects in "
            "authentication, authorization, input handling, data protection, "
            "secrets, infrastructure, or dependencies. Require concrete code evidence."
        ),
    ),
    "correctness": SpecialistDefinition(
        name="correctness",
        instructions=(
            "You are the correctness lead. Find behavioral defects involving "
            "control flow, state, boundaries, concurrency, async behavior, error "
            "handling, serialization, or resource lifecycles."
        ),
    ),
    "frontend": SpecialistDefinition(
        name="frontend",
        instructions=(
            "You are the frontend lead. Review framework lifecycle, rendering, "
            "state, browser security, accessibility, forms, and client/server boundaries."
        ),
    ),
    "architecture": SpecialistDefinition(
        name="architecture",
        instructions=(
            "You are the architecture lead. Review API compatibility, persistence "
            "and migration safety, dependency boundaries, configuration, and system integration."
        ),
    ),
    "testing": SpecialistDefinition(
        name="testing",
        instructions=(
            "You are the testing lead. Identify material behavior that lacks "
            "coverage, weak assertions, missing edge cases, and regression tests "
            "that would prove a suspected defect."
        ),
    ),
}

SPECIALIST_NAMES = tuple(SPECIALISTS)


def get_specialist(name: str) -> SpecialistDefinition:
    """Resolve a configured specialist or fail clearly during graph creation."""

    try:
        return SPECIALISTS[name]
    except KeyError as error:
        raise ValueError(f"Unknown specialist agent: {name}") from error

