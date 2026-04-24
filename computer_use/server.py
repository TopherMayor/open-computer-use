from __future__ import annotations

import json
import os
import platform
import time
import traceback
from collections.abc import Callable
from typing import Any

from . import SERVER_NAME, SERVER_VERSION, __version__
from . import audit as _audit
from . import safety as _safety
from . import types as _types
from .backends.input_utils import preserve_clipboard, restore_clipboard

PROTOCOL_VERSION = "2024-11-05"


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def ok_text(data: Any) -> dict[str, Any]:
    text = data if isinstance(data, str) else pretty_json(data)
    return {"content": [{"type": "text", "text": text}]}


def ok_content(content: list[dict[str, Any]]) -> dict[str, Any]:
    return {"content": content}


def error_result(message: str, details: Any | None = None) -> dict[str, Any]:
    payload = {"error": message}
    if details is not None:
        payload["details"] = details
    return {"isError": True, "content": [{"type": "text", "text": pretty_json(payload)}]}


def get_backend() -> Any:
    backend_name = os.environ.get("GSD_CU_BACKEND")
    if backend_name is None:
        if platform.system() == "Darwin":
            backend_name = "macos"
        else:
            backend_name = "linux-x11" if os.environ.get("DISPLAY") else "fake"

    if backend_name == "fake":
        from .backends.fake import create_backend
        return create_backend()
    elif backend_name == "macos":
        try:
            from .backends.macos import create_backend
            return create_backend()
        except Exception:
            pass
    elif backend_name == "linux-x11":
        try:
            from .backends.linux_x11 import create_backend
            return create_backend()
        except Exception:
            pass

    from .backends.fake import create_backend
    return create_backend()


backend: Any = None
_audit.configure(os.environ.get("GSD_CU_AUDIT_LOG"))
_safety.configure_safety(
    max_actions=int(os.environ.get("GSD_CU_MAX_ACTIONS", "0")),
    max_per_minute=int(os.environ.get("GSD_CU_MAX_PER_MINUTE", "0")),
)


def _tool_get_app_state(args: dict[str, Any], be: Any) -> dict[str, Any]:
    app_name = args.get("app")
    if not app_name:
        raise RuntimeError("'app' is required")
    max_depth = int(args.get("max_depth", 7))
    max_elements = int(args.get("max_elements", 220))
    include_screenshot = args.get("include_screenshot", True)
    annotate = args.get("annotate_screenshot", False)

    app_info = be.activate_or_launch_app(app_name)
    pid = app_info.get("pid", 0)

    tree = be.get_accessibility_tree(app_name, pid, max_depth=max_depth, max_elements=max_elements)
    _save_tree_snapshot(tree)
    _types.LAST_APP = app_name

    content: list[dict[str, Any]] = [
        {"type": "text", "text": pretty_json({"app": app_info, "accessibility_tree": tree})}
    ]
    if include_screenshot:
        b64, w, h, method = be.capture_screenshot()
        import base64
        screenshot_bytes = base64.b64decode(b64)
        _types.LAST_SCREENSHOT = screenshot_bytes

        if annotate:
            elements = _tree_to_elements(tree)
            try:
                from .vision import annotate_screenshot as _annotate
                annotated_bytes = _annotate(screenshot_bytes, elements)
                annotated_b64 = base64.b64encode(annotated_bytes).decode("ascii")
                content.append({"type": "image", "data": annotated_b64, "mimeType": "image/png"})
            except Exception:
                content.append({"type": "image", "data": b64, "mimeType": "image/png"})
        else:
            content.append({"type": "image", "data": b64, "mimeType": "image/png"})
    return {"content": content}


def _tool_list_apps(args: dict[str, Any], be: Any) -> dict[str, Any]:
    return {"apps": be.list_apps(
        include_recent=args.get("include_recent", True),
        recent_days=int(args.get("recent_days", 14)),
        include_installed=args.get("include_installed", False),
    )}


def _tool_click(args: dict[str, Any], be: Any) -> dict[str, Any]:
    element_index = args.get("element_index")
    x = args.get("x")
    y = args.get("y")
    return be.click(
        element_index=str(element_index) if element_index is not None else None,
        x=int(x) if x is not None else None,
        y=int(y) if y is not None else None,
        mouse_button=args.get("mouse_button", "left"),
        click_count=int(args.get("click_count", 1)),
    )


