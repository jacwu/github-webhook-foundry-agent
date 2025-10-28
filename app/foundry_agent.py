#!/usr/bin/env python3
"""Utilities for creating and invoking a Bing-grounded Azure AI Foundry agent.

This module exposes two high-level helpers that other Python files can import:

* :func:`create_agent` – registers a new agent with Bing grounding enabled
* :func:`invoke_agent` – sends a prompt to an existing agent and returns the
  resulting Azure objects (thread, run, messages)

When executed directly (``python create_agent.py``) the script will only create
an agent and report its identifier.
"""

import os
from typing import Any, List, Optional, Sequence

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import BingGroundingTool


DEFAULT_AGENT_NAME = "github-relay-bing-agent"
DEFAULT_AGENT_INSTRUCTIONS = (
    "You are a helpful assistant that can search the web for current information. "
    "When users ask about current events, weather, news, or any time-sensitive technical information, "
    "use Bing search to find accurate, up-to-date answers."
)

def get_last_assistant_message(messages: Sequence[Any]) -> Optional[str]:
    """Return the last assistant response as plain text, if present.

    Supports multiple content shapes commonly returned by Azure Agents:
    - content as a plain string
    - content as a list of segments where each segment can be:
      - a plain string
      - a dict with text in one of: "text", {"text": {"value": ...}},
        "content", "output_text", or segments marked as {"type": "text"}
    - content nested within dict/list structures (flattened recursively)
    """

    def _role_of(msg: Any) -> str:
        if isinstance(msg, dict):
            role = msg.get("role") or msg.get("author") or ""
        else:
            role = getattr(msg, "role", "") or getattr(msg, "author", "")
        
        # Convert to string and normalize
        role_str = str(role).lower()
        
        # Handle enum-style role values like "messagerole.assistant" or "messagerole.agent"
        if "." in role_str:
            role_str = role_str.split(".")[-1]
        
        # Normalize "agent" to "assistant"
        if role_str == "agent":
            role_str = "assistant"
            
        return role_str

    def _extract_text(obj: Any, out: List[str]) -> None:
        # Plain string
        if isinstance(obj, str):
            if obj:
                out.append(obj)
            return
        # Sequence: dive into items
        if isinstance(obj, (list, tuple)):
            for it in obj:
                _extract_text(it, out)
            return
        
        # Try to convert Azure SDK objects to dict if they have as_dict method
        if hasattr(obj, 'as_dict') and callable(getattr(obj, 'as_dict')):
            try:
                obj = obj.as_dict()
            except Exception:
                pass  # If conversion fails, try other methods
        
        # Mapping-like: try common text holders
        # Check for dict-like behavior using hasattr instead of isinstance
        if isinstance(obj, dict) or (hasattr(obj, 'get') and hasattr(obj, 'keys')):
            # Direct text slots
            if isinstance(obj.get("text"), str):
                out.append(obj["text"])  # type: ignore[index]
                return
            # text as object with value
            if isinstance(obj.get("text"), dict):
                val = obj["text"].get("value")  # type: ignore[index]
                if isinstance(val, str) and val:
                    out.append(val)
                    return
            # output_text or content holding string
            for key in ("output_text", "content", "message", "value"):
                v = obj.get(key)
                if isinstance(v, str) and v:
                    out.append(v)
                    return
            # type-qualified segments like {"type": "text", "text": {"value": "..."}}
            if obj.get("type") == "text":
                t = obj.get("text")
                if isinstance(t, str) and t:
                    out.append(t)
                    return
                if isinstance(t, dict):
                    val = t.get("value")
                    if isinstance(val, str) and val:
                        out.append(val)
                        return
            # Otherwise, recurse into nested fields that are list/dict-like
            for v in obj.values():
                if isinstance(v, (list, tuple, dict)):
                    _extract_text(v, out)
            return

    # Walk messages from newest to oldest looking for assistant
    # Azure returns messages with newest first, so iterate directly (no reverse)
    for message in messages:
        role = _role_of(message)
        if role != "assistant":
            continue
        # Fetch content attr or key
        content = (
            message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
        )
        if content is None:
            continue
        # Fast path: plain string
        if isinstance(content, str) and content:
            return content
        # General path: flatten
        parts: List[str] = []
        _extract_text(content, parts)
        if parts:
            return "\n".join(p for p in parts if p)
    return None


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} environment variable is not set")
    return value


