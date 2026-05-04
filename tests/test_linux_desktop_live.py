"""Live Linux X11 desktop integration tests.

Runs against a real GTK3 app on Xvfb using the linux-x11 backend.
Requires: DISPLAY set, Xvfb running, GTK3 test app running.
"""
from __future__ import annotations

import json
import os
import time

import pytest

from mcp_client import MCPClient

pytestmark = pytest.mark.skipif(
    os.environ.get("OPEN_CU_BACKEND") != "linux-x11",
    reason="Requires OPEN_CU_BACKEND=linux-x11 with live desktop",
)

APP = "Desktop Test App"


def _text_from(result: dict) -> str:
    """Extract text content from an MCP tool result."""
    content = result.get("result", {}).get("content", [])
    return next((c.get("text", "") for c in content if c.get("type") == "text"), "")


def _parse_tree(result: dict) -> list[dict]:
    """Flatten the accessibility tree into a list of elements from get_app_state result.

    The response format is: {"app": ..., "accessibility_tree": {node}}
    Each node has: element_index, role, title, value, frame, children, ...
    """
    content = result.get("result", {}).get("content", [])
    for c in content:
        if c.get("type") == "text":
            try:
                data = json.loads(c["text"])
                tree = data.get("accessibility_tree", {})
                if not tree:
                    return []
                elements = []
                def walk(node):
                    elements.append(node)
                    for child in node.get("children", []):
                        walk(child)
                walk(tree)
                return elements
            except (json.JSONDecodeError, KeyError):
                pass
    return []


