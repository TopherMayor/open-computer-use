from __future__ import annotations

import json
import os

import pytest

from computer_use import audit
from computer_use import safety


@pytest.fixture(autouse=True)
def _reset_audit():
    audit.reset_metrics()
    yield
    audit.reset_metrics()
    audit.configure(None)


class TestLatencyTracking:
    def test_latency_ms_in_audit_entry(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            handle_request(msg)
            with open(path) as f:
                entry = json.loads(f.readline())
            assert "latency_ms" in entry
            assert isinstance(entry["latency_ms"], float)
            assert entry["latency_ms"] >= 0
        finally:
            audit.configure(None)

    def test_latency_ms_on_error(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "press_key", "arguments": {}}}
            handle_request(msg)
            with open(path) as f:
                entry = json.loads(f.readline())
            assert "latency_ms" in entry
            assert entry["result"] == "error"
        finally:
            audit.configure(None)

    def test_latency_ms_on_unknown_tool(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "bogus_tool", "arguments": {}}}
            handle_request(msg)
            with open(path) as f:
                entry = json.loads(f.readline())
            assert "latency_ms" in entry
        finally:
            audit.configure(None)

    def test_direct_log_action_without_latency(self, tmp_path):
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            audit.log_action("test", {}, "ok")
            with open(path) as f:
                entry = json.loads(f.readline())
            assert "latency_ms" not in entry
        finally:
            audit.configure(None)


