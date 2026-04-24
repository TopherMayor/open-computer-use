from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from computer_use.server import error_result, handle_request, json_dumps, ok_text, pretty_json
from computer_use.types import ELEMENT_CACHE, CachedElement, clear_cache, element_from_index, frame_center


@pytest.fixture(autouse=True)
def clean_cache():
    clear_cache()
    yield
    clear_cache()


class TestJsonHelpers:
    def test_json_dumps_compact(self):
        result = json_dumps({"a": 1, "b": "hello"})
        assert '"a":1' in result
        assert "\n" not in result

    def test_pretty_json_indented(self):
        result = pretty_json({"a": 1})
        assert "\n" in result

    def test_ok_text_with_string(self):
        result = ok_text("hello")
        assert result == {"content": [{"type": "text", "text": "hello"}]}

    def test_ok_text_with_dict(self):
        result = ok_text({"key": "value"})
        content = result["content"][0]
        assert content["type"] == "text"
        parsed = json.loads(content["text"])
        assert parsed["key"] == "value"

    def test_error_result_basic(self):
        result = error_result("something broke")
        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert "something broke" in text

    def test_error_result_with_details(self):
        result = error_result("fail", details={"code": 42})
        text = result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["details"]["code"] == 42


class TestHandleRequest:
    def test_ping_returns_empty_result(self):
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp["result"] == {}

    def test_initialize_returns_capabilities(self):
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert resp["result"]["capabilities"]["tools"]["listChanged"] is False

    def test_tools_list(self):
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp["result"]["tools"]
        assert len(tools) >= 9

    def test_unknown_method_returns_error(self):
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "nonexistent"})
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_no_id_returns_none(self):
        result = handle_request({"method": "ping"})
        assert result is None

    def test_tool_call_unknown_tool(self):
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "bogus", "arguments": {}},
        })
        assert resp["result"]["isError"] is True

    def test_tool_call_get_app_state_missing_app(self):
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_app_state", "arguments": {}},
        })
        assert resp["result"]["isError"] is True

    def test_resources_list(self):
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "resources/list"})
        assert resp["result"]["resources"] == []

    def test_prompts_list(self):
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "prompts/list"})
        assert resp["result"]["prompts"] == []


class TestTypesModule:
    def test_element_from_index_unknown_raises(self):
        with pytest.raises(RuntimeError, match="Unknown element_index"):
            element_from_index("nonexistent")

    def test_frame_center_none_raises(self):
        with pytest.raises(RuntimeError, match="does not expose a screen frame"):
            frame_center(None)

    def test_frame_center_valid(self):
        frame = {"center_x": 100.6, "center_y": 200.4}
        x, y = frame_center(frame)
        assert x == 101
        assert y == 200

    def test_flat_elements(self):
        from computer_use.types import flat_elements
        ELEMENT_CACHE["0"] = CachedElement(
            element=None, frame=None, app="Test", role="button", title="OK",
        )
        result = flat_elements()
        assert len(result) == 1
        assert result[0]["element_index"] == "0"
        assert result[0]["role"] == "button"

    def test_clear_cache(self):
        ELEMENT_CACHE["0"] = CachedElement(element=None, frame=None, app="X")
        clear_cache()
        assert len(ELEMENT_CACHE) == 0


class TestInputUtils:
    def test_normalize_button_valid(self):
        from computer_use.backends.input_utils import normalize_button
        assert normalize_button("left") == "left"
        assert normalize_button("RIGHT") == "right"
        assert normalize_button("Middle") == "middle"

    def test_normalize_button_invalid(self):
        from computer_use.backends.input_utils import normalize_button
        with pytest.raises(RuntimeError, match="mouse_button"):
            normalize_button("side")

    def test_normalize_button_none_default(self):
        from computer_use.backends.input_utils import normalize_button
        assert normalize_button("") == "left"


class TestLinuxKeyNormalization:
    def test_normalize_key_token_basic(self):
        from computer_use.backends.linux_x11 import normalize_key_token
        assert normalize_key_token("return") == "enter"
        assert normalize_key_token("Escape") == "esc"
        assert normalize_key_token("tab") == "tab"

    def test_normalize_key_token_kp(self):
        from computer_use.backends.linux_x11 import normalize_key_token
        assert normalize_key_token("kp_5") == "5"

    def test_normalize_key_token_modifiers(self):
        from computer_use.backends.linux_x11 import normalize_key_token
        assert normalize_key_token("super") == "ctrl"
        assert normalize_key_token("cmd") == "ctrl"
        assert normalize_key_token("command") == "ctrl"
        assert normalize_key_token("meta") == "ctrl"
        assert normalize_key_token("ctrl") == "ctrl"
        assert normalize_key_token("alt") == "alt"
        assert normalize_key_token("option") == "alt"

    def test_press_key_sequence_empty_raises(self):
        from computer_use.backends.linux_x11 import _press_key_sequence
        with patch("computer_use.backends.linux_x11.require_pyautogui", return_value=MagicMock()), \
             pytest.raises(RuntimeError, match="key must not be empty"):
            _press_key_sequence("")

    def test_press_key_sequence_single(self):
        from computer_use.backends.linux_x11 import _press_key_sequence
        mock_pag = MagicMock()
        with patch("computer_use.backends.linux_x11.require_pyautogui", return_value=mock_pag):
            _press_key_sequence("enter")
        mock_pag.press.assert_called_once_with("enter")

    def test_press_key_sequence_combo(self):
        from computer_use.backends.linux_x11 import _press_key_sequence
        mock_pag = MagicMock()
        with patch("computer_use.backends.linux_x11.require_pyautogui", return_value=mock_pag):
            _press_key_sequence("ctrl+c")
        mock_pag.hotkey.assert_called_once_with("ctrl", "c")