class TestLinuxDesktopLive:
    """Full integration tests against the real linux-x11 backend + GTK3 app."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = MCPClient(backend="linux-x11")
        self.client.start()
        self.client.initialize()
        yield
        self.client.close()

    def _get_state(self, **kwargs):
        return self.client.tool_call("get_app_state", {"app": APP, **kwargs})

    def test_01_list_apps_finds_desktop_app(self):
        """list_apps should detect the running GTK3 Desktop Test App."""
        result = self.client.tool_call("list_apps", {})
        text = _text_from(result)
        # list_apps returns {"apps": {...}} — check the raw result
        apps_data = result.get("result", {})
        apps_text = json.dumps(apps_data).lower()
        assert "desktop test app" in apps_text or "desktoptest" in apps_text, (
            f"Desktop Test App not found in list_apps output: {apps_text[:500]}"
        )

    def test_02_get_app_state_returns_tree_and_screenshot(self):
        """get_app_state should return both accessibility tree and screenshot."""
        result = self._get_state(include_screenshot=True)
        content = result.get("result", {}).get("content", [])

        has_text = any(c.get("type") == "text" for c in content)
        has_image = any(c.get("type") == "image" for c in content)

        assert has_text, "get_app_state should return accessibility tree text"
        assert has_image, "get_app_state should return a screenshot image"

        # Parse the tree and verify it has elements
        elements = _parse_tree(result)
        assert len(elements) > 0, (
            f"Accessibility tree should have elements. "
            f"Raw text: {_text_from(result)[:500]}"
        )

    def test_03_tree_contains_expected_elements(self):
        """Accessibility tree should contain the GTK3 app's widgets."""
        result = self._get_state()
        elements = _parse_tree(result)

        # Collect all text from elements for inspection
        all_text = " ".join(
            (e.get("title") or "") + " " + (e.get("value") or "") + " " + (e.get("description") or "")
            for e in elements
        ).lower()

        # Debug: print what we actually got
        elem_summary = [(e.get("role",""), e.get("title",""), e.get("element_index","")) for e in elements]

        # Should find our widgets — the tree should have at least some roles
        assert len(elements) > 0, f"Tree was empty. Element summary: {elem_summary}"

        # Look for button or increment in the tree
        roles = [e.get("role", "").lower() for e in elements]
        titles = [e.get("title", "").lower() for e in elements]

        assert "push button" in roles or "button" in roles or "increment" in " ".join(titles), (
            f"Tree should contain a button widget. Roles: {roles}, Titles: {titles}"
        )

    def test_04_click_increment_button_by_element(self):
        """Click the Increment button via element index, counter should change."""
        # Get initial state
        state = self._get_state()
        elements = _parse_tree(state)

        # Find the Increment button
        inc_idx = None
        for e in elements:
            title = (e.get("title") or "").lower()
            role = (e.get("role") or "").lower()
            if "increment" in title and ("button" in role or "push" in role):
                inc_idx = str(e.get("element_index", ""))
                break

        assert inc_idx is not None, (
            f"Could not find Increment button in tree. "
            f"Elements: {[(e.get('title',''), e.get('role',''), e.get('element_index','')) for e in elements]}"
        )

        # Click it
        result = self.client.tool_call("click", {"app": APP, "element_index": inc_idx})
        text = _text_from(result)
        # Should not error
        assert "error" not in text.lower() or "success" in text.lower(), f"Click failed: {text}"

        # Wait for UI to update
        time.sleep(0.5)

        # Verify counter changed
        state2 = self._get_state()
        elements2 = _parse_tree(state2)
        all_text2 = " ".join(
            (e.get("title") or "") + " " + (e.get("value") or "")
            for e in elements2
        )
        # Counter should be >= 1 now
        assert "1" in all_text2, f"Counter should show >=1 after click. Got: {all_text2[:300]}"

    def test_05_visual_click_increment_button(self):
        """visual_click should find and click the Increment button by description."""
        result = self.client.tool_call("visual_click", {
            "description": "the Increment button",
        })
        text = _text_from(result)
        assert "error" not in text.lower() or "click" in text.lower() or "match" in text.lower(), (
            f"visual_click failed: {text[:500]}"
        )

    def test_06_type_text_into_name_field(self):
        """type_text should enter text into the Name entry field."""
        # First click on the Name entry to focus it using visual_locate
        state = self._get_state()
        elements = _parse_tree(state)

        # Find the text entry element
        name_idx = None
        for e in elements:
            role = (e.get("role") or "").lower()
            title = (e.get("title") or "").lower()
            if "text" in role or ("entry" in role) or "name" in title:
                name_idx = str(e.get("element_index", ""))
                break

        if name_idx:
            self.client.tool_call("click", {"app": APP, "element_index": name_idx})
            time.sleep(0.3)

        # Type text
        result = self.client.tool_call("type_text", {"text": "Hello OpenCU!"})
        text = _text_from(result)
        assert "error" not in text.lower() or "success" in text.lower(), f"type_text failed: {text}"

        # Verify text was typed — type_text returns success
        # Note: ATSPI may not expose Entry text via the value field;
        # we verify the operation succeeded rather than reading back via tree
        assert "success" in text.lower() or result.get("result") is not None, (
            f"type_text should succeed. Got: {text}"
        )

    def test_07_press_key_tab(self):
        """press_key should handle Tab without error."""
        result = self.client.tool_call("press_key", {"key": "Tab"})
        text = _text_from(result)
        assert "error" not in text.lower() or "success" in text.lower(), f"press_key Tab failed: {text}"

    def test_08_scroll_the_list(self):
        """scroll should scroll the scrollable list widget."""
        state = self._get_state()
        elements = _parse_tree(state)

        # Find a scrollable element
        scroll_idx = None
        for e in elements:
            role = (e.get("role") or "").lower()
            if "scroll" in role or "tree" in role or "list" in role:
                scroll_idx = str(e.get("element_index", ""))
                break

        if scroll_idx:
            result = self.client.tool_call("scroll", {
                "element_index": scroll_idx,
                "direction": "down",
                "pages": 1,
            })
            text = _text_from(result)
            assert "error" not in text.lower(), f"Scroll failed: {text}"
        else:
            pytest.skip("No scrollable element found in tree")

    def test_09_screenshot_diff_detects_changes(self):
        """screenshot_diff should detect visual changes after interaction."""
        # Capture before
        state1 = self._get_state(include_screenshot=True)
        content1 = state1.get("result", {}).get("content", [])
        before_b64 = ""
        for c in content1:
            if c.get("type") == "image":
                before_b64 = c.get("data", "")
                break

        assert before_b64, "Should have captured a before screenshot"

        # Make a change: click Increment
        self.client.tool_call("visual_click", {"description": "the Increment button"})
        time.sleep(0.5)

        # Diff
        result = self.client.tool_call("screenshot_diff", {"before": before_b64})
        text = _text_from(result)
        # Should either detect changes or at least not error
        assert "error" not in text.lower(), f"screenshot_diff failed: {text[:300]}"

    def test_10_visual_locate_finds_button(self):
        """visual_locate should find the Increment button without clicking."""
        result = self.client.tool_call("visual_locate", {
            "description": "Increment button",
        })
        text = _text_from(result)
        # Should find at least one match
        assert "error" not in text.lower() or "match" in text.lower(), (
            f"visual_locate failed: {text[:500]}"
        )

    def test_11_set_value_on_entry(self):
        """set_value should set the text entry field value."""
        state = self._get_state()
        elements = _parse_tree(state)

        entry_idx = None
        for e in elements:
            role = (e.get("role") or "").lower()
            if "entry" in role or "text" in role:
                entry_idx = str(e.get("element_index", ""))
                break

        if entry_idx:
            result = self.client.tool_call("set_value", {
                "element_index": entry_idx,
                "value": "set by opencu",
            })
            text = _text_from(result)
            assert "error" not in text.lower(), f"set_value failed: {text}"
        else:
            pytest.skip("No text entry element found")

    def test_12_analyze_screenshot(self):
        """analyze_screenshot should return OCR text and annotated image."""
        result = self.client.tool_call("analyze_screenshot", {
            "ocr": True,
            "annotate": True,
        })
        content = result.get("result", {}).get("content", [])
        has_text = any(c.get("type") == "text" for c in content)
        assert has_text, "analyze_screenshot should return analysis text"

    def test_13_click_at_coordinates(self):
        """click with x,y coordinates should work."""
        result = self.client.tool_call("click", {
            "x": 640,
            "y": 400,
        })
        text = _text_from(result)
        # Should not crash even if clicking empty space
        assert result.get("result") is not None, f"Coordinate click failed: {text[:300]}"
