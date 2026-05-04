from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from open_computer_use.types import ELEMENT_CACHE, CachedElement, clear_cache


@pytest.fixture(autouse=True)
def clean_cache():
    clear_cache()
    yield
    clear_cache()


def _setup_atspi_mock():
    mock_atspi = MagicMock()
    mock_atspi.CoordType.SCREEN = 0
    mock_atspi.StateType.ENABLED = 99
    mock_atspi.StateType.FOCUSED = 100
    mock_atspi.Value.get_value.side_effect = Exception("no value")
    mock_atspi.Value.set_value.side_effect = Exception("no set_value")
    return mock_atspi


def _make_mock_element(role="push button", name="OK", desc="desc",
                       enabled=True, focused=False, x=10, y=20, w=100, h=30,
                       children=None, actions=None):
    el = MagicMock()
    el.get_role_name.return_value = role
    el.get_name.return_value = name
    el.get_description.return_value = desc
    el.get_children.return_value = children or []

    state_mock = MagicMock()
    state_mock.contains.side_effect = lambda s: enabled if s == 99 else focused
    el.get_state_set.return_value = state_mock

    ext = MagicMock()
    ext.x, ext.y, ext.width, ext.height = x, y, w, h
    el.get_extents.return_value = ext

    el._test_actions = actions
    return el


def _build_tree_mocks(elements_at_root, app_name="TestApp"):
    mock_atspi = _setup_atspi_mock()

    mock_window = MagicMock()
    mock_window.get_role_name.return_value = "frame"
    mock_window.get_name.return_value = "Window"
    mock_window.get_description.return_value = None
    mock_window.get_children.return_value = elements_at_root
    mock_window.get_state_set.return_value = MagicMock()
    mock_window.get_state_set.return_value.contains.return_value = False
    ext = MagicMock()
    ext.x, ext.y, ext.width, ext.height = 0, 0, 0, 0
    mock_window.get_extents.return_value = ext

    mock_app = MagicMock()
    mock_app.get_name.return_value = app_name
    mock_app.get_windows.return_value = [mock_window]

    mock_desktop = MagicMock()
    mock_desktop.get_applications.return_value = [mock_app]

    mock_atspi.get_desktop.return_value = mock_desktop
    return mock_atspi


class TestRichAccessibilityTreeMetadata:
    def test_tree_node_includes_frame_data(self):
        from open_computer_use.backends.linux_x11 import _get_accessibility_tree

        button = _make_mock_element(x=10, y=20, w=100, h=30)
        mock_atspi = _build_tree_mocks([button])
        mock_atspi.Action.get_n_actions.return_value = 0

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            result = _get_accessibility_tree("TestApp", 1234, max_elements=10)

        assert result is not None
        window_children = result["children"]
        assert len(window_children) >= 1
        window_node = window_children[0]
        assert "children" in window_node
        button_node = window_node["children"][0]
        assert "frame" in button_node
        frame = button_node["frame"]
        assert frame["x"] == 10
        assert frame["y"] == 20
        assert frame["width"] == 100
        assert frame["height"] == 30
        assert frame["center_x"] == 60
        assert frame["center_y"] == 35

    def test_tree_node_includes_description(self):
        from open_computer_use.backends.linux_x11 import _get_accessibility_tree

        button = _make_mock_element(desc="A helpful button")
        mock_atspi = _build_tree_mocks([button])
        mock_atspi.Action.get_n_actions.return_value = 0

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            result = _get_accessibility_tree("TestApp", 1234, max_elements=10)

        assert result is not None
        button_node = result["children"][0]["children"][0]
        assert button_node.get("description") == "A helpful button"

    def test_tree_node_includes_actions(self):
        from open_computer_use.backends.linux_x11 import _get_accessibility_tree

        button = _make_mock_element(actions=["press", "grab"])
        mock_atspi = _build_tree_mocks([button])
        mock_atspi.Action.get_n_actions.return_value = 2
        mock_atspi.Action.get_action_name.side_effect = lambda el, i: el._test_actions[i]

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            result = _get_accessibility_tree("TestApp", 1234, max_elements=10)

        assert result is not None
        button_node = result["children"][0]["children"][0]
        assert button_node.get("actions") == ["press", "grab"]

    def test_tree_node_omits_empty_fields(self):
        from open_computer_use.backends.linux_x11 import _get_accessibility_tree

        panel = _make_mock_element(role="panel", name="", desc=None, x=0, y=0, w=0, h=0)
        mock_atspi = _build_tree_mocks([panel])
        mock_atspi.Action.get_n_actions.return_value = 0

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            result = _get_accessibility_tree("TestApp", 1234, max_elements=10)

        assert result is not None
        panel_node = result["children"][0]["children"][0]
        assert "title" not in panel_node or panel_node.get("title") in (None, "")
        assert "description" not in panel_node
        assert "actions" not in panel_node

    def test_element_cache_has_frame(self):
        from open_computer_use.backends.linux_x11 import _get_accessibility_tree

        button = _make_mock_element(x=50, y=60, w=200, h=40)
        mock_atspi = _build_tree_mocks([button])
        mock_atspi.Action.get_n_actions.return_value = 0

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            _get_accessibility_tree("TestApp", 1234, max_elements=10)

        button_cached = None
        for _idx, cached in ELEMENT_CACHE.items():
            if cached.role == "push button":
                button_cached = cached
                break
        assert button_cached is not None
        assert button_cached.frame is not None
        assert button_cached.frame["center_x"] == 150


