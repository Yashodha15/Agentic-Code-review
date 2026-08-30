import hashlib
import hmac

import pytest

from aegis_review.github.webhooks import InvalidWebhookSignature, verify_webhook_signature


SECRET = "local-test-secret"
BODY = b'{"action":"opened"}'


def signature(body: bytes = BODY) -> str:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_valid_webhook_signature_is_accepted() -> None:
    verify_webhook_signature(BODY, signature(), SECRET)


@pytest.mark.parametrize("header", [None, "", "sha1=bad", "sha256=bad"])
def test_missing_or_invalid_signature_is_rejected(header: str | None) -> None:
    with pytest.raises(InvalidWebhookSignature):
        verify_webhook_signature(BODY, header, SECRET)


def test_signature_is_bound_to_exact_request_bytes() -> None:
    with pytest.raises(InvalidWebhookSignature):
        verify_webhook_signature(BODY + b" ", signature(), SECRET)