def get_project_client() -> AIProjectClient:
    """Create an authenticated ``AIProjectClient`` using environment settings."""

    load_dotenv()
    endpoint = _require_env("PROJECT_ENDPOINT")
    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())


def _resolve_agent_metadata(
    *,
    agent_name: Optional[str],
    instructions: Optional[str],
) -> tuple[str, str]:
    resolved_name = agent_name or os.getenv("AIFOUNDRY_AGENT_NAME", DEFAULT_AGENT_NAME)
    resolved_instructions = (
        instructions or os.getenv("AIFOUNDRY_AGENT_INSTRUCTIONS", DEFAULT_AGENT_INSTRUCTIONS)
    )
    return resolved_name, resolved_instructions


def _extract_agent_id(agent: Any) -> Optional[str]:
    if agent is None:
        return None
    if hasattr(agent, "id"):
        return getattr(agent, "id")
    if isinstance(agent, dict):
        return agent.get("id")
    return None


def create_agent(
    *,
    client: Optional[AIProjectClient] = None,
    model_deployment_name: Optional[str] = None,
    bing_connection_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    instructions: Optional[str] = None,
):
    """Register a Bing-grounded Azure AI Foundry agent and return the SDK object."""

    load_dotenv()
    model_name = model_deployment_name or _require_env("MODEL_DEPLOYMENT_NAME")
    bing_connection = bing_connection_id or _require_env("BING_CONNECTION_NAME")
    resolved_name, resolved_instructions = _resolve_agent_metadata(
        agent_name=agent_name,
        instructions=instructions,
    )

    sdk_client = client or get_project_client()

    tool = BingGroundingTool(connection_id=bing_connection)
    agent = sdk_client.agents.create_agent(
        model=model_name,
        name=resolved_name,
        instructions=resolved_instructions,
        tools=tool.definitions,
    )

    agent_id = _extract_agent_id(agent)
    if agent_id:
        print(f"✅ Created agent successfully! Agent ID: {agent_id}")
        print(f"💡 Set AIFOUNDRY_AGENT_ID={agent_id} in your environment for future use.")
    else:
        print("✅ Created agent failed!")

    return agent_id


def invoke_agent(
    *,
    prompt: str,
    agent_id: str,
    client: Optional[AIProjectClient] = None,
    force_bing: bool = False,
) -> str:
    """Send ``prompt`` to ``agent_id`` and return the last assistant message text.

    This function performs the end-to-end flow (create thread, add message,
    run the agent, then list messages) and returns the assistant's final text
    response extracted from the messages.
    """

    if not prompt:
        raise ValueError("prompt cannot be empty")
    if not agent_id:
        raise ValueError("agent_id is required")

    load_dotenv()
    sdk_client = client or get_project_client()

    thread = sdk_client.agents.threads.create()
    sdk_client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt,
    )

    run_kwargs = {
        "thread_id": thread.id,
        "agent_id": agent_id,
    }
    if force_bing:
        run_kwargs["tool_choice"] = {"type": "bing_grounding"}

    sdk_client.agents.runs.create_and_process(**run_kwargs)
    messages_iter = sdk_client.agents.messages.list(thread_id=thread.id)
    messages = list(messages_iter)

    return get_last_assistant_message(messages) or ""


def main() -> None:
    client = get_project_client()
    agent_id = create_agent(client=client)

    result_text = invoke_agent(
        agent_id=agent_id,
        prompt="Hello, what's the lastest version of next.js?",
        force_bing=True,
    )

    print(result_text)


if __name__ == "__main__":
    main()


__all__ = [
    "create_agent",
    "get_project_client",
    "invoke_agent",
    "get_last_assistant_message",
]
