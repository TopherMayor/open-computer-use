from __future__ import annotations

import base64
import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_png(width: int = 100, height: int = 100, color: tuple = (128, 128, 128)) -> bytes:
    from PIL import Image
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_png_b64(width: int = 100, height: int = 100, color: tuple = (128, 128, 128)) -> str:
    return base64.b64encode(_make_png(width, height, color)).decode("ascii")


@pytest.fixture(autouse=True)
def clean_state():
    from computer_use.types import clear_cache
    clear_cache()
    import computer_use.types as _types
    _types.LAST_SCREENSHOT = b""
    yield
    clear_cache()
    _types.LAST_SCREENSHOT = b""


class TestOCRExtract:
    def test_ocr_with_mock_tesseract(self):
        from computer_use.vision import ocr_extract
        img_bytes = _make_png()

        mock_ts = MagicMock()
        mock_ts.Output.DICT = "dict"
        mock_data = {
            "text": ["Hello", "", "World"],
            "left": [10, 0, 10],
            "top": [20, 0, 40],
            "width": [50, 0, 50],
            "height": [15, 0, 15],
            "conf": [95, -1, 88],
        }
        mock_ts.image_to_data.return_value = mock_data
        with patch.dict("sys.modules", {"pytesseract": mock_ts}):
            import importlib
            import computer_use.vision as vis
            importlib.reload(vis)
            results = vis.ocr_extract(img_bytes)

        importlib.reload(vis)
        assert len(results) == 2
        assert results[0]["text"] == "Hello"
        assert results[0]["x"] == 10
        assert results[0]["confidence"] == 0.95
        assert results[1]["text"] == "World"
        assert results[1]["confidence"] == 0.88

    def test_ocr_import_error_returns_empty(self):
        from computer_use.vision import ocr_extract
        img_bytes = _make_png()
        with patch.dict("sys.modules", {"pytesseract": None}):
            import importlib
            import computer_use.vision
            importlib.reload(computer_use.vision)
            result = computer_use.vision.ocr_extract(img_bytes)
        assert result == []
        importlib.reload(computer_use.vision)

    def test_ocr_exception_returns_empty(self):
        from computer_use.vision import ocr_extract
        with patch("computer_use.vision.pytesseract", side_effect=Exception("boom"), create=True):
            with patch("computer_use.vision.ocr_extract", wraps=None) as mock_ocr:
                pass
        with patch("PIL.Image.open", side_effect=Exception("bad image")):
            result = ocr_extract(b"not an image")
        assert result == []


class TestAnnotateScreenshot:
    def test_annotate_draws_boxes(self):
        from computer_use.vision import annotate_screenshot
        from PIL import Image

        img_bytes = _make_png(200, 200, (255, 255, 255))
        elements = [
            {"index": "0", "role": "button", "label": "Click Me", "frame": {"x": 10, "y": 10, "width": 80, "height": 30}},
            {"index": "1", "role": "text", "label": "Hello", "frame": {"x": 100, "y": 50, "width": 60, "height": 20}},
        ]
        result = annotate_screenshot(img_bytes, elements)
        assert isinstance(result, bytes)
        assert len(result) > 0
        result_img = Image.open(io.BytesIO(result))
        assert result_img.size == (200, 200)

    def test_annotate_empty_elements_returns_image(self):
        from computer_use.vision import annotate_screenshot
        img_bytes = _make_png(100, 100)
        result = annotate_screenshot(img_bytes, [])
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_annotate_color_coding_by_role(self):
        from computer_use.vision import annotate_screenshot
        from PIL import Image

        img_bytes = _make_png(300, 300, (255, 255, 255))
        elements = [
            {"index": "0", "role": "button", "frame": {"x": 5, "y": 5, "width": 60, "height": 30}},
            {"index": "1", "role": "text", "frame": {"x": 80, "y": 5, "width": 60, "height": 30}},
            {"index": "2", "role": "input", "frame": {"x": 155, "y": 5, "width": 60, "height": 30}},
        ]
        result = annotate_screenshot(img_bytes, elements)
        assert isinstance(result, bytes)

    def test_annotate_skips_elements_without_frame(self):
        from computer_use.vision import annotate_screenshot
        img_bytes = _make_png(100, 100)
        elements = [
            {"index": "0", "role": "button", "label": "No Frame"},
            {"index": "1", "role": "text", "label": "With Frame", "frame": {"x": 10, "y": 10, "width": 50, "height": 20}},
        ]
        result = annotate_screenshot(img_bytes, elements)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_annotate_skips_zero_size_elements(self):
        from computer_use.vision import annotate_screenshot
        img_bytes = _make_png(100, 100)
        elements = [
            {"index": "0", "role": "button", "frame": {"x": 10, "y": 10, "width": 0, "height": 0}},
        ]
        result = annotate_screenshot(img_bytes, elements)
        assert isinstance(result, bytes)


