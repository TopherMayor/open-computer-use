from __future__ import annotations

import json
import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

_IS_FAKE = os.environ.get("OPEN_CU_BACKEND", "fake") == "fake"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_computer_use.server import handle_request, self_test  # noqa: E402
from open_computer_use.types import ELEMENT_CACHE, CachedElement, clear_cache  # noqa: E402

requires_fake = pytest.mark.skipif(not _IS_FAKE, reason="requires fake backend")


@pytest.fixture(autouse=True)
def clean_cache():
    import open_computer_use.server as srv

    clear_cache()
    srv.backend = None
    yield
    clear_cache()
    srv.backend = None


def _req(name: str, arguments: dict | None = None, req_id: int = 1) -> dict:
    return handle_request({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    })


@requires_fake
class TestDragViaHandleRequest:
    def test_drag_valid_coordinates(self):
        resp = _req("drag", {"from_x": 10, "from_y": 20, "to_x": 100, "to_y": 200})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        result = resp["result"]
        assert "content" in result
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["success"] is True
        assert data["from"] == [10, 20]
        assert data["to"] == [100, 200]

    def test_drag_with_custom_duration(self):
        resp = _req("drag", {"from_x": 0, "from_y": 0, "to_x": 50, "to_y": 50, "duration": 1.0})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["duration"] == 1.0


@requires_fake
class TestTypeTextViaHandleRequest:
    def test_type_text_basic(self):
        resp = _req("type_text", {"text": "hello world"})
        assert resp["jsonrpc"] == "2.0"
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["chars"] == 11
        assert data["method"] == "fake"

    def test_type_text_empty_string(self):
        resp = _req("type_text", {"text": ""})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["chars"] == 0


@requires_fake
class TestPressKeyViaHandleRequest:
    def test_press_key_return(self):
        resp = _req("press_key", {"key": "Return"})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["key"] == "Return"

    def test_press_key_combo(self):
        resp = _req("press_key", {"key": "ctrl+c"})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["key"] == "ctrl+c"


@requires_fake
class TestScrollViaHandleRequest:
    def test_scroll_with_element_index(self):
        ELEMENT_CACHE["0"] = CachedElement(
            element=None,
            frame={"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25},
            app="TestApp",
            role="button",
            title="OK",
        )
        resp = _req("scroll", {"element_index": "0", "direction": "down"})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["element_index"] == "0"
        assert data["direction"] == "down"

    def test_scroll_with_pages(self):
        ELEMENT_CACHE["0"] = CachedElement(
            element=None,
            frame={"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25},
            app="TestApp",
            role="button",
            title="OK",
        )
        resp = _req("scroll", {"element_index": "0", "direction": "up", "pages": 2.5})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["pages"] == 2.5


@requires_fake
class TestSetValueViaHandleRequest:
    def test_set_value_basic(self):
        ELEMENT_CACHE["0"] = CachedElement(
            element=None,
            frame={"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25},
            app="TestApp",
            role="button",
            title="OK",
        )
        resp = _req("set_value", {"element_index": "0", "value": "new text"})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["method"] == "AXValue"
        assert data["element_index"] == "0"


@requires_fake
class TestListAppsViaHandleRequest:
    def test_list_apps_default(self):
        resp = _req("list_apps")
        data = json.loads(resp["result"]["content"][0]["text"])
        assert "apps" in data
        assert len(data["apps"]) >= 1
        assert data["apps"][0]["name"] == "FakeApp"

    def test_list_apps_with_include_installed(self):
        resp = _req("list_apps", {"include_installed": True})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert "apps" in data


@requires_fake
class TestPerformSecondaryActionViaHandleRequest:
    def test_perform_secondary_action(self):
        ELEMENT_CACHE["0"] = CachedElement(
            element=None,
            frame={"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25},
            app="TestApp",
            role="button",
            title="OK",
        )
        resp = _req("perform_secondary_action", {"element_index": "0", "action": "AXShowMenu"})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["element_index"] == "0"
        assert data["action"] == "AXShowMenu"


class TestSelfTest:
    def test_self_test_returns_zero(self):
        with patch("sys.stdout", new_callable=StringIO) as _mock_stdout:
            result = self_test()
        assert result == 0

    def test_self_test_output_contains_tool_names(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            self_test()
        output = mock_stdout.getvalue()
        assert "get_app_state" in output
        assert "click" in output
        assert "drag" in output

    def test_self_test_output_is_valid_json(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            self_test()
        data = json.loads(mock_stdout.getvalue())
        assert data["server"] == "open-computer-use"
        assert data["toolCount"] >= 9
        assert data["missingHandlers"] == []
        assert data["schemasValid"] is True


@requires_fake
class TestGetAppStateAnnotated:
    def test_get_app_state_with_annotate_screenshot(self):
        resp = _req("get_app_state", {"app": "TestApp", "annotate_screenshot": True})
        assert resp["jsonrpc"] == "2.0"
        content = resp["result"]["content"]
        image_items = [c for c in content if c.get("type") == "image"]
        assert len(image_items) >= 1
        assert image_items[0]["mimeType"] == "image/png"
        assert len(image_items[0]["data"]) > 0

    def test_get_app_state_without_screenshot(self):
        resp = _req("get_app_state", {"app": "TestApp", "include_screenshot": False})
        content = resp["result"]["content"]
        assert all(c.get("type") != "image" for c in content)


class TestMCPProtocolEdgeCases:
    def test_notification_without_id_returns_none(self):
        result = handle_request({"jsonrpc": "2.0", "method": "ping"})
        assert result is None

    def test_tools_call_null_name_returns_error(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": None, "arguments": {}},
        })
        assert resp["result"]["isError"] is True

    def test_tools_call_missing_name_returns_error(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "id": 43,
            "method": "tools/call",
            "params": {"arguments": {}},
        })
        assert resp["result"]["isError"] is True

    def test_tools_call_empty_name_returns_error(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "id": 44,
            "method": "tools/call",
            "params": {"name": "", "arguments": {}},
        })
        assert resp["result"]["isError"] is True

    def test_outer_exception_handler_returns_jsonrpc_error(self):
        _req("ping")

        class BoomDict(dict):
            def __contains__(self, key):
                raise RuntimeError("boom")

        with patch("open_computer_use.server.TOOL_HANDLERS", BoomDict()):
            resp = handle_request({
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/call",
                "params": {"name": "click", "arguments": {}},
            })
        assert "error" in resp
        assert resp["error"]["code"] == -32603
        assert "boom" in resp["error"]["message"]

    def test_response_includes_request_id(self):
        resp = handle_request({"jsonrpc": "2.0", "id": 77, "method": "ping"})
        assert resp["id"] == 77

    def test_tools_call_with_null_params_uses_defaults(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "id": 55,
            "method": "tools/call",
            "params": None,
        })
        assert resp["result"]["isError"] is True
