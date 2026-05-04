from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_computer_use.backends.fake import FakeBackend
from open_computer_use.server import handle_request
from open_computer_use.types import (
    INTERACTIVE_ROLES,
    ELEMENT_CACHE,
    clear_cache,
    count_tree_nodes,
    filter_tree,
    generate_role_summary,
    is_visible,
)


@pytest.fixture(autouse=True)
def clean_cache():
    import open_computer_use.server as srv

    clear_cache()
    srv.backend = None
    yield
    clear_cache()
    srv.backend = None


def _get_tree(max_elements: int = 20) -> dict:
    be = FakeBackend()
    return be.get_accessibility_tree("TestApp", 123, max_elements=max_elements)


class TestPathGeneration:
    def test_root_has_path(self):
        tree = _get_tree()
        assert "path" in tree
        assert tree["path"] == "window"

    def test_children_have_path(self):
        tree = _get_tree()
        for child in tree["children"]:
            assert "path" in child
            assert child["path"].startswith("window/")

    def test_path_contains_role(self):
        tree = _get_tree()
        for child in tree["children"]:
            role = child["role"]
            assert role in child["path"]

    def test_path_is_slash_separated(self):
        tree = _get_tree()
        for child in tree["children"]:
            parts = child["path"].split("/")
            assert len(parts) == 2
            assert parts[0] == "window"


class TestFilterInteractive:
    def test_interactive_filter_removes_non_interactive(self):
        tree = _get_tree()
        filtered = filter_tree(tree, "interactive")
        assert filtered is not None

        def collect_roles(node):
            roles = [node.get("role")]
            for c in node.get("children", []):
                roles.extend(collect_roles(c))
            return roles

        roles = collect_roles(filtered)
        for role in roles:
            if role:
                assert role.lower() in INTERACTIVE_ROLES or role == "window"

    def test_interactive_filter_keeps_buttons(self):
        tree = _get_tree()
        filtered = filter_tree(tree, "interactive")

        def find_roles(node):
            roles = [node.get("role")]
            for c in node.get("children", []):
                roles.extend(find_roles(c))
            return roles

        roles = find_roles(filtered)
        assert "button" in roles

    def test_interactive_filter_keeps_textfields(self):
        tree = _get_tree()
        filtered = filter_tree(tree, "interactive")

        def find_roles(node):
            roles = [node.get("role")]
            for c in node.get("children", []):
                roles.extend(find_roles(c))
            return roles

        roles = find_roles(filtered)
        assert "textfield" in roles

    def test_interactive_filter_keeps_checkboxes(self):
        tree = _get_tree()
        filtered = filter_tree(tree, "interactive")

        def find_roles(node):
            roles = [node.get("role")]
            for c in node.get("children", []):
                roles.extend(find_roles(c))
            return roles

        roles = find_roles(filtered)
        assert "checkbox" in roles

    def test_interactive_filter_preserves_root(self):
        tree = _get_tree()
        filtered = filter_tree(tree, "interactive")
        assert filtered["role"] == "window"

    def test_non_interactive_leaf_roles_excluded(self):
        tree = _get_tree()
        filtered = filter_tree(tree, "interactive")

        def find_roles(node):
            roles = [node.get("role")]
            for c in node.get("children", []):
                roles.extend(find_roles(c))
            return roles

        roles = [r.lower() for r in find_roles(filtered) if r]
        for r in roles:
            if r != "window":
                assert r in INTERACTIVE_ROLES

    def test_filter_none_returns_full_tree(self):
        tree = _get_tree()
        result = filter_tree(tree, "")
        assert result is tree

    def test_filter_via_server(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_app_state",
                "arguments": {"app": "TestApp", "include_screenshot": False, "filter": "interactive"},
            },
        })
        content = resp["result"]["content"]
        text = content[0]["text"]
        data = json.loads(text)
        tree = data["accessibility_tree"]

        def find_roles(node):
            roles = [node.get("role")]
            for c in node.get("children", []):
                roles.extend(find_roles(c))
            return roles

        roles = [r.lower() for r in find_roles(tree) if r]
        for r in roles:
            if r != "window":
                assert r in INTERACTIVE_ROLES


class TestFilterText:
    def test_text_filter_keeps_elements_with_title(self):
        tree = _get_tree()
        filtered = filter_tree(tree, "text")
        assert filtered is not None

        def all_have_text(node):
            has_text = bool(node.get("title") or node.get("value") or node.get("text"))
            children_ok = all(all_have_text(c) for c in node.get("children", []))
            return has_text or children_ok

        assert all_have_text(filtered)

    def test_text_filter_preserves_root(self):
        tree = _get_tree()
        filtered = filter_tree(tree, "text")
        assert filtered["role"] == "window"

    def test_filter_via_server_text(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_app_state",
                "arguments": {"app": "TestApp", "include_screenshot": False, "filter": "text"},
            },
        })
        content = resp["result"]["content"]
        text = content[0]["text"]
        data = json.loads(text)
        tree = data["accessibility_tree"]
        assert tree["role"] == "window"
        assert len(tree.get("children", [])) > 0


