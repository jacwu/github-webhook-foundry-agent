"""Security utilities, including GitHub webhook HMAC validation."""

import hmac
import hashlib
from typing import Optional


def validate_github_signature(secret: bytes, payload: bytes, signature_header: Optional[str]) -> bool:
    """Validate GitHub webhook signature.

    GitHub sends an ``X-Hub-Signature-256`` header containing an HMAC SHA-256
    of the raw request payload. The format is ``sha256=<hex>``.
    Returns True on match; False otherwise.
    """
    if not signature_header or not isinstance(signature_header, str):
        return False

    try:
        algo, sig = signature_header.split("=", 1)
    except ValueError:
        return False
    if algo.lower() != "sha256" or not sig:
        return False

    mac = hmac.new(secret or b"", payload or b"", hashlib.sha256)
    expected = mac.hexdigest()
    return hmac.compare_digest(sig, expected)


__all__ = ["validate_github_signature"]

