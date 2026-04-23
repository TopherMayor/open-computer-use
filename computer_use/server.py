from __future__ import annotations

import json
import os
import platform
import traceback
from typing import Any, Callable

from . import SERVER_NAME, SERVER_VERSION


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


backend = get_backend()


def tool_get_app_state(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    from .types import LAST_APP
    global LAST_APP

    app_name = str(args.get("app") or "").strip()
    if not app_name:
        raise RuntimeError("app is required")

    max_depth = int(args.get("max_depth", 7))
    max_elements = int(args.get("max_elements", 220))
    include_screenshot = bool(args.get("include_screenshot", True))

    app = be.activate_or_launch_app(app_name)
    LAST_APP = app_name
    be.clear_cache()

    screenshot_content: dict[str, Any] | None = None
    screenshot_meta: dict[str, Any] | None = None
    if include_screenshot:
        image_b64, width, height, capture_backend = be.capture_screenshot()
        screenshot_content = {"type": "image", "data": image_b64, "mimeType": "image/png"}
        screenshot_meta = {
            "width": width,
            "height": height,
            "backend": capture_backend,
            "coordinateSystem": "screen coordinates",
        }

    tree = be.get_accessibility_tree(
        app_name,
        app.get("pid", 0),
        max_depth=max_depth,
        max_elements=max_elements,
    )

    payload = {
        "app": app,
        "screen": be.screen_size(),
        "screenshot": screenshot_meta,
        "accessibilityTrusted": be.is_accessibility_trusted(),
        "accessibilityTree": tree,
        "flatElements": be.flat_elements(),
        "elementCount": len(be.flat_elements()),
        "notes": [
            "Use element_index values from this response for click, scroll, set_value, and perform_secondary_action.",
            "If accessibilityTrusted is false, grant Accessibility permission to the process launching this MCP server.",
        ],
    }

    content = []
    if screenshot_content is not None:
        content.append(screenshot_content)
    content.append({"type": "text", "text": pretty_json(payload)})
    return ok_content(content)


def tool_list_apps(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    apps = be.list_apps(
        recent_days=int(args.get("recent_days", 14)),
        include_recent=bool(args.get("include_recent", True)),
        include_installed=bool(args.get("include_installed", False)),
    )
    running = [a for a in apps if a.get("running")]
    recent = [a for a in apps if a.get("lastUsed")]
    installed = [a for a in apps if not a.get("running") and not a.get("lastUsed")]
    return ok_text({
        "runningCount": len(running),
        "recentCount": len(recent),
        "installedCount": len(installed),
        "apps": apps,
    })


def tool_click(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    result = be.click(
        element_index=args.get("element_index"),
        x=args.get("x"),
        y=args.get("y"),
        **args,
    )
    return ok_text(result)


def tool_drag(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    result = be.drag(
        from_x=int(args["from_x"]),
        from_y=int(args["from_y"]),
        to_x=int(args["to_x"]),
        to_y=int(args["to_y"]),
        **args,
    )
    return ok_text(result)


def tool_press_key(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    result = be.press_key(str(args.get("key") or ""))
    return ok_text(result)


def tool_type_text(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    result = be.type_text(str(args.get("text") or ""))
    return ok_text(result)


def tool_scroll(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    result = be.scroll(
        element_index=str(args.get("element_index")),
        direction=str(args.get("direction", "down")),
        pages=float(args.get("pages", 1)),
        **args,
    )
    return ok_text(result)


def tool_set_value(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    result = be.set_value(
        element_index=str(args.get("element_index")),
        value=str(args.get("value") or ""),
        **args,
    )
    return ok_text(result)


def tool_perform_secondary_action(args: dict[str, Any], be: Any = None) -> dict[str, Any]:
    result = be.perform_action(
        element_index=str(args.get("element_index")),
        action=str(args.get("action") or ""),
        **args,
    )
    return ok_text(result)


TOOL_HANDLERS: dict[str, Callable[[dict[str, Any], Any], dict[str, Any]]] = {
    "get_app_state": tool_get_app_state,
    "list_apps": tool_list_apps,
    "click": tool_click,
    "drag": tool_drag,
    "press_key": tool_press_key,
    "type_text": tool_type_text,
    "scroll": tool_scroll,
    "set_value": tool_set_value,
    "perform_secondary_action": tool_perform_secondary_action,
}


PROTOCOL_VERSION = "2024-11-05"
DEFAULT_MAX_DEPTH = 7
DEFAULT_MAX_ELEMENTS = 220


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    if "id" not in message:
        return None

    request_id = message["id"]
    method = message.get("method")
    params = message.get("params") or {}

    global backend
    if method in ("initialize", "ping", "tools/list", "resources/list", "prompts/list"):
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
            result = TOOL_HANDLERS[name](arguments, backend)
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