class TestGetMetrics:
    def test_empty_metrics(self):
        assert audit.get_metrics() == {}

    def test_single_tool_metrics(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            for i in range(5):
                msg = {"id": i, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
                handle_request(msg)
            metrics = audit.get_metrics()
            assert "list_apps" in metrics
            m = metrics["list_apps"]
            assert m["count"] == 5.0
            assert m["mean"] > 0
            assert m["p50"] > 0
            assert m["p99"] > 0
            assert m["p50"] <= m["p99"]
        finally:
            audit.configure(None)

    def test_multiple_tools_tracked_separately(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            safety.configure_safety()
            msg1 = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            msg2 = {"id": 2, "method": "tools/call", "params": {"name": "click", "arguments": {"x": 10, "y": 20}}}
            handle_request(msg1)
            handle_request(msg2)
            metrics = audit.get_metrics()
            assert "list_apps" in metrics
            assert "click" in metrics
            assert metrics["list_apps"]["count"] == 1.0
            assert metrics["click"]["count"] == 1.0
        finally:
            audit.configure(None)

    def test_reset_metrics(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            handle_request(msg)
            assert "list_apps" in audit.get_metrics()
            audit.reset_metrics()
            assert audit.get_metrics() == {}
        finally:
            audit.configure(None)

    def test_percentile_single_entry(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            handle_request(msg)
            m = audit.get_metrics()["list_apps"]
            assert m["p50"] == m["p99"] == m["mean"]
        finally:
            audit.configure(None)


class TestFailureBundles:
    def test_no_bundle_when_disabled(self, tmp_path, monkeypatch):
        from computer_use.server import handle_request

        monkeypatch.delenv("GSD_CU_FAILURE_BUNDLES", raising=False)
        monkeypatch.chdir(tmp_path)
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        safety.configure_safety()
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "press_key", "arguments": {}}}
            handle_request(msg)
            assert not (tmp_path / "failure-bundles").exists()
        finally:
            audit.configure(None)

    def test_bundle_created_on_tool_error(self, tmp_path, monkeypatch):
        from computer_use.server import handle_request

        monkeypatch.setenv("GSD_CU_FAILURE_BUNDLES", "1")
        monkeypatch.chdir(tmp_path)
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        safety.configure_safety()
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "press_key", "arguments": {}}}
            handle_request(msg)
            bundle_dir = tmp_path / "failure-bundles"
            assert bundle_dir.exists()
            files = list(bundle_dir.glob("failure-*.json"))
            assert len(files) == 1
            with open(files[0]) as f:
                bundle = json.load(f)
            assert "error" in bundle
            assert "traceback" in bundle
            assert "request" in bundle
            assert "environment" in bundle
            assert bundle["request"]["tool"] == "press_key"
            assert "python" in bundle["environment"]
            assert "platform" in bundle["environment"]
        finally:
            audit.configure(None)

    def test_bundle_includes_audit_entries(self, tmp_path, monkeypatch):
        from computer_use.server import handle_request

        monkeypatch.setenv("GSD_CU_FAILURE_BUNDLES", "1")
        monkeypatch.chdir(tmp_path)
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        safety.configure_safety()
        try:
            ok_msg = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            handle_request(ok_msg)
            err_msg = {"id": 2, "method": "tools/call", "params": {"name": "press_key", "arguments": {}}}
            handle_request(err_msg)
            bundle_dir = tmp_path / "failure-bundles"
            files = list(bundle_dir.glob("failure-*.json"))
            assert len(files) == 1
            with open(files[0]) as f:
                bundle = json.load(f)
            assert "recent_audit" in bundle
            assert len(bundle["recent_audit"]) >= 1
        finally:
            audit.configure(None)

    def test_bundle_contains_screenshot_when_available(self, tmp_path, monkeypatch):
        from computer_use.server import handle_request
        from computer_use import types as _types

        monkeypatch.setenv("GSD_CU_FAILURE_BUNDLES", "1")
        monkeypatch.chdir(tmp_path)
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        safety.configure_safety()
        try:
            _types.LAST_SCREENSHOT = b"fake_screenshot_data"
            err_msg = {"id": 1, "method": "tools/call", "params": {"name": "press_key", "arguments": {}}}
            handle_request(err_msg)
            bundle_dir = tmp_path / "failure-bundles"
            files = list(bundle_dir.glob("failure-*.json"))
            assert len(files) == 1
            with open(files[0]) as f:
                bundle = json.load(f)
            assert "screenshot_b64" in bundle
        finally:
            _types.LAST_SCREENSHOT = b""
            audit.configure(None)

    def test_no_bundle_on_success(self, tmp_path, monkeypatch):
        from computer_use.server import handle_request

        monkeypatch.setenv("GSD_CU_FAILURE_BUNDLES", "1")
        monkeypatch.chdir(tmp_path)
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        safety.configure_safety()
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            handle_request(msg)
            assert not (tmp_path / "failure-bundles").exists()
        finally:
            audit.configure(None)


class TestTreeSnapshots:
    def test_no_snapshot_when_disabled(self, tmp_path, monkeypatch):
        from computer_use.server import _tool_get_app_state
        from computer_use.backends.fake import create_backend

        monkeypatch.delenv("GSD_CU_SNAPSHOT_TREES", raising=False)
        monkeypatch.chdir(tmp_path)
        be = create_backend()
        _tool_get_app_state({"app": "FakeApp"}, be)
        assert not (tmp_path / "artifacts").exists()

    def test_snapshot_created_when_enabled(self, tmp_path, monkeypatch):
        from computer_use.server import _tool_get_app_state
        from computer_use.backends.fake import create_backend

        monkeypatch.setenv("GSD_CU_SNAPSHOT_TREES", "1")
        monkeypatch.chdir(tmp_path)
        be = create_backend()
        _tool_get_app_state({"app": "FakeApp"}, be)
        tree_dir = tmp_path / "artifacts" / "trees"
        assert tree_dir.exists()
        files = list(tree_dir.glob("tree-*.json"))
        assert len(files) == 1
        with open(files[0]) as f:
            tree = json.load(f)
        assert "role" in tree
        assert tree["role"] == "window"

    def test_multiple_snapshots_unique_files(self, tmp_path, monkeypatch):
        import time

        from computer_use.server import _tool_get_app_state
        from computer_use.backends.fake import create_backend

        monkeypatch.setenv("GSD_CU_SNAPSHOT_TREES", "1")
        monkeypatch.chdir(tmp_path)
        be = create_backend()
        _tool_get_app_state({"app": "FakeApp"}, be)
        time.sleep(0.001)
        _tool_get_app_state({"app": "FakeApp"}, be)
        tree_dir = tmp_path / "artifacts" / "trees"
        files = list(tree_dir.glob("tree-*.json"))
        assert len(files) == 2

    def test_snapshot_valid_json(self, tmp_path, monkeypatch):
        from computer_use.server import _tool_get_app_state
        from computer_use.backends.fake import create_backend

        monkeypatch.setenv("GSD_CU_SNAPSHOT_TREES", "1")
        monkeypatch.chdir(tmp_path)
        be = create_backend()
        _tool_get_app_state({"app": "FakeApp", "max_depth": 3, "max_elements": 5}, be)
        tree_dir = tmp_path / "artifacts" / "trees"
        files = list(tree_dir.glob("tree-*.json"))
        assert len(files) == 1
        with open(files[0]) as f:
            tree = json.load(f)
        assert tree["element_index"] == "0"
        assert isinstance(tree.get("children"), list)
