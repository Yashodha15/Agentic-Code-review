"""Pure presentation helpers shared by the Streamlit console and tests."""

from __future__ import annotations

import html
from typing import Any


LEAD_AGENTS = {"architecture", "correctness", "frontend", "security", "testing"}


def agent_lanes(traces: list[dict[str, Any]], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn the flat trace log into lead-agent lanes and spawned subagents."""

    lanes: list[dict[str, Any]] = []
    for trace in traces:
        stage = trace.get("stage", "")
        if stage not in LEAD_AGENTS:
            continue
        lanes.append(
            {
                "name": stage,
                "status": trace.get("status", "unknown"),
                "detail": trace.get("detail", ""),
                "subagents": [
                    item for item in traces if item.get("stage", "").startswith(f"{stage}.")
                ],
                "finding_count": sum(
                    item.get("source_agent") == stage for item in findings
                ),
            }
        )
    return lanes


def badge(value: str) -> str:
    """Render a small status or severity badge using a safe CSS class."""

    safe_value = html.escape(value or "unknown")
    css_value = "".join(
        character
        for character in safe_value.lower()
        if character.isalnum() or character == "-"
    )
    return f'<span class="badge {css_value}">{safe_value}</span>'
