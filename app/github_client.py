"""Minimal GitHub REST API client helpers."""

from typing import Any, Dict, Tuple

import requests

GITHUB_API = "https://api.github.com"


def post_issue_comment(
    *,
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
    token: str,
    timeout: float = 10.0,
) -> Tuple[bool, Dict[str, Any]]:
    """Post a comment to a GitHub issue. Returns (ok, response_json)."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-webhook-azure-foundry-agent",
    }
    resp = requests.post(url, headers=headers, json={"body": body}, timeout=timeout)
    ok = 200 <= resp.status_code < 300
    try:
        data = resp.json()
    except Exception:
        data = {"text": getattr(resp, "text", ""), "status": resp.status_code}
    return ok, data


__all__ = ["post_issue_comment"]

