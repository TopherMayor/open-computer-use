from __future__ import annotations

import pytest
from mcp_client import MCPClient


class TestFailureModes:
    def test_backend_unavailable(self):
        client = MCPClient(backend="nonexistent")
        client.start()
        try:
            result = client.initialize()
            assert "result" in result
        finally:
            client.close()

    def test_unknown_element_index(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("click", {"app": "FakeApp", "element_index": "999"})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            text = text_content.get("text", "")
            assert "error" in text.lower() or "unknown" in text.lower()
        finally:
            client.close()

    def test_invalid_action(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("perform_secondary_action", {"app": "FakeApp", "element_index": "0", "action": "InvalidAction"})
            assert "result" in result
        finally:
            client.close()

    def test_missing_app_for_list_apps(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("list_apps", {})
            assert "result" in result
        finally:
            client.close()