class TestFallbackTreeFrameData:
    def test_fallback_tree_populates_frames_from_xdotool(self):
        from open_computer_use.backends.linux_x11 import _fallback_accessibility_tree

        wmctrl_output = "0x02400003  0 hostname My Window Title\n0x02400004  0 hostname Another Window\n"
        xdotool_output_1 = "X=100\nY=200\nWIDTH=800\nHEIGHT=600\nWINDOW=9437187\n"
        xdotool_output_2 = "X=50\nY=50\nWIDTH=400\nHEIGHT=300\nWINDOW=9437188\n"

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if cmd[0] == "wmctrl" and "-l" in cmd:
                result.stdout = wmctrl_output
            elif cmd[0] == "xdotool" and "getwindowgeometry" in cmd:
                if cmd[-1] == "0x02400003":
                    result.stdout = xdotool_output_1
                else:
                    result.stdout = xdotool_output_2
            return result

        with patch("open_computer_use.backends.linux_x11.subprocess.run", side_effect=mock_run):
            result = _fallback_accessibility_tree("TestApp", 10)

        assert result is not None
        assert "0" in ELEMENT_CACHE
        root_frame = ELEMENT_CACHE["0"].frame
        assert root_frame is not None
        assert root_frame["width"] == 1920

        assert "1" in ELEMENT_CACHE
        frame_1 = ELEMENT_CACHE["1"].frame
        assert frame_1 is not None
        assert frame_1["x"] == 100
        assert frame_1["y"] == 200
        assert frame_1["width"] == 800
        assert frame_1["height"] == 600
        assert frame_1["center_x"] == 500
        assert frame_1["center_y"] == 500

    def test_fallback_tree_handles_missing_xdotool(self):
        from open_computer_use.backends.linux_x11 import _fallback_accessibility_tree

        wmctrl_output = "0x02400003  0 hostname My Window\n"

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "wmctrl":
                result.returncode = 0
                result.stdout = wmctrl_output
            elif cmd[0] == "xdotool":
                result.returncode = 1
                result.stdout = ""
            return result

        with patch("open_computer_use.backends.linux_x11.subprocess.run", side_effect=mock_run):
            result = _fallback_accessibility_tree("TestApp", 10)

        assert result is not None
        assert "1" in ELEMENT_CACHE
        assert ELEMENT_CACHE["1"].frame is None

    def test_fallback_tree_root_has_synthetic_frame_when_wmctrl_works(self):
        from open_computer_use.backends.linux_x11 import _fallback_accessibility_tree

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            return result

        with patch("open_computer_use.backends.linux_x11.subprocess.run", side_effect=mock_run):
            result = _fallback_accessibility_tree("TestApp", 10)

        assert result is not None
        assert ELEMENT_CACHE["0"].frame is not None
        assert ELEMENT_CACHE["0"].frame["width"] == 1920


