from __future__ import annotations

import os

import pytest
from mcp_client import MCPClient


class TestDesktopSmoke:
    @pytest.fixture(autouse=True)
    def setup_desktop(self):
        display = os.environ.get("DISPLAY")
        if not display:
            pytest.skip("DISPLAY not set")

    def test_list_apps_includes_fixture_app(self):
        client = MCPClient(backend="linux-x11")
        client.start()
        try:
            result = client.initialize()
            assert "result" in result
        finally:
            client.close()

    def test_get_app_state_returns_screenshot(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("get_app_state", {"app": "FakeApp", "include_screenshot": True})
            assert "result" in result
            content = result["result"]["content"]
            has_image = any(c.get("type") == "image" for c in content)
            assert has_image
        finally:
            client.close()

    def test_click_on_element_changes_state(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("get_app_state", {"app": "FakeApp"})
            assert "result" in result

            result = client.tool_call("click", {"app": "FakeApp", "element_index": "0"})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            text = text_content.get("text", "")
            assert "success" in text.lower()
        finally:
            client.close()

    def test_type_text_enters_text(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("type_text", {"app": "FakeApp", "text": "Hello"})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            text = text_content.get("text", "")
            assert "success" in text.lower()
        finally:
            client.close()

    def test_press_key_handles_tab(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("press_key", {"app": "FakeApp", "key": "Tab"})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            text = text_content.get("text", "")
            assert "success" in text.lower()
        finally:
            client.close()

    def test_scroll_changes_visible_rows(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("get_app_state", {"app": "FakeApp"})
            result = client.tool_call(
                "scroll", {"app": "FakeApp", "element_index": "0", "direction": "down", "pages": 1})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            text = text_content.get("text", "")
            assert "success" in text.lower()
        finally:
            client.close()

    def test_set_value_sets_text_field(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("set_value", {"app": "FakeApp", "element_index": "0", "value": "test"})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            text = text_content.get("text", "")
            assert "success" in text.lower()
        finally:
            client.close()

    def test_drag_moves_object(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call(
                "drag", {"app": "FakeApp", "from_x": 100, "from_y": 100, "to_x": 200, "to_y": 200})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            text = text_content.get("text", "")
            assert "success" in text.lower()
        finally:
            client.close()

    def test_perform_secondary_action(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call(
                "perform_secondary_action", {"app": "FakeApp", "element_index": "0", "action": "AXPress"})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            text = text_content.get("text", "")
            assert "success" in text.lower()
        finally:
            client.close()
