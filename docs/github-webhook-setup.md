# GitHub Webhook Setup

Essential steps to deliver `issue_comment` events to the FastAPI service.

## Requirements
- Repo admin rights.
- Public HTTPS endpoint (Azure Web App or current ngrok URL).
- Shared secret that matches `GITHUB_WEBHOOK_SECRET`.

## Configure on GitHub
1. Go to **Settings ▸ Webhooks ▸ Add webhook**.
2. Set Payload URL to `https://<endpoint>/webhook` (use ngrok URL when local).
3. Choose content type `application/json` and paste the shared secret.
4. Select **Let me select individual events ➝ Issue comments** and leave the webhook active.
5. Save.

## Verify
- Trigger **Ping** or **Redeliver** and confirm a `202 Accepted` (or `200` for ignored events).
- A `401` means the secret mismatches or the payload body was altered.

## Keep in Mind
- Only `issue_comment` events with `action=created` and comments containing `@FoundryAgent` anywhere are processed.
- The service forwards only the text after the first `@FoundryAgent` mention, trimming leading punctuation and whitespace (e.g., `: , ! --` and common CJK punctuation like `，、。`).
