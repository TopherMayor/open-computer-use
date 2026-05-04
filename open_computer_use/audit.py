"""Structured JSONL audit logging for desktop actions."""
from __future__ import annotations

import json
import time
from typing import Any

_audit_log_path: str | None = None
_latency_data: dict[str, list[float]] = {}


def configure(path: str | None) -> None:
    """Set the audit log file path. None disables logging."""
    global _audit_log_path
    _audit_log_path = path


def get_path() -> str | None:
    """Return the current audit log path."""
    return _audit_log_path


def log_action(
    tool: str,
    args: dict[str, Any],
    result_summary: str,
    error: str | None = None,
    latency_ms: float | None = None,
) -> None:
    """Write one JSONL line for a tool invocation."""
    if _audit_log_path is None:
        return
    entry: dict[str, Any] = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool": tool,
        "args": {k: v for k, v in args.items() if k not in ("screenshot", "image_data")},
        "result": result_summary,
    }
    if error:
        entry["error"] = error
    if latency_ms is not None:
        entry["latency_ms"] = round(latency_ms, 3)
        _latency_data.setdefault(tool, []).append(latency_ms)
    try:
        with open(_audit_log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def get_metrics() -> dict[str, dict[str, float]]:
    """Return aggregate latency stats per tool: count, mean, p50, p99."""
    result: dict[str, dict[str, float]] = {}
    for tool, latencies in _latency_data.items():
        if not latencies:
            continue
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        mean_val = sum(sorted_lat) / n
        result[tool] = {
            "count": float(n),
            "mean": round(mean_val, 3),
            "p50": round(_percentile(sorted_lat, 50), 3),
            "p99": round(_percentile(sorted_lat, 99), 3),
        }
    return result


def reset_metrics() -> None:
    """Clear all accumulated latency data."""
    _latency_data.clear()


def _percentile(sorted_data: list[float], p: float) -> float:
    """Compute the p-th percentile using linear interpolation."""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    k = (p / 100.0) * (n - 1)
    f = int(k)
    c = f + 1
    if c >= n:
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