class TestDiffScreenshots:
    def test_identical_images_no_change(self):
        from computer_use.vision import diff_screenshots
        img = _make_png(100, 100, (128, 128, 128))
        result = diff_screenshots(img, img)
        assert result["changed"] is False
        assert result["regions"] == []

    def test_different_images_detects_change(self):
        from computer_use.vision import diff_screenshots
        before = _make_png(100, 100, (0, 0, 0))
        after = _make_png(100, 100, (255, 255, 255))
        result = diff_screenshots(before, after)
        assert result["changed"] is True
        assert len(result["regions"]) > 0
        assert result["diff_image"] != b""

    def test_small_change_below_threshold(self):
        from computer_use.vision import diff_screenshots
        from PIL import Image
        import numpy as np

        before_arr = np.full((100, 100, 3), 128, dtype=np.uint8)
        after_arr = before_arr.copy()
        after_arr[0, 0] = [130, 130, 130]

        before_img = Image.fromarray(before_arr)
        after_img = Image.fromarray(after_arr)
        before_buf = io.BytesIO()
        after_buf = io.BytesIO()
        before_img.save(before_buf, format="PNG")
        after_img.save(after_buf, format="PNG")

        result = diff_screenshots(before_buf.getvalue(), after_buf.getvalue(), threshold=5.0)
        assert result["changed"] is False

    def test_diff_returns_diff_image(self):
        from computer_use.vision import diff_screenshots
        before = _make_png(100, 100, (0, 0, 0))
        after = _make_png(100, 100, (255, 0, 0))
        result = diff_screenshots(before, after)
        assert result["diff_image"] != b""
        from PIL import Image
        diff_img = Image.open(io.BytesIO(result["diff_image"]))
        assert diff_img.size == (100, 100)

    def test_diff_different_sizes_resizes(self):
        from computer_use.vision import diff_screenshots
        before = _make_png(100, 100)
        after = _make_png(200, 200)
        result = diff_screenshots(before, after)
        assert isinstance(result, dict)
        assert "changed" in result

    def test_diff_regions_have_coordinates(self):
        from computer_use.vision import diff_screenshots
        before = _make_png(200, 200, (0, 0, 0))
        after = _make_png(200, 200, (255, 255, 255))
        result = diff_screenshots(before, after)
        for region in result["regions"]:
            assert "x" in region
            assert "y" in region
            assert "width" in region
            assert "height" in region
            assert "percentage" in region


class TestDescribeElements:
    def test_empty_elements(self):
        from computer_use.vision import describe_elements
        result = describe_elements([])
        assert "No UI elements" in result

    def test_single_element(self):
        from computer_use.vision import describe_elements
        elements = [{"role": "button", "label": "OK"}]
        result = describe_elements(elements)
        assert "button" in result
        assert "OK" in result

    def test_multiple_roles(self):
        from computer_use.vision import describe_elements
        elements = [
            {"role": "button", "label": "Save"},
            {"role": "button", "label": "Cancel"},
            {"role": "text", "label": "Name"},
            {"role": "input", "title": "Email field"},
        ]
        result = describe_elements(elements)
        assert "button" in result
        assert "text" in result
        assert "input" in result

    def test_elements_without_labels(self):
        from computer_use.vision import describe_elements
        elements = [{"role": "window"}]
        result = describe_elements(elements)
        assert "window" in result

    def test_many_elements_truncates_labels(self):
        from computer_use.vision import describe_elements
        elements = [{"role": "button", "label": f"Btn{i}"} for i in range(25)]
        result = describe_elements(elements)
        assert "button" in result