class TestClickByElementIndex:
    def test_click_tries_atspi_press_action(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        ELEMENT_CACHE["1"] = CachedElement(
            element=MagicMock(),
            frame={"x": 10, "y": 20, "width": 100, "height": 30, "center_x": 60, "center_y": 35},
            app="TestApp", role="push button", title="OK",
        )

        mock_atspi = MagicMock()
        mock_atspi.Action.get_n_actions.return_value = 1
        mock_atspi.Action.get_action_name.return_value = "press"
        mock_atspi.Action.do_action.return_value = True

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            backend = LinuxX11Backend()
            result = backend.click(element_index="1", x=None, y=None)

        assert result["success"] is True
        assert result["method"] == "ATSPI-press"
        assert result["element_index"] == "1"

    def test_click_falls_back_to_mouse_on_no_atspi(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        ELEMENT_CACHE["1"] = CachedElement(
            element=None,
            frame={"x": 10, "y": 20, "width": 100, "height": 30, "center_x": 60, "center_y": 35},
            app="TestApp", role="push button", title="OK",
        )

        mock_pyautogui = MagicMock()
        from open_computer_use.backends import linux_x11
        with patch.object(linux_x11, "require_pyautogui", return_value=mock_pyautogui), \
             patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock()}):
            backend = LinuxX11Backend()
            result = backend.click(element_index="1", x=None, y=None)

        assert result["success"] is True
        assert result["method"] == "mouse"
        assert result["x"] == 60
        assert result["y"] == 35

    def test_click_does_not_use_atspi_for_right_click(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        ELEMENT_CACHE["1"] = CachedElement(
            element=MagicMock(),
            frame={"x": 10, "y": 20, "width": 100, "height": 30, "center_x": 60, "center_y": 35},
            app="TestApp", role="push button", title="OK",
        )

        mock_pyautogui = MagicMock()
        from open_computer_use.backends import linux_x11
        with patch.object(linux_x11, "require_pyautogui", return_value=mock_pyautogui):
            backend = LinuxX11Backend()
            result = backend.click(element_index="1", x=None, y=None, mouse_button="right")

        assert result["success"] is True
        assert result["method"] == "mouse"
        assert result["button"] == "right"


class TestPerformAction:
    def test_perform_action_matches_action_name(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        mock_element = MagicMock()
        ELEMENT_CACHE["1"] = CachedElement(
            element=mock_element, frame=None, app="TestApp", role="button", title="OK",
        )

        mock_atspi = MagicMock()
        mock_atspi.Action.get_n_actions.return_value = 2
        mock_atspi.Action.get_action_name.side_effect = lambda el, i: ["press", "grab"][i]
        mock_atspi.Action.do_action.return_value = True

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            backend = LinuxX11Backend()
            result = backend.perform_action("1", "press")

        assert result["success"] is True
        assert result["action"] == "press"

    def test_perform_action_raises_on_unknown(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        mock_element = MagicMock()
        ELEMENT_CACHE["1"] = CachedElement(
            element=mock_element, frame=None, app="TestApp", role="button", title="OK",
        )

        mock_atspi = MagicMock()
        mock_atspi.Action.get_n_actions.return_value = 1
        mock_atspi.Action.get_action_name.return_value = "grab"

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            backend = LinuxX11Backend()
            with pytest.raises(RuntimeError, match="not found"):
                backend.perform_action("1", "jump")

    def test_perform_action_raises_on_no_element(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        ELEMENT_CACHE["1"] = CachedElement(
            element=None, frame=None, app="TestApp", role="panel", title="Panel",
        )

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock()}):
            backend = LinuxX11Backend()
            with pytest.raises(RuntimeError, match="No ATSPI element"):
                backend.perform_action("1", "press")

    def test_perform_action_prefix_match(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        mock_element = MagicMock()
        ELEMENT_CACHE["1"] = CachedElement(
            element=mock_element, frame=None, app="TestApp", role="button", title="OK",
        )

        mock_atspi = MagicMock()
        mock_atspi.Action.get_n_actions.return_value = 1
        mock_atspi.Action.get_action_name.return_value = "activate"
        mock_atspi.Action.do_action.return_value = True

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            backend = LinuxX11Backend()
            result = backend.perform_action("1", "activ")

        assert result["success"] is True
        assert result["action"] == "activate"

    def test_perform_action_raises_on_no_atspi(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        mock_element = MagicMock()
        ELEMENT_CACHE["1"] = CachedElement(
            element=mock_element, frame=None, app="TestApp", role="button", title="OK",
        )

        gi_mock = MagicMock()
        gi_mock.repository = property(lambda self: (_ for _ in ()).throw(ImportError("no gi")))
        with patch.dict("sys.modules", {"gi": gi_mock}, clear=False):
            backend = LinuxX11Backend()
            with pytest.raises(RuntimeError, match="ATSPI not available"):
                backend.perform_action("1", "press")


class TestSetValue:
    def test_set_value_falls_back_to_click_select_type(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        ELEMENT_CACHE["1"] = CachedElement(
            element=None,
            frame={"x": 10, "y": 20, "width": 200, "height": 30, "center_x": 110, "center_y": 35},
            app="TestApp", role="text", title="Field",
        )

        mock_pyautogui = MagicMock()
        from open_computer_use.backends import linux_x11
        with patch.object(linux_x11, "require_pyautogui", return_value=mock_pyautogui), \
             patch.object(linux_x11, "_press_key_sequence"), \
             patch.object(linux_x11, "_type_literal_text", return_value="keyboard"):
            backend = LinuxX11Backend()
            result = backend.set_value("1", "hello")

        assert result["success"] is True
        assert "click-select" in result["method"]
        mock_pyautogui.click.assert_called_once_with(x=110, y=35)

    def test_set_value_tries_atspi_value_interface(self):
        from open_computer_use.backends.linux_x11 import LinuxX11Backend

        mock_element = MagicMock()
        ELEMENT_CACHE["1"] = CachedElement(
            element=mock_element,
            frame={"x": 10, "y": 20, "width": 200, "height": 30, "center_x": 110, "center_y": 35},
            app="TestApp", role="slider", title="Volume",
        )

        mock_atspi = MagicMock()
        mock_atspi.Value.set_value.return_value = True

        with patch.dict("sys.modules", {"gi": MagicMock(), "gi.repository": MagicMock(Atspi=mock_atspi)}):
            backend = LinuxX11Backend()
            result = backend.set_value("1", "50")

        assert result["success"] is True
        assert result["method"] == "ATSPI-Value"


class TestListApps:
    def test_list_apps_with_installed(self):
        from open_computer_use.backends import linux_x11
        from open_computer_use.backends.linux_x11 import LinuxX11Backend
        with patch.object(linux_x11, "_installed_linux_apps", return_value=[
            {"name": "Test App", "running": False, "source": "desktop-file"},
        ]), patch.object(linux_x11, "_list_apps", return_value=[
            {"name": "RunningApp", "running": True, "source": "wmctrl"},
        ]):
            backend = LinuxX11Backend()
            result = backend.list_apps(include_installed=True)

        names = [a["name"] for a in result]
        assert "Test App" in names
        assert "RunningApp" in names
        test_app = next(a for a in result if a["name"] == "Test App")
        assert test_app.get("running") is False

    def test_list_apps_without_installed(self):
        from open_computer_use.backends import linux_x11
        from open_computer_use.backends.linux_x11 import LinuxX11Backend
        with patch.object(linux_x11, "_list_apps", return_value=[
            {"name": "RunningApp", "running": True, "source": "wmctrl"},
        ]):
            backend = LinuxX11Backend()
            result = backend.list_apps()

        assert len(result) == 1
        assert result[0]["name"] == "RunningApp"


class TestMergeAppLists:
    def test_merge_deduplicates_by_name(self):
        from open_computer_use.backends.linux_x11 import _merge_app_lists

        running = [{"name": "Firefox", "pid": 1234, "running": True, "source": "wmctrl"}]
        installed = [{"name": "Firefox", "running": False, "source": "desktop-file"}]

        result = _merge_app_lists(running, installed)
        firefox_entries = [a for a in result if a["name"] == "Firefox"]
        assert len(firefox_entries) == 1
        assert firefox_entries[0]["running"] is True
        assert firefox_entries[0]["pid"] == 1234

    def test_merge_sorts_running_first(self):
        from open_computer_use.backends.linux_x11 import _merge_app_lists

        running = [{"name": "zsh", "running": True, "source": "ps"}]
        installed = [
            {"name": "AppA", "running": False, "source": "desktop-file"},
            {"name": "AppB", "running": False, "source": "desktop-file"},
        ]

        result = _merge_app_lists(running, installed)
        assert result[0]["name"] == "zsh"
        assert result[0]["running"] is True
