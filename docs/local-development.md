# Local Development

Minimal steps to run and test the FastAPI webhook locally.

## Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configure `.env`
```bash
cp .env.example .env
```
Populate at least `GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`, and `AIFOUNDRY_AGENT_ID`. Optionally set `PORT`.

## Start the App
```bash
python main.py        # defaults to port 8000
```

## Expose Public URL
- Run `ngrok http <port>`.
- Use the returned HTTPS URL plus `/webhook` in your GitHub webhook settings.

## Quick Debug Checklist
- Logs appear in the terminal; ngrok inspector lives at `http://127.0.0.1:4040`.
- `401` responses mean the webhook secret mismatches.
- `200` ignores usually mean the comment lacked `@FoundryAgent` or the event action was not `created`.

## End-to-End Smoke Test
1. Start FastAPI and ngrok.
2. Update the GitHub webhook to the current ngrok URL.
3. Comment on an issue with `@FoundryAgent <prompt>`.
4. Expect a `202 Accepted` delivery and a follow-up GitHub comment from the agent.

