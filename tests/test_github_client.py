import json
from importlib import reload

import pytest


class DummyResponse:
    def __init__(self, status_code=201, json_data=None):
        self.status_code = status_code
        self._json = json_data or {"id": 1, "body": "ok"}
        self.text = json.dumps(self._json)

    def json(self):
        return self._json


def test_post_comment_success(monkeypatch):
    from app import github_client as gh
    reload(gh)

    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers or {}
        calls["json"] = json or {}
        return DummyResponse(201, {"id": 99})

    monkeypatch.setattr(gh, "requests", type("R", (), {"post": staticmethod(fake_post)}))

    ok, resp = gh.post_issue_comment(
        owner="octo",
        repo="repo",
        issue_number=123,
        body="hello",
        token="tkn",
    )

    assert ok is True
    assert resp["id"] == 99
    assert calls["url"].endswith("/repos/octo/repo/issues/123/comments")
    assert calls["headers"]["Authorization"] == "Bearer tkn"
    assert calls["json"]["body"] == "hello"


def test_post_comment_failure(monkeypatch):
    from app import github_client as gh
    reload(gh)

    def fake_post(url, headers=None, json=None, timeout=None):
        return DummyResponse(401, {"message": "bad token"})

    monkeypatch.setattr(gh, "requests", type("R", (), {"post": staticmethod(fake_post)}))

    ok, resp = gh.post_issue_comment(
        owner="o",
        repo="r",
        issue_number=1,
        body="b",
        token="bad",
    )

    assert ok is False
    assert resp["message"] == "bad token"

