"""Contracts and reusable detection logic for review adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from aegis_review.models import AdapterMatch


@dataclass(frozen=True)
class RepositorySnapshot:
    """Minimal repository information adapters may inspect safely.

    Manifest content is supplied by the repository context builder. Adapters do
    not read arbitrary files themselves, which makes detection easy to test and
    keeps filesystem policy in one place.
    """

    changed_files: tuple[str, ...]
    manifests: dict[str, str] = field(default_factory=dict)


class ReviewAdapter(ABC):
    """Provider-independent contract implemented by every technology adapter."""

    name: str
    kind: str

    @abstractmethod
    def detect(self, snapshot: RepositorySnapshot) -> AdapterMatch | None:
        """Return a match when the repository contains this technology."""


class SignalAdapter(ReviewAdapter):
    """Adapter driven by extensions, marker files, and manifest dependencies."""

    def __init__(
        self,
        *,
        name: str,
        kind: str,
        extensions: tuple[str, ...] = (),
        marker_files: tuple[str, ...] = (),
        manifest_terms: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.kind = kind
        self.extensions = extensions
        self.marker_files = marker_files
        self.manifest_terms = manifest_terms

    def detect(self, snapshot: RepositorySnapshot) -> AdapterMatch | None:
        reasons: list[str] = []
        file_names = {PurePosixPath(path).name for path in snapshot.changed_files}
        all_known_paths = set(snapshot.changed_files) | set(snapshot.manifests)

        matching_extensions = sorted(
            {
                PurePosixPath(path).suffix.lower()
                for path in snapshot.changed_files
                if PurePosixPath(path).suffix.lower() in self.extensions
            }
        )
        if matching_extensions:
            reasons.append(f"Changed extensions: {', '.join(matching_extensions)}")

        marker_hits = sorted(
            marker
            for marker in self.marker_files
            if marker in file_names
            or marker in all_known_paths
            or any(path.endswith(f"/{marker}") for path in all_known_paths)
        )
        if marker_hits:
            reasons.append(f"Repository markers: {', '.join(marker_hits)}")

        combined_manifests = "\n".join(snapshot.manifests.values()).lower()
        term_hits = sorted(term for term in self.manifest_terms if term.lower() in combined_manifests)
        if term_hits:
            reasons.append(f"Manifest signals: {', '.join(term_hits)}")

        if not reasons:
            return None

        # Multiple independent signals are more reliable than an extension alone.
        confidence = min(1.0, 0.55 + (0.2 * (len(reasons) - 1)))
        return AdapterMatch(
            name=self.name,
            kind=self.kind,
            confidence=confidence,
            reasons=reasons,
        )
