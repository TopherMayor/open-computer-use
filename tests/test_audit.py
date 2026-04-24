from __future__ import annotations

import json
import os
import tempfile

import pytest

from computer_use import audit


class TestAuditConfigure:
    def test_configure_none_disables_logging(self, tmp_path):
        audit.configure(str(tmp_path / "audit.jsonl"))
        audit.configure(None)
        audit.log_action("test", {}, "ok")
        assert not (tmp_path / "audit.jsonl").exists()

    def test_configure_enables_logging(self, tmp_path):
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        audit.log_action("test", {}, "ok")
        assert os.path.exists(path)
        audit.configure(None)


class TestLogAction:
    def test_writes_valid_jsonl(self, tmp_path):
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        audit.log_action("click", {"x": 100, "y": 200}, "ok")
        audit.configure(None)
        with open(path) as f:
            line = f.readline()
        entry = json.loads(line)
        assert entry["tool"] == "click"
        assert entry["args"]["x"] == 100
        assert entry["result"] == "ok"
        assert "ts" in entry
        assert "iso" in entry

    def test_strips_binary_args(self, tmp_path):
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        audit.log_action("get_app_state", {"app": "Safari", "screenshot": "bigbase64data", "image_data": "moredata"}, "ok")
        audit.configure(None)
        with open(path) as f:
            line = f.readline()
        entry = json.loads(line)
        assert "screenshot" not in entry["args"]
        assert "image_data" not in entry["args"]
        assert entry["args"]["app"] == "Safari"

    def test_includes_error_field(self, tmp_path):
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        audit.log_action("click", {"x": 1}, "error", error="something broke")
        audit.configure(None)
        with open(path) as f:
            line = f.readline()
        entry = json.loads(line)
        assert entry["error"] == "something broke"

    def test_no_error_field_when_none(self, tmp_path):
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        audit.log_action("click", {"x": 1}, "ok")
        audit.configure(None)
        with open(path) as f:
            line = f.readline()
        entry = json.loads(line)
        assert "error" not in entry

    def test_missing_directory_graceful(self, tmp_path):
        path = str(tmp_path / "nonexistent" / "dir" / "audit.jsonl")
        audit.configure(path)
        audit.log_action("test", {}, "ok")  # should not crash
        audit.configure(None)

    def test_multiple_entries(self, tmp_path):
        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        audit.log_action("click", {"x": 1}, "ok")
        audit.log_action("type_text", {"text": "hi"}, "ok")
        audit.configure(None)
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["tool"] == "click"
        assert json.loads(lines[1])["tool"] == "type_text"


class TestAuditIntegration:
    def test_handle_request_produces_audit_entry(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            handle_request(msg)
            assert os.path.exists(path)
            with open(path) as f:
                line = f.readline()
            entry = json.loads(line)
            assert entry["tool"] == "list_apps"
            assert entry["result"] == "ok"
        finally:
            audit.configure(None)

    def test_handle_request_error_produces_audit_entry(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            msg = {"id": 1, "method": "tools/call", "params": {"name": "nonexistent", "arguments": {}}}
            handle_request(msg)
            assert os.path.exists(path)
            with open(path) as f:
                line = f.readline()
            entry = json.loads(line)
            assert "error" in entry
        finally:
            audit.configure(None)

    def test_non_tool_call_no_audit(self, tmp_path):
        from computer_use.server import handle_request

        path = str(tmp_path / "audit.jsonl")
        audit.configure(path)
        try:
            msg = {"id": 1, "method": "initialize", "params": {}}
            handle_request(msg)
            assert not os.path.exists(path)
        finally:
            audit.configure(None)