class TestMaxElementsTruncation:
    def test_truncation_when_exceeded(self):
        tree = _get_tree(max_elements=5)
        assert tree.get("_truncated") is True
        assert tree.get("_total_elements") == 17

    def test_no_truncation_when_under_limit(self):
        tree = _get_tree(max_elements=20)
        assert "_truncated" not in tree

    def test_truncated_tree_has_fewer_children(self):
        tree = _get_tree(max_elements=5)
        assert len(tree["children"]) == 4

    def test_truncation_via_server(self):
        resp = handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_app_state",
                "arguments": {"app": "TestApp", "include_screenshot": False, "max_elements": 5},
            },
        })
        content = resp["result"]["content"]
        text = content[0]["text"]
        data = json.loads(text)
        tree = data["accessibility_tree"]
        assert tree.get("_truncated") is True


class TestRoleSummary:
    def test_button_summary(self):
        assert generate_role_summary("button", "Submit") == "Button: Submit"

    def test_textfield_summary(self):
        assert generate_role_summary("textfield", "Username") == "Text Field []"

    def test_textfield_with_value(self):
        assert generate_role_summary("textfield", "Username", value="john") == "Text Field [john]"

    def test_checkbox_unchecked(self):
        assert generate_role_summary("checkbox", "Remember", checked=False) == "Checkbox [unchecked]"

    def test_checkbox_checked(self):
        assert generate_role_summary("checkbox", "Remember", checked=True) == "Checkbox [checked]"

    def test_menuitem_summary(self):
        assert generate_role_summary("menuitem", "New File") == "Menu Item: New File"

    def test_unknown_role(self):
        assert generate_role_summary("panel", "Stuff") == "panel"

    def test_none_role(self):
        assert generate_role_summary(None, "Stuff") == ""

    def test_role_summary_in_tree(self):
        tree = _get_tree()
        for child in tree["children"]:
            assert "role_summary" in child
            if child["role"] == "button":
                assert child["role_summary"].startswith("Button: ")
            elif child["role"] == "textfield":
                assert "Text Field" in child["role_summary"]
            elif child["role"] == "checkbox":
                assert "Checkbox" in child["role_summary"]

    def test_root_has_role_summary(self):
        tree = _get_tree()
        assert "role_summary" in tree


class TestVisibility:
    def test_all_fake_elements_visible(self):
        tree = _get_tree()
        assert tree.get("visible") is True
        for child in tree["children"]:
            assert child.get("visible") is True

    def test_visible_field_present_on_all_nodes(self):
        tree = _get_tree()
        assert "visible" in tree
        for child in tree["children"]:
            assert "visible" in child

    def test_is_visible_offscreen(self):
        assert is_visible({"x": 2000, "y": 0, "width": 100, "height": 50}, 1920, 1080) is False

    def test_is_visible_zero_size(self):
        assert is_visible({"x": 100, "y": 100, "width": 0, "height": 0}, 1920, 1080) is False

    def test_is_visible_none_frame(self):
        assert is_visible(None, 1920, 1080) is False

    def test_is_visible_onscreen(self):
        assert is_visible({"x": 100, "y": 100, "width": 200, "height": 50}, 1920, 1080) is True


class TestCountTreeNodes:
    def test_count_single_node(self):
        assert count_tree_nodes({"role": "window"}) == 1

    def test_count_with_children(self):
        tree = {"role": "window", "children": [{"role": "button"}, {"role": "button"}]}
        assert count_tree_nodes(tree) == 3

    def test_count_nested(self):
        tree = {
            "role": "window",
            "children": [
                {"role": "group", "children": [{"role": "button"}, {"role": "button"}]},
                {"role": "button"},
            ],
        }
        assert count_tree_nodes(tree) == 5


class TestBackwardCompatibility:
    def test_existing_test_get_accessibility_tree_still_works(self):
        be = FakeBackend()
        tree = be.get_accessibility_tree("TestApp", 123, max_elements=10)
        assert tree is not None
        assert tree["role"] == "window"
        assert len(tree["children"]) == 9

    def test_tree_has_traditional_fields(self):
        tree = _get_tree()
        assert "element_index" in tree
        assert "role" in tree
        assert "title" in tree
        assert "children" in tree
        for child in tree["children"]:
            assert "element_index" in child
            assert "role" in child
            assert "title" in child
