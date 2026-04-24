"""Structured JSONL audit logging for desktop actions."""
from __future__ import annotations
import json
import os
import time
from typing import Any

_audit_log_path: str | None = None

def configure(path: str | None) -> None:
    """Set the audit log file path. None disables logging."""
    global _audit_log_path
    _audit_log_path = path

def log_action(tool: str, args: dict[str, Any], result_summary: str, error: str | None = None) -> None:
    """Write one JSONL line for a tool invocation."""
    if _audit_log_path is None:
        return
    entry = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool": tool,
        "args": {k: v for k, v in args.items() if k not in ("screenshot", "image_data")},
        "result": result_summary,
    }
    if error:
        entry["error"] = error
    try:
        with open(_audit_log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
