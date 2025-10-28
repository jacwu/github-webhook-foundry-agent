#!/usr/bin/env python3
"""Comprehensive tests for foundry_agent.py module.

This file consolidates all tests for the foundry_agent module, including:
- Agent creation with Bing grounding
- Agent invocation with prompts
- Message parsing from Azure SDK responses
"""

import sys
from pathlib import Path
from types import SimpleNamespace
import importlib

# Add parent directory to path to import foundry_agent
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app import foundry_agent


# ==============================================================================
# Mock Classes for Azure SDK
# ==============================================================================

class FakeBingGroundingTool:
    """Mock Azure BingGroundingTool for testing."""
    created_connections: list[str] = []
    last_definitions = None

    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        FakeBingGroundingTool.created_connections.append(connection_id)
        self.definitions = [
            {
                "type": "bing_grounding",
                "connection_id": connection_id,
            }
        ]
        FakeBingGroundingTool.last_definitions = self.definitions


class FakeAgents:
    """Mock Azure Agents API for testing."""
    def __init__(self):
        self.create_agent_calls: list[dict] = []
        self.thread_creations = 0
        self.messages_created: list[dict] = []
        self.run_calls: list[dict] = []
        self.message_list_calls: list[str] = []
        self._thread = SimpleNamespace(id="thread-123")
        self._messages = [
            SimpleNamespace(id="msg-1", role="assistant", content="assistant says hi"),
            SimpleNamespace(
                id="msg-2",
                role="assistant",
                content=[{"text": "structured note"}],
            ),
        ]
        self.threads = self.Threads(self)
        self.messages = self.Messages(self)
        self.runs = self.Runs(self)

    def create_agent(self, **kwargs):
        self.create_agent_calls.append(kwargs)
        return SimpleNamespace(id="agent-789", name=kwargs.get("name"))

    class Threads:
        def __init__(self, outer):
            self._outer = outer

        def create(self):
            self._outer.thread_creations += 1
            return self._outer._thread

    class Messages:
        def __init__(self, outer):
            self._outer = outer

        def create(self, **kwargs):
            self._outer.messages_created.append(kwargs)
            return SimpleNamespace(id="msg-outbound")

        def list(self, **kwargs):
            thread_id = kwargs.get("thread_id")
            if thread_id is not None:
                self._outer.message_list_calls.append(thread_id)
            return list(self._outer._messages)

    class Runs:
        def __init__(self, outer):
            self._outer = outer

        def create_and_process(self, **kwargs):
            self._outer.run_calls.append(kwargs)
            return SimpleNamespace(id="run-456", status="succeeded")


class FakeClient:
    """Mock Azure AIProjectClient for testing."""
    def __init__(self):
        self.agents = FakeAgents()


# ==============================================================================
# Mock Classes for Message Parsing Tests
# ==============================================================================

class MockAzureMessage:
    """Mock Azure SDK ThreadMessage object."""
    
    def __init__(self, role, content):
        self.role = MockRole(role)
        self.content = content
    
    def get(self, key, default=None):
        return getattr(self, key, default)


class MockRole:
    """Mock Azure SDK MessageRole enum."""
    
    def __init__(self, role_name):
        self.role_name = role_name
    
    def __str__(self):
        # Simulate Azure SDK enum string representation
        if self.role_name == "assistant":
            return "MessageRole.agent"  # Azure SDK uses "agent" internally
        return f"MessageRole.{self.role_name}"


class MockMessageTextContent:
    """Mock Azure SDK MessageTextContent object."""
    
    def __init__(self, value, annotations=None):
        self.type = "text"
        self.text = {"value": value, "annotations": annotations or []}
    
    def as_dict(self):
        return {
            "type": self.type,
            "text": self.text
        }
    
    def get(self, key, default=None):
        data = self.as_dict()
        return data.get(key, default)


# ==============================================================================
# Tests for create_agent function
# ==============================================================================

def test_create_agent_uses_client_and_returns_agent(monkeypatch):
    """Test that create_agent properly calls Azure SDK and returns agent ID."""
    module = importlib.reload(foundry_agent)
    monkeypatch.setattr(module, "load_dotenv", lambda: None)
    FakeBingGroundingTool.created_connections = []
    FakeBingGroundingTool.last_definitions = None
    monkeypatch.setattr(module, "BingGroundingTool", FakeBingGroundingTool)

    client = FakeClient()

    agent_id = module.create_agent(
        client=client,
        model_deployment_name="model-x",
        bing_connection_id="conn-42",
        agent_name="custom-name",
        instructions="Do great things",
    )

    assert agent_id == "agent-789"
    assert FakeBingGroundingTool.created_connections == ["conn-42"]

    assert len(client.agents.create_agent_calls) == 1
    call = client.agents.create_agent_calls[0]
    assert call["model"] == "model-x"
    assert call["name"] == "custom-name"
    assert call["instructions"] == "Do great things"
    assert call["tools"] == FakeBingGroundingTool.last_definitions


