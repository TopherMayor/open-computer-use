"""Failure bundle creation for tool call errors."""
from __future__ import annotations

import base64
import json
import os
import platform
import sys
import time
from typing import Any


def _enabled() -> bool:
    return os.environ.get("GSD_CU_FAILURE_BUNDLES") == "1"


def create_failure_bundle(
    error: str,
    tb: str,
    request: dict[str, Any],
    audit_log_path: str | None = None,
    screenshot: bytes | None = None,
) -> str | None:
    """Create a failure bundle JSON file. Returns the path or None if disabled."""
    if not _enabled():
        return None

    os.makedirs("failure-bundles", exist_ok=True)

    bundle: dict[str, Any] = {
        "timestamp": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "error": error,
        "traceback": tb,
        "request": request,
        "environment": {
            "backend": os.environ.get("GSD_CU_BACKEND", "auto"),
            "python": sys.version,
            "platform": platform.platform(),
        },
    }

    if audit_log_path:
        bundle["recent_audit"] = _read_recent_audit(audit_log_path, 60)

    if screenshot:
        bundle["screenshot_b64"] = base64.b64encode(screenshot).decode("ascii")

    path = f"failure-bundles/failure-{time.time():.6f}.json"
    with open(path, "w") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    return path


def _read_recent_audit(audit_log_path: str, window_seconds: float) -> list[dict[str, Any]]:
    """Read audit log entries from the last N seconds."""
    cutoff = time.time() - window_seconds
    entries: list[dict[str, Any]] = []
    try:
        with open(audit_log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("ts", 0) >= cutoff:
                        entries.append(entry)
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return entries
