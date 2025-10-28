import hmac
import hashlib
import json
from importlib import reload

import pytest
from fastapi.testclient import TestClient


def reload_module():
    from app import webhook as wh

    reload(wh)
    return wh

def make_signature(secret: bytes, payload: bytes) -> str:
    return "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()


def build_payload(body: str, action: str = "created"):
    return {
        "action": action,
        "comment": {
            "id": 42,
            "body": body,
            "html_url": "https://github.com/o/r/issues/1#issuecomment-42",
        },
        "issue": {"number": 1},
        "repository": {"owner": {"login": "o"}, "name": "r"},
    }


def setup_app(monkeypatch):
    from app import webhook as wh
    reload(wh)

    # Mock the agent invocation and GitHub client
    calls = {"invoke": [], "post": []}

    def fake_invoke_agent(prompt: str, agent_id: str, client=None, force_bing=False):
        calls["invoke"].append({
            "prompt": prompt,
            "agent_id": agent_id,
            "force_bing": force_bing,
        })
        return "agent-response-text"

    def fake_post_issue_comment(owner, repo, issue_number, body, token):
        calls["post"].append({
            "owner": owner,
            "repo": repo,
            "issue_number": issue_number,
            "body": body,
            "token": token,
        })
        return True, {"id": 99}

    monkeypatch.setattr(wh, "invoke_agent", fake_invoke_agent)
    monkeypatch.setattr(wh, "post_issue_comment", fake_post_issue_comment)

    secret = b"topsecret"
    token = "ghs_123"
    agent_id = "agent-abc"

    wh.GITHUB_WEBHOOK_SECRET = secret
    wh.GITHUB_TOKEN = token
    wh.AIFOUNDRY_AGENT_ID = agent_id

    client = TestClient(wh.app)
    return wh, client, secret, calls


def test_is_target_comment_matches_anywhere_case_insensitive():
    wh = reload_module()

    assert wh._is_target_comment("@FoundryAgent please do X") is True
    assert wh._is_target_comment("Please @FoundryAgent do Y") is True
    assert wh._is_target_comment("prefix @foundryagent suffix") is True
    assert wh._is_target_comment("no mention here") is False
    assert wh._is_target_comment("") is False


def test_strip_mention_extracts_after_first_and_trims_punct():
    wh = reload_module()

    assert wh._strip_mention("@FoundryAgent:   ,!  Hello world") == "Hello world"
    assert wh._strip_mention("Please @FoundryAgent   --  do this") == "do this"

    s = "@foundryagent ??? first part @FoundryAgent second"
    assert wh._strip_mention(s) == "first part @FoundryAgent second"

    assert wh._strip_mention("前缀 @FoundryAgent ，、、你好") == "你好"


def test_strip_mention_no_mention_returns_trimmed_text():
    wh = reload_module()

    assert wh._strip_mention("  no mention  ") == "no mention"


def test_webhook_accepts_and_processes_agent_flow(monkeypatch):
    wh, client, secret, calls = setup_app(monkeypatch)

    payload_dict = build_payload("@FoundryAgent  hello world ")
    payload = json.dumps(payload_dict).encode()
    sig = make_signature(secret, payload)

    resp = client.post(
        "/webhook",
        data=payload,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 202

    # BackgroundTasks should have executed mocked functions
    assert calls["invoke"][0]["prompt"] == "hello world"
    assert calls["post"][0]["owner"] == "o"
    assert calls["post"][0]["repo"] == "r"
    assert calls["post"][0]["issue_number"] == 1
    assert "agent-response-text" in calls["post"][0]["body"]


def test_webhook_accepts_when_mention_mid_comment_and_strips_punct(monkeypatch):
    wh, client, secret, calls = setup_app(monkeypatch)

    payload_dict = build_payload("Please @FoundryAgent:   ,!  do this")
    payload = json.dumps(payload_dict).encode()
    sig = make_signature(secret, payload)

    resp = client.post(
        "/webhook",
        data=payload,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 202
    # Prompt passed to agent should be cleaned and only the part after mention
    assert calls["invoke"][0]["prompt"] == "do this"


def test_webhook_ignores_non_created_action(monkeypatch):
    wh, client, secret, calls = setup_app(monkeypatch)

    payload = json.dumps(build_payload("@FoundryAgent hi", action="edited")).encode()
    sig = make_signature(secret, payload)

    resp = client.post(
        "/webhook",
        data=payload,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert calls["invoke"] == []
    assert calls["post"] == []


def test_webhook_ignores_non_matching_comment(monkeypatch):
    wh, client, secret, calls = setup_app(monkeypatch)

    payload = json.dumps(build_payload("Just a comment")).encode()
    sig = make_signature(secret, payload)

    resp = client.post(
        "/webhook",
        data=payload,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert calls["invoke"] == []
    assert calls["post"] == []


def test_webhook_rejects_bad_signature(monkeypatch):
    wh, client, secret, calls = setup_app(monkeypatch)

    payload = json.dumps(build_payload("@FoundryAgent hi")).encode()
    bad_sig = "sha256=deadbeef"

    resp = client.post(
        "/webhook",
        data=payload,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": bad_sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 401
    assert calls["invoke"] == []
    assert calls["post"] == []
