from unittest.mock import patch

import pytest
from mcp_client import MCPClient


class TestFailureModes:
    def test_backend_unavailable(self, monkeypatch):
        from open_computer_use.server import get_backend

        monkeypatch.setenv("OPEN_CU_BACKEND", "nonexistent")
        with pytest.raises(ValueError, match="Unknown OPEN_CU_BACKEND"):
            get_backend()

    def test_explicit_backend_failure_never_falls_back_to_fake(self, monkeypatch):
        from open_computer_use.server import get_backend

        monkeypatch.setenv("OPEN_CU_BACKEND", "macos")
        with patch(
            "open_computer_use.backends.macos.create_backend",
            side_effect=RuntimeError("backend init failed"),
        ), pytest.raises(RuntimeError, match="refusing to use the fake backend"):
            get_backend()

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
            result = client.tool_call(
                "perform_secondary_action", {"app": "FakeApp", "element_index": "0", "action": "InvalidAction"})
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