def _tool_drag(args: dict[str, Any], be: Any) -> dict[str, Any]:
    return be.drag(
        int(args["from_x"]),
        int(args["from_y"]),
        int(args["to_x"]),
        int(args["to_y"]),
        duration=float(args.get("duration", 0.35)),
    )


def _tool_press_key(args: dict[str, Any], be: Any) -> dict[str, Any]:
    return be.press_key(args["key"])


def _tool_type_text(args: dict[str, Any], be: Any) -> dict[str, Any]:
    saved = preserve_clipboard()
    try:
        return be.type_text(args["text"])
    finally:
        restore_clipboard(saved)


def _tool_scroll(args: dict[str, Any], be: Any) -> dict[str, Any]:
    element_index = args.get("element_index")
    if not element_index:
        raise RuntimeError("'element_index' is required for scroll")
    return be.scroll(
        element_index,
        args["direction"],
        float(args.get("pages", 1)),
    )


def _tool_set_value(args: dict[str, Any], be: Any) -> dict[str, Any]:
    saved = preserve_clipboard()
    try:
        return be.set_value(args["element_index"], args["value"])
    finally:
        restore_clipboard(saved)


def _tool_perform_secondary_action(args: dict[str, Any], be: Any) -> dict[str, Any]:
    return be.perform_action(args["element_index"], args["action"])


def _tree_to_elements(tree: dict[str, Any] | None) -> list[dict[str, Any]]:
    elements = []
    if not tree:
        return elements

    def walk(node: dict[str, Any]) -> None:
        frame = node.get("frame")
        entry: dict[str, Any] = {
            "index": node.get("element_index", ""),
            "role": node.get("role"),
            "label": node.get("title"),
        }
        if frame:
            entry["frame"] = frame
        elements.append(entry)
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return elements


def _tool_analyze_screenshot(args: dict[str, Any], be: Any) -> dict[str, Any]:
    import base64

    from . import vision

    do_ocr = args.get("ocr", True)
    do_annotate = args.get("annotate", True)
    app_name = args.get("app")

    if app_name:
        app_info = be.activate_or_launch_app(app_name)
        pid = app_info.get("pid", 0)
        tree = be.get_accessibility_tree(app_name, pid)
        _types.LAST_APP = app_name
    else:
        tree = None
        app_info = None

    b64, w, h, method = be.capture_screenshot()
    screenshot_bytes = base64.b64decode(b64)
    _types.LAST_SCREENSHOT = screenshot_bytes

    result_data: dict[str, Any] = {
        "screen_size": {"width": w, "height": h},
        "capture_method": method,
    }

    if app_info:
        result_data["app"] = app_info

    if do_ocr:
        ocr_results = vision.ocr_extract(screenshot_bytes)
        result_data["ocr"] = ocr_results

    elements = _tree_to_elements(tree) if tree else []
    if elements:
        result_data["elements"] = elements
        result_data["description"] = vision.describe_elements(elements)

    content: list[dict[str, Any]] = [
        {"type": "text", "text": pretty_json(result_data)}
    ]

    if do_annotate and elements:
        try:
            annotated_bytes = vision.annotate_screenshot(screenshot_bytes, elements)
            annotated_b64 = base64.b64encode(annotated_bytes).decode("ascii")
            content.append({"type": "image", "data": annotated_b64, "mimeType": "image/png"})
        except Exception:
            content.append({"type": "image", "data": b64, "mimeType": "image/png"})
    else:
        content.append({"type": "image", "data": b64, "mimeType": "image/png"})

    return {"content": content}


