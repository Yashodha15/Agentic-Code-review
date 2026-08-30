"""Tests for the Anthropic-backed review provider."""

from langchain_anthropic import ChatAnthropic

from aegis_review.providers import anthropic
from aegis_review.providers.base import AgentRequest


class _StructuredClient:
    def __init__(self, result) -> None:
        self.result = result

    def invoke(self, _messages):
        return self.result


class _FakeClient:
    def __init__(self, result) -> None:
        self.result = result

    def with_structured_output(self, _schema):
        return _StructuredClient(self.result)


def _request() -> AgentRequest:
    return AgentRequest(
        lead_agent="security",
        agent_name="security.input-validation",
        parent_agent="security",
        subagents=(),
        system_instructions="Review input validation.",
        diff_text="+ return eval(value)",
        changed_files=("src/example.py",),
    )


def test_provider_omits_deprecated_temperature(monkeypatch) -> None:
    """Construct the real client so the test exercises accepted inputs."""
    captured: dict[str, object] = {}

    def recording_client(**kwargs):
        captured.update(kwargs)
        return ChatAnthropic(api_key="test-key", **kwargs)

    monkeypatch.setattr(anthropic, "ChatAnthropic", recording_client)

    anthropic.AnthropicReviewProvider(model="claude-sonnet-5")

    assert captured["model"] == "claude-sonnet-5"
    assert "temperature" not in captured


def test_provider_defaults_source_and_isolates_invalid_finding(monkeypatch) -> None:
    """One malformed candidate must not discard valid sibling findings."""
    result = anthropic._ProviderFindingBatch(
        findings=[
            anthropic._ProviderFinding(
                title="Unsafe dynamic evaluation",
                category="security",
                severity="high",
                confidence=0.95,
                path="src/example.py",
                line=1,
                comment="External input reaches eval and can execute arbitrary code.",
            ),
            anthropic._ProviderFinding(
                title="X" * 121,
                category="security",
                severity="high",
                confidence=0.9,
                path="src/example.py",
                line=1,
                comment="This candidate is invalid because its title is too long.",
            ),
        ]
    )
    monkeypatch.setattr(anthropic, "ChatAnthropic", lambda **_kwargs: _FakeClient(result))

    findings = anthropic.AnthropicReviewProvider(model="claude-sonnet-5").review(_request())

    assert len(findings) == 1
    assert findings[0].source_agent == "security.input-validation"
