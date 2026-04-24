from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_IS_FAKE = os.environ.get("GSD_CU_BACKEND", "fake") == "fake"
requires_fake = pytest.mark.skipif(not _IS_FAKE, reason="requires fake backend")


@pytest.fixture(autouse=True)
def clean_state():
    from computer_use.types import clear_cache
    clear_cache()
    import computer_use.types as _types
    _types.LAST_SCREENSHOT = b""
    _types.LAST_APP = None
    yield
    clear_cache()
    _types.LAST_SCREENSHOT = b""
    _types.LAST_APP = None


class TestParseDescription:
    def test_simple_tokens(self):
        from computer_use.matcher import parse_description
        parsed = parse_description("Submit button")
        assert "submit" in parsed.tokens
        assert "button" in parsed.tokens
        assert parsed.role_hint == "button"

    def test_quoted_phrase(self):
        from computer_use.matcher import parse_description
        parsed = parse_description('"Save As" button')
        assert "Save As" in parsed.quoted_phrases
        assert parsed.role_hint == "button"

    def test_role_hint_menu(self):
        from computer_use.matcher import parse_description
        parsed = parse_description("File menu")
        assert parsed.role_hint == "menu"

    def test_role_hint_field(self):
        from computer_use.matcher import parse_description
        parsed = parse_description("username text field")
        assert parsed.role_hint == "field"

    def test_empty_description(self):
        from computer_use.matcher import parse_description
        parsed = parse_description("")
        assert parsed.tokens == []
        assert parsed.quoted_phrases == []
        assert parsed.role_hint is None

    def test_whitespace_only(self):
        from computer_use.matcher import parse_description
        parsed = parse_description("   ")
        assert parsed.tokens == []