def _tool_screenshot_diff(args: dict[str, Any], be: Any) -> dict[str, Any]:
    import base64

    from . import vision

    before_b64 = args.get("before")
    if not before_b64:
        raise RuntimeError("'before' is required")

    before_bytes = base64.b64decode(before_b64)
    after_b64 = args.get("after")

    if after_b64:
        after_bytes = base64.b64decode(after_b64)
    else:
        b64, w, h, method = be.capture_screenshot()
        after_bytes = base64.b64decode(b64)
        _types.LAST_SCREENSHOT = after_bytes

    threshold = float(args.get("threshold", 5.0))
    result = vision.diff_screenshots(before_bytes, after_bytes, threshold=threshold)

    content: list[dict[str, Any]] = [
        {"type": "text", "text": pretty_json({
            "changed": result["changed"],
            "change_percent": result.get("change_percent", 0),
            "regions": result["regions"],
        })}
    ]

    if result.get("diff_image"):
        diff_b64 = base64.b64encode(result["diff_image"]).decode("ascii")
        content.append({"type": "image", "data": diff_b64, "mimeType": "image/png"})

    return {"content": content}


def _tool_visual_click(args: dict[str, Any], be: Any) -> dict[str, Any]:
    import base64

    from . import matcher
    from . import vision

    description = args.get("description", "").strip()
    if not description:
        raise RuntimeError("'description' is required")
    app_name = args.get("app")
    match_strategy = args.get("match_strategy", "combined")
    click_count = int(args.get("click_count", 1))
    mouse_button = args.get("mouse_button", "left")

    if app_name:
        app_info = be.activate_or_launch_app(app_name)
        pid = app_info.get("pid", 0)
        be.get_accessibility_tree(app_name, pid)
        _types.LAST_APP = app_name

    b64, w, h, method = be.capture_screenshot()
    screenshot_bytes = base64.b64decode(b64)
    _types.LAST_SCREENSHOT = screenshot_bytes

    ocr_results: list[dict[str, Any]] = []
    if match_strategy in ("ocr", "combined", "auto"):
        ocr_results = vision.ocr_extract(screenshot_bytes)

    elements = _types.flat_elements()
    matches = matcher.find_elements(
        description,
        elements=elements,
        ocr_results=ocr_results,
        match_strategy=match_strategy,
        max_results=1,
    )

    if not matches:
        return error_result(
            "No matching element found for: " + description,
            {"description": description, "strategy": match_strategy},
        )

    best = matches[0]
    cx, cy = matcher.match_center(best)

    click_result = be.click(
        element_index=best.element_index if best.element_index else None,
        x=cx,
        y=cy,
        mouse_button=mouse_button,
        click_count=click_count,
    )

    return {
        "clicked": True,
        "match": {
            "element_index": best.element_index,
            "role": best.role,
            "title": best.title,
            "score": best.score,
            "source": best.source,
            "frame": best.frame,
        },
        "coordinates": {"x": cx, "y": cy},
        "click_result": click_result,
    }


def _tool_visual_locate(args: dict[str, Any], be: Any) -> dict[str, Any]:
    import base64

    from . import matcher
    from . import vision

    description = args.get("description", "").strip()
    if not description:
        raise RuntimeError("'description' is required")
    app_name = args.get("app")
    match_strategy = args.get("match_strategy", "combined")
    max_results = int(args.get("max_results", 5))

    if app_name:
        app_info = be.activate_or_launch_app(app_name)
        pid = app_info.get("pid", 0)
        be.get_accessibility_tree(app_name, pid)
        _types.LAST_APP = app_name

    b64, w, h, method = be.capture_screenshot()
    screenshot_bytes = base64.b64decode(b64)
    _types.LAST_SCREENSHOT = screenshot_bytes

    ocr_results: list[dict[str, Any]] = []
    if match_strategy in ("ocr", "combined", "auto"):
        ocr_results = vision.ocr_extract(screenshot_bytes)

    elements = _types.flat_elements()
    matches = matcher.find_elements(
        description,
        elements=elements,
        ocr_results=ocr_results,
        match_strategy=match_strategy,
        max_results=max_results,
    )

    match_list = []
    for m in matches:
        entry: dict[str, Any] = {
            "element_index": m.element_index,
            "role": m.role,
            "title": m.title,
            "score": m.score,
            "source": m.source,
            "frame": m.frame,
        }
        if m.ocr_text:
            entry["ocr_text"] = m.ocr_text
        match_list.append(entry)

    return {
        "matches": match_list,
        "count": len(match_list),
        "description": description,
        "strategy": match_strategy,
    }


