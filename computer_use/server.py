from __future__ import annotations

import json
import os
import platform
import traceback
from typing import Any, Callable

from . import SERVER_NAME, SERVER_VERSION
from . import types as _types

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


def _tool_get_app_state(args: dict[str, Any], be: Any) -> dict[str, Any]:
    app_name = args.get("app")
    if not app_name:
        raise RuntimeError("'app' is required")
    max_depth = int(args.get("max_depth", 7))
    max_elements = int(args.get("max_elements", 220))
    include_screenshot = args.get("include_screenshot", True)

    app_info = be.activate_or_launch_app(app_name)
    pid = app_info.get("pid", 0)

    tree = be.get_accessibility_tree(app_name, pid, max_depth=max_depth, max_elements=max_elements)
    _types.LAST_APP = app_name

    content: list[dict[str, Any]] = [
        {"type": "text", "text": pretty_json({"app": app_info, "accessibility_tree": tree})}
    ]
    if include_screenshot:
        b64, w, h, method = be.capture_screenshot()
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
    return be.type_text(args["text"])


def _tool_scroll(args: dict[str, Any], be: Any) -> dict[str, Any]:
    return be.scroll(
        args["element_index"],
        args["direction"],
        float(args.get("pages", 1)),
    )


def _tool_set_value(args: dict[str, Any], be: Any) -> dict[str, Any]:
    return be.set_value(args["element_index"], args["value"])


def _tool_perform_secondary_action(args: dict[str, Any], be: Any) -> dict[str, Any]:
    return be.perform_action(args["element_index"], args["action"])


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
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            from .tools import TOOLS
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name not in TOOL_HANDLERS:
                raise RuntimeError(f"Unknown tool: {name}")
            try:
                tool_result = TOOL_HANDLERS[name](arguments, backend)
                if "content" in tool_result:
                    result = tool_result
                else:
                    result = ok_text(tool_result)
            except Exception as exc:
                result = error_result(str(exc))
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
            "result": error_result(str(exc)),
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
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Self-hosted Computer Use MCP server")
    parser.add_argument("--self-test", action="store_true", help="Validate server metadata without touching the GUI")
    parser.add_argument("--list-tools", action="store_true", help="Print tool schemas and exit")
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