from __future__ import annotations

from unittest.mock import MagicMock, patch

from computer_use.backends.input_utils import preserve_clipboard, restore_clipboard


class TestPreserveClipboard:
    def test_returns_none_when_pyperclip_unavailable(self):
        with patch.dict("sys.modules", {"pyperclip": None}):
            result = preserve_clipboard()
            assert result is None

    def test_returns_text_when_pyperclip_available(self):
        mock_pc = MagicMock()
        mock_pc.paste.return_value = "saved text"
        with patch.dict("sys.modules", {"pyperclip": mock_pc}):
            result = preserve_clipboard()
            assert result == "saved text"

    def test_returns_none_on_pyperclip_exception(self):
        mock_pc = MagicMock()
        mock_pc.paste.side_effect = Exception("no clipboard")
        with patch.dict("sys.modules", {"pyperclip": mock_pc}):
            result = preserve_clipboard()
            assert result is None


class TestRestoreClipboard:
    def test_handles_none_gracefully(self):
        restore_clipboard(None)  # should not crash

    def test_restores_text(self):
        mock_pc = MagicMock()
        with patch.dict("sys.modules", {"pyperclip": mock_pc}):
            restore_clipboard("saved")
            mock_pc.copy.assert_called_once_with("saved")

    def test_handles_exception_on_restore(self):
        mock_pc = MagicMock()
        mock_pc.copy.side_effect = Exception("fail")
        with patch.dict("sys.modules", {"pyperclip": mock_pc}):
            restore_clipboard("saved")  # should not crash


class TestClipboardIntegration:
    def test_type_text_preserves_clipboard(self):
        from computer_use.server import handle_request
        mock_pc = MagicMock()
        mock_pc.paste.return_value = "original"
        with patch.dict("sys.modules", {"pyperclip": mock_pc}):
            msg = {"id": 1, "method": "tools/call", "params": {"name": "type_text", "arguments": {"text": "hello"}}}
            handle_request(msg)
            mock_pc.copy.assert_called_with("original")

    def test_set_value_preserves_clipboard(self):
        from computer_use import types
        from computer_use.server import handle_request
        types.ELEMENT_CACHE["5"] = types.CachedElement(
            element=None, frame={"center_x": 100.0, "center_y": 200.0}, app="Test"
        )
        mock_pc = MagicMock()
        mock_pc.paste.return_value = "original"
        with patch.dict("sys.modules", {"pyperclip": mock_pc}):
            msg = {"id": 1, "method": "tools/call",
                   "params": {"name": "set_value", "arguments": {"element_index": "5", "value": "new"}}}
            handle_request(msg)
            mock_pc.copy.assert_called_with("original")
        types.ELEMENT_CACHE.pop("5", None)
