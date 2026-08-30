"""Security checks for untrusted GitHub webhook deliveries."""

from __future__ import annotations

import hashlib
import hmac


class InvalidWebhookSignature(ValueError):
    """Raised when a delivery cannot be authenticated as GitHub-originated."""


def verify_webhook_signature(body: bytes, signature_header: str | None, secret: str) -> None:
    """Validate GitHub's SHA-256 HMAC without timing-sensitive comparison."""

    if not secret:
        raise RuntimeError("GitHub webhook secret is not configured.")
    if not signature_header or not signature_header.startswith("sha256="):
        raise InvalidWebhookSignature("Missing or malformed webhook signature.")

    supplied_digest = signature_header.removeprefix("sha256=")
    expected_digest = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(supplied_digest, expected_digest):
        raise InvalidWebhookSignature("Webhook signature did not match the payload.")

