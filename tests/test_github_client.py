"""Tests for GitHub review publication decisions."""

from aegis_review.github.client import _review_event


def test_clean_review_publishes_comment() -> None:
    assert _review_event([]) == "COMMENT"


def test_specialist_error_requests_changes() -> None:
    assert _review_event(["security: provider unavailable"]) == "REQUEST_CHANGES"
