"""Focused tests for Streamlit console data shaping."""

from aegis_review.console.presentation import agent_lanes, badge


def test_agent_lanes_groups_subagents_and_findings() -> None:
    traces = [
        {"stage": "security", "status": "completed", "detail": "done"},
        {"stage": "security.authentication", "status": "completed", "detail": "done"},
        {"stage": "queue", "status": "completed", "detail": "queued"},
    ]
    findings = [{"source_agent": "security"}, {"source_agent": "correctness"}]

    assert agent_lanes(traces, findings) == [
        {
            "name": "security",
            "status": "completed",
            "detail": "done",
            "subagents": [traces[1]],
            "finding_count": 1,
        }
    ]


def test_badge_escapes_untrusted_values() -> None:
    assert "<script>" not in badge("<script>")
    assert "&lt;script&gt;" in badge("<script>")