def _save_tree_snapshot(tree: dict[str, Any] | None) -> None:
    if not os.environ.get("GSD_CU_SNAPSHOT_TREES"):
        return
    if tree is None:
        return
    os.makedirs("artifacts/trees", exist_ok=True)
    path = f"artifacts/trees/tree-{time.time():.6f}.json"
    try:
        with open(path, "w") as f:
            json.dump(tree, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _save_failure_bundle(error: str, request_id: Any, tool_name: str, args: dict[str, Any]) -> None:
    from . import failure
    from . import types as _types_mod
    try:
        failure.create_failure_bundle(
            error=error,
            tb=traceback.format_exc(),
            request={"id": request_id, "tool": tool_name, "args": args},
            audit_log_path=_audit.get_path(),
            screenshot=_types_mod.LAST_SCREENSHOT or None,
        )
    except Exception:
        pass


TOOL_HANDLERS: dict[str, Callable] = {
    "get_app_state": _tool_get_app_state,
    "list_apps": _tool_list_apps,
    "click": _tool_click,
    "drag": _tool_drag,
    "press_key": _tool_press_key,
    "type_text": _tool_type_text,
    "scroll": _tool_scroll,
    "set_value": _tool_set_value,
    "perform_secondary_action": _tool_perform_secondary_action,
    "analyze_screenshot": _tool_analyze_screenshot,
    "screenshot_diff": _tool_screenshot_diff,
    "visual_click": _tool_visual_click,
    "visual_locate": _tool_visual_locate,
}


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    global backend
    if "id" not in message:
        return None

    request_id = message["id"]
    method = message.get("method")
    params = message.get("params") or {}

    if backend is None:
        backend = get_backend()

    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            from .tools import TOOLS
            result = {"tools": TOOLS}
        elif method == "tools/call":
            _call_start = time.monotonic()
            name = params.get("name")
            if not name or name not in TOOL_HANDLERS:
                _lat = (time.monotonic() - _call_start) * 1000
                _audit.log_action(str(name), {}, "error: unknown tool", error=f"Unknown tool: {name}", latency_ms=_lat)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": error_result(f"Unknown tool: {name}"),
                }
            allowed, reason = _safety.check_action_allowed()
            if not allowed:
                _lat = (time.monotonic() - _call_start) * 1000
                _audit.log_action(name, {}, f"blocked: {reason}", latency_ms=_lat)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": error_result(reason),
                }
            arguments = params.get("arguments") or {}
            try:
                tool_result = TOOL_HANDLERS[name](arguments, backend)
                if "content" in tool_result:
                    result = tool_result
                else:
                    result = ok_text(tool_result)
                _safety.record_action()
                _lat = (time.monotonic() - _call_start) * 1000
                _audit.log_action(name, arguments, "ok", latency_ms=_lat)
            except Exception as exc:
                _lat = (time.monotonic() - _call_start) * 1000
                result = error_result(str(exc))
                _audit.log_action(name, arguments, "error", error=str(exc), latency_ms=_lat)
                _save_failure_bundle(str(exc), request_id, name, arguments)
        elif method == "resources/list":
            result = {"resources": []}
        elif method == "prompts/list":
            result = {"prompts": []}
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": f"Internal error: {exc}"},
        }


def serve_stdio() -> None:
    import sys
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle_request(message)
            if response is not None:
                sys.stdout.write(json_dumps(response) + "\n")
                sys.stdout.flush()
        except Exception:
            sys.stderr.write(traceback.format_exc() + "\n")
            sys.stderr.flush()


def self_test() -> int:
    from .tools import TOOLS
    names = [tool["name"] for tool in TOOLS]
    missing_handlers = [name for name in names if name not in TOOL_HANDLERS]
    schemas = [tool.get("inputSchema", {}).get("type") == "object" for tool in TOOLS]
    result = {
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "toolCount": len(TOOLS),
        "tools": names,
        "missingHandlers": missing_handlers,
        "schemasValid": all(schemas),
    }
    print(pretty_json(result))
    return 1 if missing_handlers or not all(schemas) else 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Self-hosted Computer Use MCP server")
    parser.add_argument("--self-test", action="store_true", help="Validate server metadata without touching the GUI")
    parser.add_argument("--list-tools", action="store_true", help="Print tool schemas and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.list_tools:
        from .tools import TOOLS
        print(pretty_json({"tools": TOOLS}))
        return 0

    serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
