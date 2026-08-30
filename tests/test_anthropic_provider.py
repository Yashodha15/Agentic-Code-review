"""Tests for the Anthropic-backed review provider."""

from aegis_review.providers import anthropic


class _FakeClient:
    """Capture structured-output setup without calling Anthropic."""

    def with_structured_output(self, schema):
        return (self, schema)


def test_provider_omits_deprecated_temperature(monkeypatch) -> None:
    """New Claude models reject the legacy temperature request parameter."""
    captured: dict[str, object] = {}

    def fake_chat_anthropic(**kwargs):
        captured.update(kwargs)
        return _FakeClient()

    monkeypatch.setattr(anthropic, "ChatAnthropic", fake_chat_anthropic)

    anthropic.AnthropicReviewProvider(model="claude-sonnet-5")

    assert captured["model"] == "claude-sonnet-5"
    assert "temperature" not in captured
