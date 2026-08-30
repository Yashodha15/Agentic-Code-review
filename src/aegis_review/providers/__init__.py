"""Model-provider integrations used by specialist review agents."""

from aegis_review.providers.base import AgentRequest, ReviewModelProvider
from aegis_review.providers.fake import FakeReviewProvider

__all__ = ["AgentRequest", "FakeReviewProvider", "ReviewModelProvider"]