class TestRoleColors:
    def test_known_role(self):
        from computer_use.vision import _role_color
        color = _role_color("button")
        assert color == (66, 133, 244)

    def test_unknown_role(self):
        from computer_use.vision import _role_color
        color = _role_color("foobar")
        assert color == (33, 33, 33)

    def test_none_role(self):
        from computer_use.vision import _role_color
        color = _role_color(None)
        assert color == (33, 33, 33)

    def test_case_insensitive(self):
        from computer_use.vision import _role_color
        assert _role_color("Button") == _role_color("button")


class TestLastScreenshot:
    def test_last_screenshot_stored_after_get_app_state(self):
        import computer_use.types as _types
        from computer_use.server import handle_request

        assert _types.LAST_SCREENSHOT == b""

        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_app_state", "arguments": {"app": "TestApp"}},
        })
        assert resp["result"]["content"][0]["type"] == "text"
        assert len(_types.LAST_SCREENSHOT) > 0


class TestAnalyzeScreenshotTool:
    def test_analyze_screenshot_returns_data(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "analyze_screenshot", "arguments": {}},
        })
        content = resp["result"]["content"]
        text_items = [c for c in content if c.get("type") == "text"]
        image_items = [c for c in content if c.get("type") == "image"]
        assert len(text_items) == 1
        assert len(image_items) == 1
        import json
        data = json.loads(text_items[0]["text"])
        assert "screen_size" in data

    def test_analyze_screenshot_with_app(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "analyze_screenshot", "arguments": {"app": "FakeApp"}},
        })
        content = resp["result"]["content"]
        text_items = [c for c in content if c.get("type") == "text"]
        import json
        data = json.loads(text_items[0]["text"])
        assert "app" in data
        assert "elements" in data

    def test_analyze_screenshot_ocr_disabled(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "analyze_screenshot", "arguments": {"ocr": False}},
        })
        content = resp["result"]["content"]
        text_items = [c for c in content if c.get("type") == "text"]
        import json
        data = json.loads(text_items[0]["text"])
        assert "ocr" not in data


class TestScreenshotDiffTool:
    def test_screenshot_diff_identical_images(self):
        b64 = _make_png_b64(100, 100, (128, 128, 128))
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "screenshot_diff", "arguments": {"before": b64, "after": b64}},
        })
        content = resp["result"]["content"]
        text_items = [c for c in content if c.get("type") == "text"]
        import json
        data = json.loads(text_items[0]["text"])
        assert data["changed"] is False

    def test_screenshot_diff_different_images(self):
        before_b64 = _make_png_b64(100, 100, (0, 0, 0))
        after_b64 = _make_png_b64(100, 100, (255, 255, 255))
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "screenshot_diff", "arguments": {"before": before_b64, "after": after_b64}},
        })
        content = resp["result"]["content"]
        text_items = [c for c in content if c.get("type") == "text"]
        import json
        data = json.loads(text_items[0]["text"])
        assert data["changed"] is True
        assert len(data["regions"]) > 0

    def test_screenshot_diff_missing_before(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "screenshot_diff", "arguments": {}},
        })
        assert resp["result"]["isError"] is True

    def test_screenshot_diff_captures_current_if_no_after(self):
        before_b64 = _make_png_b64(100, 100, (0, 0, 0))
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "screenshot_diff", "arguments": {"before": before_b64}},
        })
        content = resp["result"]["content"]
        text_items = [c for c in content if c.get("type") == "text"]
        assert len(text_items) >= 1


class TestMCPContractVision:
    def test_tools_list_includes_vision_tools(self):
        from computer_use.server import handle_request
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "analyze_screenshot" in tool_names
        assert "screenshot_diff" in tool_names

    def test_vision_tools_have_schemas(self):
        from computer_use.server import handle_request
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp["result"]["tools"]
        for tool in tools:
            if tool["name"] in ("analyze_screenshot", "screenshot_diff"):
                assert "inputSchema" in tool
                assert tool["inputSchema"]["type"] == "object"


class TestFakeBackendVision:
    def test_fake_ocr_returns_stub(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.ocr_extract(b"fake image")
        assert len(result) == 1
        assert result[0]["text"] == "FakeApp"
        assert result[0]["confidence"] == 0.95

    def test_fake_annotate_passthrough(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        data = b"fake image data"
        result = be.annotate_screenshot(data, [])
        assert result == data

    def test_fake_diff_returns_no_change(self):
        from computer_use.backends.fake import FakeBackend
        be = FakeBackend()
        result = be.diff_screenshots(b"before", b"after")
        assert result["changed"] is False
