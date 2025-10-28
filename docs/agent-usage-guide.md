# Agent Usage Guide

Essential steps for `app/foundry_agent.py`.

## Prerequisites
- Activate the virtual environment and install dependencies.
- Populate `.env` with `PROJECT_ENDPOINT`, `MODEL_DEPLOYMENT_NAME`, `BING_CONNECTION_NAME`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`.

## Create an Agent
```bash
source venv/bin/activate
python app/foundry_agent.py
```
- Save the printed agent ID as `AIFOUNDRY_AGENT_ID` for later use.

## Invoke an Agent
```python
from app.create_agent import invoke_agent, get_last_assistant_message

thread, run, messages = invoke_agent(
    agent_id="asst_your_agent_id",
    prompt="<your question>"
)
print(get_last_assistant_message(messages))
```