# ==============================================================================
# Tests for invoke_agent function
# ==============================================================================

def test_invoke_agent_invokes_full_conversation(monkeypatch):
    """Test that invoke_agent performs full conversation flow."""
    module = importlib.reload(foundry_agent)
    monkeypatch.setattr(module, "load_dotenv", lambda: None)

    client = FakeClient()

    result = module.invoke_agent(
        client=client,
        agent_id="agent-789",
        prompt="How is the weather?",
        force_bing=True,
    )

    expected_text = module.get_last_assistant_message(client.agents._messages)
    assert result == expected_text

    assert client.agents.thread_creations == 1
    assert client.agents.messages_created == [
        {"thread_id": "thread-123", "role": "user", "content": "How is the weather?"}
    ]
    assert client.agents.run_calls[0]["tool_choice"] == {"type": "bing_grounding"}
    assert client.agents.run_calls[0]["thread_id"] == "thread-123"
    assert client.agents.run_calls[0]["agent_id"] == "agent-789"
    assert client.agents.message_list_calls == ["thread-123"]


# ==============================================================================
# Tests for get_last_assistant_message function
# ==============================================================================

def test_get_last_assistant_message_with_azure_sdk_objects():
    """Test parsing with Azure SDK-like objects (MessageRole.agent enum)."""
    messages = [
        MockAzureMessage(
            role="assistant",
            content=[
                MockMessageTextContent(
                    value="Hello! This is the assistant response.",
                    annotations=[]
                )
            ]
        ),
        MockAzureMessage(
            role="user",
            content=[
                MockMessageTextContent(
                    value="User's question",
                    annotations=[]
                )
            ]
        )
    ]
    
    result = foundry_agent.get_last_assistant_message(messages)
    
    assert result == "Hello! This is the assistant response."


def test_get_last_assistant_message_with_plain_dicts():
    """Test parsing with plain dict messages (backward compatibility)."""
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": {
                        "value": "Plain dict response"
                    }
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": {
                        "value": "User message"
                    }
                }
            ]
        }
    ]
    
    result = foundry_agent.get_last_assistant_message(messages)
    
    assert result == "Plain dict response"


def test_get_last_assistant_message_with_citations():
    """Test parsing assistant message with URL citations."""
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": {
                        "value": "Here is information from Bing【3:1†source】.",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "text": "【3:1†source】",
                                "url_citation": {
                                    "url": "https://example.com"
                                }
                            }
                        ]
                    }
                }
            ]
        }
    ]
    
    result = foundry_agent.get_last_assistant_message(messages)
    
    # Citations should be included in the text
    assert "Here is information from Bing" in result
    assert "【3:1†source】" in result


def test_get_last_assistant_message_returns_none_when_no_assistant():
    """Test that None is returned when there are no assistant messages."""
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": {"value": "Hello"}}]
        }
    ]
    
    result = foundry_agent.get_last_assistant_message(messages)
    
    assert result is None


def test_get_last_assistant_message_returns_latest_assistant():
    """Test that it returns the most recent (first in list) assistant message.
    
    Azure returns messages with newest first, so the function should return
    the first assistant message it encounters in the list.
    """
    messages = [
        {
            "role": "assistant",
            "content": [{"type": "text", "text": {"value": "Newest assistant message"}}]
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": {"value": "User message"}}]
        },
        {
            "role": "assistant",
            "content": [{"type": "text", "text": {"value": "Older assistant message"}}]
        }
    ]
    
    result = foundry_agent.get_last_assistant_message(messages)
    
    # Should return the newest (first) assistant message
    assert result == "Newest assistant message"


def test_get_last_assistant_message_handles_mixed_types():
    """Test parsing with mixed Azure SDK objects and dicts."""
    messages = [
        MockAzureMessage(
            role="assistant",
            content=[
                MockMessageTextContent(
                    value="Azure SDK message",
                    annotations=[]
                )
            ]
        ),
        {
            "role": "user",
            "content": [{"type": "text", "text": {"value": "Dict message"}}]
        }
    ]
    
    result = foundry_agent.get_last_assistant_message(messages)
    
    assert result == "Azure SDK message"


def test_get_last_assistant_message_with_plain_string_content():
    """Test parsing when content is a plain string."""
    messages = [
        {
            "role": "assistant",
            "content": "Simple string response"
        }
    ]
    
    result = foundry_agent.get_last_assistant_message(messages)
    
    assert result == "Simple string response"


def test_get_last_assistant_message_handles_empty_content():
    """Test that empty or None content is handled gracefully."""
    messages = [
        {
            "role": "assistant",
            "content": None
        },
        {
            "role": "assistant",
            "content": []
        }
    ]
    
    result = foundry_agent.get_last_assistant_message(messages)
    
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
