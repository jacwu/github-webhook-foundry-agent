import hmac
import hashlib

import pytest


def test_validate_signature_accepts_valid_signature(monkeypatch):
    from importlib import reload
    from app import security as sec
    reload(sec)

    secret = b"topsecret"
    payload = b'{"action":"ping"}'
    signature = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()

    assert sec.validate_github_signature(secret, payload, signature) is True


def test_validate_signature_rejects_invalid_signature(monkeypatch):
    from importlib import reload
    from app import security as sec
    reload(sec)

    secret = b"topsecret"
    payload = b"{}"
    bad_sig = "sha256=deadbeef"

    assert sec.validate_github_signature(secret, payload, bad_sig) is False


def test_validate_signature_handles_missing_header():
    from app.security import validate_github_signature

    assert validate_github_signature(b"s", b"{}", None) is False

