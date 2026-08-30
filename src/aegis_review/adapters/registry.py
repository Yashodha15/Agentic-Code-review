"""Adapter registry and built-in technology definitions."""

from __future__ import annotations

from aegis_review.adapters.base import RepositorySnapshot, ReviewAdapter, SignalAdapter
from aegis_review.models import AdapterMatch


class AdapterRegistry:
    """Runs all registered detectors and returns matches by confidence."""

    def __init__(self, adapters: list[ReviewAdapter] | None = None) -> None:
        self._adapters = list(adapters or [])

    def register(self, adapter: ReviewAdapter) -> None:
        if any(existing.name == adapter.name for existing in self._adapters):
            raise ValueError(f"Adapter already registered: {adapter.name}")
        self._adapters.append(adapter)

    def detect(self, snapshot: RepositorySnapshot) -> list[AdapterMatch]:
        matches = [match for adapter in self._adapters if (match := adapter.detect(snapshot))]
        return sorted(matches, key=lambda match: (-match.confidence, match.kind, match.name))


def default_registry() -> AdapterRegistry:
    """Create the initial language and framework adapter catalog."""

    return AdapterRegistry(
        [
            SignalAdapter(
                name="python",
                kind="language",
                extensions=(".py", ".pyi"),
                marker_files=("pyproject.toml", "requirements.txt", "Pipfile"),
            ),
            SignalAdapter(
                name="javascript",
                kind="language",
                extensions=(".js", ".jsx", ".mjs", ".cjs"),
                marker_files=("package.json",),
            ),
            SignalAdapter(
                name="typescript",
                kind="language",
                extensions=(".ts", ".tsx"),
                marker_files=("tsconfig.json",),
                manifest_terms=("typescript",),
            ),
            SignalAdapter(
                name="react",
                kind="framework",
                extensions=(".jsx", ".tsx"),
                manifest_terms=('"react"', "next", "remix"),
            ),
            SignalAdapter(
                name="angular",
                kind="framework",
                marker_files=("angular.json",),
                manifest_terms=("@angular/core", "@angular/cli"),
            ),
            SignalAdapter(
                name="fastapi",
                kind="framework",
                manifest_terms=("fastapi",),
            ),
            SignalAdapter(
                name="django",
                kind="framework",
                marker_files=("manage.py",),
                manifest_terms=("django",),
            ),
        ]
    )

