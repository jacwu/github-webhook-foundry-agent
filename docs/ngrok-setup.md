# ngrok Setup

Expose the local FastAPI server for GitHub webhook testing.

## Install
- macOS: `brew install ngrok`
- Others: download from https://ngrok.com/download and follow the installer.

## One-Time Auth
```bash
ngrok config add-authtoken <token>
```

## Run a Tunnel
```bash
ngrok http 8000   # replace with app port if different
```
Note the HTTPS forwarding URL.

## Point GitHub Webhook
- Payload URL: `<https URL>/webhook`
- Content type `application/json`, secret matches local `GITHUB_WEBHOOK_SECRET`.

## Inspect Traffic
- Visit `http://127.0.0.1:4040` for request history and replay.
- Every new tunnel changes the public URL; update GitHub each time.

