from __future__ import annotations

import base64
import os

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        try:
            from open_computer_use.server import get_backend

            be = get_backend()
            b64, w, h, method = be.capture_screenshot()
            os.makedirs("test-recordings", exist_ok=True)
            safe_name = item.name.replace("/", "_").replace(" ", "_")
            path = f"test-recordings/{safe_name}_failure.png"
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
        except Exception:
            pass
