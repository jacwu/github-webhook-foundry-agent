# GitHub Issue Comment - Azure AI Foundry Agent Relay

Relay `issue_comment` events that mention `@FoundryAgent` into an Azure AI Foundry Agent and post the agent's reply back to the originating GitHub issue. Built with FastAPI, designed to run identically locally (venv + ngrok) and in production (Azure Web App), with background task processing to stay within GitHub's webhook response SLA.

## Key Features
- FastAPI webhook endpoint (`/webhook`) handling GitHub `issue_comment` events.
- Filters only comments where `action == created` and body contains `@FoundryAgent` (anywhere).
- Extracts the text **after the first** `@FoundryAgent` mention; trims leading punctuation & whitespace (e.g. `: , ! --` and common CJK punctuation such as `，、。`).
- Invokes an Azure AI Foundry Agent (via `agent-framework-azure-ai`) in a FastAPI background task.
- Posts the agent response back to the same issue using GitHub REST API.
- Secure HMAC signature validation using `X-Hub-Signature-256` + shared secret.
- Unified codebase: same Python files for local dev and Azure Web App deployment.
- Test-driven: unit tests cover agent invocation, webhook parsing, security, and GitHub API integration.

## Architecture Overview
```
GitHub Issue Comment ──(webhook)──▶ FastAPI /webhook
                                 │
                                 ├─ Signature Validation (HMAC SHA-256)
                                 ├─ Comment Filter + Prompt Extraction
                                 └─▶ Background Task:
                                      1. Invoke Azure AI Foundry Agent
                                      2. Post reply comment back to GitHub
```
- Immediate HTTP `202 Accepted` lets GitHub finish delivery quickly.
- Background task manages potentially longer agent + GitHub API calls.
- All secrets provided through environment variables (never committed).

## Repository Structure
```
AGENTS.md                       # Feasibility + requirements overview
README.md                       # (This file) project intro & usage guide
requirements.txt                # Python dependencies
main.py                         # FastAPI entry point (uvicorn launcher)
app/
  foundry_agent.py              # Azure AI Foundry Agent creation & invocation helpers
  github_client.py              # GitHub API wrapper (post issue comments)
  security.py                   # HMAC signature validation utilities
  webhook.py                    # Webhook routing & comment parsing logic
docs/
  agent-usage-guide.md          # Detailed agent creation & invocation steps
  github-webhook-setup.md       # Step-by-step GitHub webhook configuration
  local-development.md          # Local environment + smoke test instructions
  ngrok-setup.md                # ngrok installation & usage
tests/
  test_foundry_agent.py         # Agent module tests (mocked SDK)
  test_github_client.py         # GitHub API interaction tests
  test_security.py              # Signature validation tests
  test_webhook.py               # Webhook parsing & filtering tests
```

## Prerequisites
- Python 3.10+ (recommended)
- GitHub repository admin access (to configure webhook)
- Azure subscription + Azure AI Foundry project & model deployment
- GitHub Personal Access Token (PAT) or GitHub App installation (for posting comments)
- ngrok account (for local tunnel) when testing locally

## Installation & Setup
```bash
# Clone
git clone <repo-url> github-webhook-foundry-agent
cd github-webhook-foundry-agent

# Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize environment variables
cp .env.example .env
```
Edit `.env` with required values (see below), then proceed.

## Environment Variables
| Name | Purpose |
|------|---------|
| PROJECT_ENDPOINT | Azure AI Foundry project endpoint URL |
| MODEL_DEPLOYMENT_NAME | Model deployment name used by the agent |
| BING_CONNECTION_NAME | Bing grounded search connection for agent context |
| AZURE_TENANT_ID | Azure AD tenant (for client credentials) |
| AZURE_CLIENT_ID | Service principal / app registration client ID |
| AZURE_CLIENT_SECRET | Service principal secret |
| AIFOUNDRY_AGENT_ID | Created agent ID (after initial creation) | get the foundry agent id after creation
| GITHUB_WEBHOOK_SECRET | Shared secret for HMAC signature validation |
| GITHUB_TOKEN | PAT (repo:write) for posting issue comments |

## 1. Create an Azure AI Foundry Agent
If you do not yet have an agent ID:
```bash
source venv/bin/activate
python app/foundry_agent.py
```
This script creates the agent using environment credentials and prints its ID. Copy that value into `.env` as `AIFOUNDRY_AGENT_ID`.

## 2. Register the GitHub Webhook
1. Navigate to your repo: Settings → Webhooks → Add webhook.
2. Payload URL (local via ngrok or production): `https://<host>/webhook`
3. Content type: `application/json`
4. Secret: same value as `GITHUB_WEBHOOK_SECRET` in `.env`
5. Select individual events → enable only "Issue comments".
6. Save and use the "Ping" button to verify; expect `202 Accepted`.

### Processing Rules
- Only `issue_comment` events with `action == created` are considered.
- Only comments containing `@FoundryAgent` anywhere are forwarded.
- Prompt = substring after first `@FoundryAgent`, cleaned of leading punctuation/whitespace.

## 3. Local Development & ngrok
Start FastAPI:
```bash
source venv/bin/activate
python main.py          # starts on 0.0.0.0:8000
```
Install & run ngrok (macOS example):
```bash
brew install ngrok
ngrok config add-authtoken <token>
ngrok http 8000
```
Copy the HTTPS forwarding URL (e.g. `https://abcd1234.ngrok.io`) and update the GitHub webhook Payload URL to `https://abcd1234.ngrok.io/webhook`.

### Debugging Aids
- ngrok inspector: `http://127.0.0.1:4040`
- `401 Unauthorized`: signature mismatch (verify secret & raw body integrity).
- `200 OK` (without relay): comment lacked `@FoundryAgent` or wrong `action`.

## Security (Webhook Signature Validation)
The header `X-Hub-Signature-256` is validated using HMAC SHA-256 over the raw JSON payload with `GITHUB_WEBHOOK_SECRET`. If absent or mismatching, the request is rejected (`401`). Never log raw secrets; only log high-level validation outcomes.

## Testing
Run the test suite before committing:
```bash
pytest -v --cov=app
```