class TestFakeBackend:
    def test_list_apps(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        apps = be.list_apps()
        assert len(apps) == 1
        assert apps[0]["name"] == "FakeApp"

    def test_capture_screenshot(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        b64, w, h, method = be.capture_screenshot()
        assert w == 1920
        assert h == 1080
        assert method == "fake"
        assert len(b64) > 0

    def test_get_accessibility_tree(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        tree = be.get_accessibility_tree("TestApp", 123, max_elements=10)
        assert tree is not None
        assert tree["role"] == "window"
        assert len(tree["children"]) == 9

    def test_click_element(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        be.get_accessibility_tree("TestApp", 123)
        result = be.click(element_index="1", x=None, y=None)
        assert result["success"] is True
        assert result["method"] == "AXPress"

    def test_click_coordinates(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.click(element_index=None, x=100, y=200, mouse_button="right", click_count=2)
        assert result["success"] is True
        assert result["method"] == "mouse"
        assert result["x"] == 100
        assert result["y"] == 200
        assert result["button"] == "right"
        assert result["click_count"] == 2

    def test_drag(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.drag(10, 20, 30, 40, duration=0.5)
        assert result["success"] is True
        assert result["from"] == [10, 20]
        assert result["to"] == [30, 40]

    def test_press_key(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.press_key("Return")
        assert result["success"] is True
        assert result["key"] == "Return"

    def test_type_text(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.type_text("hello world")
        assert result["success"] is True
        assert result["chars"] == 11

    def test_scroll(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.scroll("0", "down", 2.0)
        assert result["success"] is True
        assert result["direction"] == "down"
        assert result["pages"] == 2.0

    def test_set_value(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.set_value("0", "test")
        assert result["success"] is True

    def test_perform_action(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.perform_action("0", "AXPress")
        assert result["success"] is True
        assert result["action"] == "AXPress"

    def test_screen_size(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        size = be.screen_size()
        assert size == {"width": 1920, "height": 1080}

    def test_is_accessibility_trusted(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        assert be.is_accessibility_trusted() is True

    def test_flat_elements(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.flat_elements()
        assert isinstance(result, list)

    def test_element_from_index(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        el = be.element_from_index("3")
        assert el.role == "button"
        assert el.title == "Element 3"


class TestLinuxScrollDirections:
    def test_scroll_up(self):
        from computer_use.backends.linux_x11 import LinuxX11Backend
        ELEMENT_CACHE["1"] = CachedElement(
            element=None,
            frame={"x": 10, "y": 20, "width": 100, "height": 30, "center_x": 60, "center_y": 35},
            app="TestApp", role="scroll", title="List",
        )
        mock_pag = MagicMock()
        from computer_use.backends import input_utils, linux_x11
        with patch.object(input_utils, "require_pyautogui", return_value=mock_pag), \
             patch.object(linux_x11, "element_from_index") as mock_efi:
            mock_efi.return_value = ELEMENT_CACHE["1"]
            backend = LinuxX11Backend()
            result = backend.scroll("1", "up", 1.0)
        assert result["success"] is True
        assert result["direction"] == "up"

    def test_scroll_invalid_direction(self):
        from computer_use.backends.linux_x11 import LinuxX11Backend
        ELEMENT_CACHE["1"] = CachedElement(
            element=None,
            frame={"x": 10, "y": 20, "width": 100, "height": 30, "center_x": 60, "center_y": 35},
            app="TestApp", role="scroll", title="List",
        )
        mock_pag = MagicMock()
        from computer_use.backends import input_utils, linux_x11
        with patch.object(input_utils, "require_pyautogui", return_value=mock_pag), \
             patch.object(linux_x11, "element_from_index") as mock_efi:
            mock_efi.return_value = ELEMENT_CACHE["1"]
            backend = LinuxX11Backend()
            with pytest.raises(RuntimeError, match="direction must be one of"):
                backend.scroll("1", "diagonal", 1.0)


class TestLinuxClickEdgeCases:
    def test_click_without_element_or_coords_raises(self):
        from computer_use.backends.linux_x11 import LinuxX11Backend
        backend = LinuxX11Backend()
        with pytest.raises(RuntimeError, match="element_index or both x and y"):
            backend.click(element_index=None, x=None, y=None)

    def test_click_double_click_uses_mouse(self):
        from computer_use.backends.linux_x11 import LinuxX11Backend
        ELEMENT_CACHE["1"] = CachedElement(
            element=MagicMock(),
            frame={"x": 10, "y": 20, "width": 100, "height": 30, "center_x": 60, "center_y": 35},
            app="TestApp", role="button", title="OK",
        )
        mock_pag = MagicMock()
        from computer_use.backends import linux_x11
        with patch.object(linux_x11, "require_pyautogui", return_value=mock_pag), \
             patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock()}):
            backend = LinuxX11Backend()
            result = backend.click(element_index="1", x=None, y=None, click_count=2)
        assert result["success"] is True
        assert result["method"] == "mouse"
        assert result["click_count"] == 2
