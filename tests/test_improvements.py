from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from computer_use.server import handle_request
from computer_use.types import clear_cache

_IS_FAKE = os.environ.get("GSD_CU_BACKEND", "fake") == "fake"
requires_fake = pytest.mark.skipif(not _IS_FAKE, reason="requires fake backend")


@pytest.fixture(autouse=True)
def clean_cache():
    import computer_use.server as srv

    clear_cache()
    srv.backend = None
    yield
    clear_cache()
    srv.backend = None


class TestToolScrollMissingElementIndex:
    def test_scroll_missing_element_index_raises_runtime_error(self):
        from computer_use.server import _tool_scroll

        with pytest.raises(RuntimeError, match="element_index.*required"):
            _tool_scroll({}, MagicMock())


class TestToolScrollMissingDirection:
    def test_scroll_missing_direction_raises_key_error(self):
        from computer_use.server import _tool_scroll

        with pytest.raises(KeyError, match="direction"):
            _tool_scroll({"element_index": "0"}, MagicMock())


class TestSaveTreeSnapshotNoneTree:
    def test_none_tree_returns_early_no_file(self, tmp_path, monkeypatch):
        from computer_use.server import _save_tree_snapshot

        monkeypatch.setenv("GSD_CU_SNAPSHOT_TREES", "1")
        monkeypatch.chdir(tmp_path)
        _save_tree_snapshot(None)
        artifacts = tmp_path / "artifacts" / "trees"
        assert not artifacts.exists()


class TestSaveFailureBundleDisabled:
    def test_disabled_returns_none(self):
        from computer_use.server import _save_failure_bundle

        result = _save_failure_bundle("err", 1, "click", {})
        assert result is None


class TestFallbackAccessibilityTreeWmctrlFails:
    def test_wmctrl_fails_returns_minimal_tree(self):
        from computer_use.backends.linux_x11 import _fallback_accessibility_tree

        with patch("computer_use.backends.linux_x11._run", return_value=(-1, "", "")):
            tree = _fallback_accessibility_tree("TestApp", 10)
        assert tree["element_index"] == "0"
        assert tree["role"] == "window"
        assert tree["title"] == "TestApp"
        assert tree["children"] == []


class TestFindRunningAppEmptyString:
    def test_empty_string_returns_none(self):
        from computer_use.backends.linux_x11 import _find_running_app

        with patch("computer_use.backends.linux_x11._list_apps", return_value=[]):
            result = _find_running_app("")
        assert result is None


class TestListAppsAllSubprocessFail:
    def test_all_calls_fail_returns_empty(self):
        from computer_use.backends.linux_x11 import _list_apps

        with patch("computer_use.backends.linux_x11._run", return_value=(-1, "", "")):
            result = _list_apps()
        assert result == []


class TestActivateAppEmptyWindows:
    def test_empty_windows_returns_none(self):
        from computer_use.backends.linux_x11 import _activate_app

        result = _activate_app([])
        assert result is None


class TestHandleRequestInitializedNotification:
    def test_initialized_notification_no_id_returns_none(self):
        result = handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert result is None


class TestHandleRequestCancelledNotification:
    def test_cancelled_notification_no_id_returns_none(self):
        result = handle_request({"jsonrpc": "2.0", "method": "notifications/cancelled"})
        assert result is None