class TestMatcherScoring:
    def test_role_match_bonus(self):
        from computer_use.matcher import _score_element, parse_description
        parsed = parse_description("Submit button")
        score = _score_element(parsed, "1", "button", "Submit", {"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25})
        assert score >= 30 + 20 + 25 + 10 + 5

    def test_no_role_match(self):
        from computer_use.matcher import _score_element, parse_description
        parsed = parse_description("Submit button")
        score = _score_element(parsed, "1", "link", "Submit", {"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25})
        assert score < 30 + 20 + 25 + 10 + 5

    def test_no_title_overlap(self):
        from computer_use.matcher import _score_element, parse_description
        parsed = parse_description("Submit button")
        score = _score_element(parsed, "1", "button", "Something Else", {"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25})
        assert score >= 30 + 10 + 5

    def test_no_frame_penalty(self):
        from computer_use.matcher import _score_element, parse_description
        parsed = parse_description("Submit button")
        score_with_frame = _score_element(parsed, "1", "button", "Submit", {"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25})
        score_no_frame = _score_element(parsed, "1", "button", "Submit", None)
        assert score_with_frame > score_no_frame

    def test_disabled_penalty(self):
        from computer_use.matcher import _score_element, parse_description
        parsed = parse_description("Submit button")
        score_enabled = _score_element(parsed, "1", "button", "Submit", None, enabled=True)
        score_disabled = _score_element(parsed, "1", "button", "Submit", None, enabled=False)
        assert score_enabled > score_disabled

    def test_quoted_phrase_high_score(self):
        from computer_use.matcher import _score_element, parse_description
        parsed = parse_description('"Save As" button')
        score = _score_element(parsed, "1", "button", "Save As", {"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25})
        assert score >= 30 + 40 + 10 + 5

    def test_ocr_scoring(self):
        from computer_use.matcher import _score_ocr, parse_description
        parsed = parse_description("Submit")
        score = _score_ocr(parsed, "Submit", 0.95)
        assert score >= 20 + 25 + 9

    def test_ocr_scoring_no_match(self):
        from computer_use.matcher import _score_ocr, parse_description
        parsed = parse_description("Submit")
        score = _score_ocr(parsed, "Cancel", 0.95)
        assert score < 20


class TestFindElements:
    def test_find_by_a11y_title(self):
        from computer_use.matcher import find_elements
        elements = [
            {"element_index": "0", "role": "window", "title": "FakeApp"},
            {"element_index": "1", "role": "button", "title": "Submit", "frame": {"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25}},
        ]
        matches = find_elements("Submit button", elements=elements)
        assert len(matches) >= 1
        assert matches[0].element_index == "1"
        assert matches[0].source == "accessibility"

    def test_find_by_ocr(self):
        from computer_use.matcher import find_elements
        ocr_results = [
            {"text": "Submit", "x": 10, "y": 20, "width": 80, "height": 30, "confidence": 0.9},
        ]
        matches = find_elements("Submit", ocr_results=ocr_results, match_strategy="ocr")
        assert len(matches) >= 1
        assert matches[0].source == "ocr"

    def test_combined_prefers_a11y(self):
        from computer_use.matcher import find_elements
        elements = [
            {"element_index": "1", "role": "button", "title": "Submit", "frame": {"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25}},
        ]
        ocr_results = [
            {"text": "Submit", "x": 10, "y": 20, "width": 80, "height": 30, "confidence": 0.9},
        ]
        matches = find_elements("Submit", elements=elements, ocr_results=ocr_results, match_strategy="combined")
        a11y_matches = [m for m in matches if m.source == "accessibility"]
        assert len(a11y_matches) >= 1

    def test_no_matches_returns_empty(self):
        from computer_use.matcher import find_elements
        elements = [
            {"element_index": "1", "role": "button", "title": "Cancel"},
        ]
        matches = find_elements("Submit", elements=elements)
        assert matches == []

    def test_empty_description_returns_empty(self):
        from computer_use.matcher import find_elements
        matches = find_elements("", elements=[{"element_index": "1", "title": "Submit"}])
        assert matches == []

    def test_max_results_limits_output(self):
        from computer_use.matcher import find_elements
        elements = [
            {"element_index": str(i), "role": "button", "title": "Submit", "frame": {"x": float(i * 10), "y": 0.0, "width": 100.0, "height": 50.0, "center_x": float(i * 10 + 50), "center_y": 25.0}}
            for i in range(10)
        ]
        matches = find_elements("Submit button", elements=elements, max_results=3)
        assert len(matches) <= 3

    def test_accessibility_only_strategy(self):
        from computer_use.matcher import find_elements
        ocr_results = [{"text": "Submit", "x": 10, "y": 20, "width": 80, "height": 30, "confidence": 0.9}]
        matches = find_elements("Submit", ocr_results=ocr_results, match_strategy="accessibility")
        assert all(m.source == "accessibility" for m in matches)

    def test_ocr_only_strategy(self):
        from computer_use.matcher import find_elements
        elements = [
            {"element_index": "1", "role": "button", "title": "Submit", "frame": {"x": 0, "y": 0, "width": 100, "height": 50, "center_x": 50, "center_y": 25}},
        ]
        matches = find_elements("Submit", elements=elements, match_strategy="ocr")
        assert all(m.source == "ocr" for m in matches)

    def test_deduplication(self):
        from computer_use.matcher import find_elements
        elements = [
            {"element_index": "1", "role": "button", "title": "Submit", "frame": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0, "center_x": 50.0, "center_y": 25.0}},
        ]
        ocr_results = [
            {"text": "Submit", "x": 0, "y": 0, "width": 100, "height": 50, "confidence": 0.9},
        ]
        matches = find_elements("Submit", elements=elements, ocr_results=ocr_results, match_strategy="combined")
        center_coords = [(round(m.frame["center_x"], 1), round(m.frame["center_y"], 1)) for m in matches if m.frame]
        assert len(center_coords) == len(set(center_coords))


class TestMatchCenter:
    def test_match_center_from_frame(self):
        from computer_use.matcher import ElementMatch, match_center
        match = ElementMatch(
            element_index="1",
            role="button",
            title="Submit",
            frame={"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0, "center_x": 50.0, "center_y": 25.0},
            score=80.0,
            source="accessibility",
        )
        cx, cy = match_center(match)
        assert cx == 50
        assert cy == 25

    def test_match_center_no_frame_raises(self):
        from computer_use.matcher import ElementMatch, match_center
        match = ElementMatch(
            element_index="1",
            role="button",
            title="Submit",
            frame=None,
            score=80.0,
            source="accessibility",
        )
        with pytest.raises(RuntimeError):
            match_center(match)


@requires_fake
class TestVisualClickTool:
    def test_visual_click_finds_and_clicks(self):
        from computer_use.server import handle_request
        handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_app_state", "arguments": {"app": "FakeApp"}},
        })
        resp = handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "visual_click", "arguments": {"description": "Submit button"}},
        })
        assert "result" in resp
        result = resp["result"]
        assert "content" in result
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["clicked"] is True
        assert data["match"]["title"] == "Submit"
        assert data["match"]["source"] == "accessibility"
        assert "x" in data["coordinates"]

    def test_visual_click_with_app(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_click", "arguments": {"description": "Cancel", "app": "FakeApp"}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        assert data["clicked"] is True
        assert data["match"]["title"] == "Cancel"

    def test_visual_click_no_match(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_click", "arguments": {"description": "nonexistent xyzzy"}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        assert "error" in data

    def test_visual_click_empty_description(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_click", "arguments": {"description": ""}},
        })
        assert resp["result"].get("isError") is True or "error" in resp["result"]["content"][0]["text"].lower()

    def test_visual_click_stores_screenshot(self):
        import computer_use.types as _types
        from computer_use.server import handle_request
        assert _types.LAST_SCREENSHOT == b""
        handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_click", "arguments": {"description": "OK button"}},
        })
        assert len(_types.LAST_SCREENSHOT) > 0


@requires_fake
class TestVisualLocateTool:
    def test_visual_locate_returns_matches(self):
        from computer_use.server import handle_request
        handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_app_state", "arguments": {"app": "FakeApp"}},
        })
        resp = handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": "Submit button"}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        assert data["count"] >= 1
        assert data["matches"][0]["title"] == "Submit"

    def test_visual_locate_multiple_matches(self):
        from computer_use.server import handle_request
        handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_app_state", "arguments": {"app": "FakeApp"}},
        })
        resp = handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": "button", "max_results": 5}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        assert data["count"] >= 1

    def test_visual_locate_no_matches(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": "nonexistent xyzzy"}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        assert data["count"] == 0
        assert data["matches"] == []

    def test_visual_locate_with_app(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": "File menu", "app": "FakeApp"}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        assert data["count"] >= 1
        assert data["matches"][0]["title"] == "File"

    def test_visual_locate_max_results(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": "button", "max_results": 2}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        assert data["count"] <= 2

    def test_visual_locate_empty_description(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": ""}},
        })
        assert resp["result"].get("isError") is True or "error" in resp["result"]["content"][0]["text"].lower()


@requires_fake
class TestMatchStrategies:
    def test_accessibility_only(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": "Submit", "match_strategy": "accessibility"}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        if data["count"] > 0:
            assert data["matches"][0]["source"] == "accessibility"

    def test_ocr_only(self):
        from computer_use.server import handle_request
        resp = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": "FakeApp", "match_strategy": "ocr"}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        if data["count"] > 0:
            assert data["matches"][0]["source"] == "ocr"

    def test_combined_strategy(self):
        from computer_use.server import handle_request
        handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_app_state", "arguments": {"app": "FakeApp"}},
        })
        resp = handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "visual_locate", "arguments": {"description": "Submit", "match_strategy": "combined"}},
        })
        result = resp["result"]
        data = json.loads(result["content"][0]["text"])
        assert data["count"] >= 1


class TestToolSchemas:
    def test_tools_list_includes_visual_tools(self):
        from computer_use.server import handle_request
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "visual_click" in tool_names
        assert "visual_locate" in tool_names

    def test_visual_tools_have_schemas(self):
        from computer_use.server import handle_request
        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp["result"]["tools"]
        for tool in tools:
            if tool["name"] in ("visual_click", "visual_locate"):
                assert "inputSchema" in tool
                assert tool["inputSchema"]["type"] == "object"
                assert "description" in tool["inputSchema"]["properties"]
