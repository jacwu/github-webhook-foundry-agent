import json
import logging
import os
import string
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, Header, Request, Response, status

from .foundry_agent import invoke_agent
from .github_client import post_issue_comment
from .security import validate_github_signature


log = logging.getLogger("webhook")

app = FastAPI(title="GitHub Webhook Azure Foundry Agent")


# Config via env, may be overridden in tests
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
AIFOUNDRY_AGENT_ID = os.getenv("AIFOUNDRY_AGENT_ID", "")

_MENTION_TOKEN = "@foundryagent"
_CJK_PUNCTUATION = "\uFF0C\u3001\u3002\uFF01\uFF1F\uFF1A\uFF1B"
_LEADING_TRIM_CHARS = string.whitespace + string.punctuation + _CJK_PUNCTUATION

def _extract_event(headers_event: Optional[str]) -> str:
    return (headers_event or "").strip()


def _parse_payload(body: bytes) -> Dict[str, Any]:
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return {}


def _is_target_comment(text: str) -> bool:
    if not text:
        return False
    return _MENTION_TOKEN in text.lower()


def _strip_mention(text: str) -> str:
    raw = text or ""
    lower = raw.lower()
    idx = lower.find(_MENTION_TOKEN)
    if idx == -1:
        return raw.strip()

    remainder = raw[idx + len(_MENTION_TOKEN):]
    cleaned = remainder.lstrip(_LEADING_TRIM_CHARS)
    return cleaned.strip()


def process_comment_background(
    *,
    owner: str,
    repo: str,
    issue_number: int,
    prompt_text: str,
    original_url: Optional[str],
) -> None:
    try:
        response_text = invoke_agent(
            prompt=prompt_text,
            agent_id=AIFOUNDRY_AGENT_ID,
            force_bing=True,
        )
        log.info(response_text)
    except Exception as e:
        log.exception("Agent invocation failed: %s", e)
        return

    body_lines = []
    if original_url:
        body_lines.append(f"Replying to {original_url}")
        body_lines.append("")
    body_lines.append("Response from Foundry Agent:")
    body_lines.append("")
    body_lines.append(response_text or "(no content)")
    body = "\n".join(body_lines)

    try:
        post_issue_comment(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            body=body,
            token=GITHUB_TOKEN,
        )
    except Exception as e:
        log.exception("Posting comment to GitHub failed: %s", e)


@app.post("/webhook")
async def github_webhook(
    response: Response,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
    request: Request = None,
):
    # Only accept issue_comment events
    event = _extract_event(x_github_event)
    log.info("Received GitHub event: %s", event)
    if event != "issue_comment":
        return {"status": "ignored"}

    raw = await request.body() if request else b""

    if not validate_github_signature(GITHUB_WEBHOOK_SECRET, raw or b"", x_hub_signature_256):
        log.error("Signature validation failed")
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"error": "invalid signature"}

    payload = _parse_payload(raw or b"{}")
    action = payload.get("action")
    log.info("Processing action: %s", action)
    if action != "created":
        return {"status": "ignored"}

    comment = payload.get("comment", {}) or {}
    text = comment.get("body", "")
    
    if not _is_target_comment(text):
        return {"status": "ignored"}

    prompt_text = _strip_mention(text)
    repo_info = payload.get("repository", {}) or {}
    owner = (repo_info.get("owner") or {}).get("login") or ""
    repo = repo_info.get("name") or ""
    issue = payload.get("issue", {}) or {}
    issue_number = int(issue.get("number") or 0)
    original_url = comment.get("html_url")

    # Queue background processing and return 202 promptly
    background_tasks.add_task(
        process_comment_background,
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        prompt_text=prompt_text,
        original_url=original_url,
    )
    response.status_code = status.HTTP_202_ACCEPTED
    return {"status": "accepted"}


__all__ = ["app", "process_comment_background"]
