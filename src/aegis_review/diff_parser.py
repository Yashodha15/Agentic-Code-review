"""Small, dependency-free parser for GitHub-style unified diffs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


HUNK_HEADER = re.compile(
    r"^@@ -(?:\d+)(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@"
)


class DiffParseError(ValueError):
    """Raised when a diff contains malformed structural data."""


@dataclass(frozen=True)
class DiffHunk:
    """A single hunk and the publishable lines on its new-file side."""

    new_start: int
    new_count: int
    added_lines: frozenset[int]


@dataclass
class DiffFile:
    """Changes for one file in a pull request."""

    old_path: str | None
    new_path: str | None
    hunks: list[DiffHunk] = field(default_factory=list)

    @property
    def publishable_lines(self) -> frozenset[int]:
        """Return new-side lines GitHub can receive as inline comments."""

        return frozenset(line for hunk in self.hunks for line in hunk.added_lines)


@dataclass
class PullRequestDiff:
    """Parsed pull-request diff indexed by destination path."""

    files: list[DiffFile]

    def by_path(self) -> dict[str, DiffFile]:
        return {item.new_path: item for item in self.files if item.new_path is not None}

    @property
    def changed_files(self) -> list[str]:
        return [item.new_path for item in self.files if item.new_path is not None]


def _strip_git_prefix(path: str) -> str | None:
    """Convert Git headers such as ``b/src/app.py`` to repository paths."""

    path = path.strip()
    if path == "/dev/null":
        return None
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def parse_unified_diff(content: str) -> PullRequestDiff:
    """Parse enough unified-diff structure to validate GitHub comment lines.

    The parser deliberately ignores file contents beyond their prefix. Its job
    is structural validation, not language parsing; language adapters handle
    source semantics later in the pipeline.
    """

    files: list[DiffFile] = []
    current_file: DiffFile | None = None
    lines = content.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.startswith("diff --git "):
            parts = line.split(" ", 3)
            if len(parts) != 4:
                raise DiffParseError(f"Malformed file header: {line}")
            current_file = DiffFile(
                old_path=_strip_git_prefix(parts[2]),
                new_path=_strip_git_prefix(parts[3]),
            )
            files.append(current_file)
            index += 1
            continue

        if current_file is not None and line.startswith("--- "):
            current_file.old_path = _strip_git_prefix(line[4:].split("\t", 1)[0])
            index += 1
            continue

        if current_file is not None and line.startswith("+++ "):
            current_file.new_path = _strip_git_prefix(line[4:].split("\t", 1)[0])
            index += 1
            continue

        match = HUNK_HEADER.match(line)
        if current_file is not None and match:
            new_line = int(match.group("start"))
            new_count = int(match.group("count") or "1")
            added_lines: set[int] = set()
            index += 1

            while index < len(lines) and not lines[index].startswith(("@@ ", "diff --git ")):
                body_line = lines[index]
                if body_line.startswith("+") and not body_line.startswith("+++"):
                    added_lines.add(new_line)
                    new_line += 1
                elif body_line.startswith("-") and not body_line.startswith("---"):
                    # A deleted line does not advance the new-file cursor.
                    pass
                elif not body_line.startswith("\\"):
                    new_line += 1
                index += 1

            current_file.hunks.append(
                DiffHunk(
                    new_start=int(match.group("start")),
                    new_count=new_count,
                    added_lines=frozenset(added_lines),
                )
            )
            continue

        index += 1

    return PullRequestDiff(files=files)

