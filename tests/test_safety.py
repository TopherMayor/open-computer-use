from __future__ import annotations

import os
import time

from computer_use import safety
from computer_use.safety import ActionBudget, RateLimiter


class TestActionBudget:
    def test_unlimited(self):
        b = ActionBudget(0)
        assert b.check() is True
        assert b.remaining() == -1

    def test_limited(self):
        b = ActionBudget(3)
        assert b.check() is True
        b.consume()
        assert b.check() is True
        assert b.remaining() == 2
        b.consume()
        b.consume()
        assert b.check() is False
        assert b.remaining() == 0

    def test_exceeded_stays_exceeded(self):
        b = ActionBudget(1)
        b.consume()
        assert b.check() is False
        b.consume()
        assert b.check() is False

    def test_remaining_cannot_go_negative(self):
        b = ActionBudget(1)
        b.consume()
        b.consume()
        assert b.remaining() == 0


class TestRateLimiter:
    def test_unlimited(self):
        r = RateLimiter(0)
        assert r.check() is True

    def test_limited(self):
        r = RateLimiter(2)
        assert r.check() is True
        r.consume()
        assert r.check() is True
        r.consume()
        assert r.check() is False

    def test_window_expiry(self):
        r = RateLimiter(1)
        r.consume()
        assert r.check() is False
        r.timestamps[0] = time.time() - 61
        assert r.check() is True


class TestConfigureSafety:
    def test_resets_state(self):
        safety.configure_safety(max_actions=1)
        safety._budget.consume()
        assert safety._budget.check() is False
        safety.configure_safety(max_actions=5)
        assert safety._budget.check() is True

    def test_unlimited_default(self):
        safety.configure_safety()
        assert safety._budget.max_actions == 0
        assert safety._rate_limiter.max_per_minute == 0


class TestCheckActionAllowed:
    def test_allowed(self):
        safety.configure_safety()
        allowed, reason = safety.check_action_allowed()
        assert allowed is True
        assert reason == ""

    def test_budget_exceeded(self):
        safety.configure_safety(max_actions=1)
        safety.record_action()
        allowed, reason = safety.check_action_allowed()
        assert allowed is False
        assert "budget exceeded" in reason
        safety.configure_safety()

    def test_rate_limit_exceeded(self):
        safety.configure_safety(max_per_minute=1)
        safety.record_action()
        allowed, reason = safety.check_action_allowed()
        assert allowed is False
        assert "Rate limit exceeded" in reason
        safety.configure_safety()


class TestEmergencyStop:
    def test_no_file_means_no_stop(self, tmp_path):
        safety._EMERGENCY_STOP_FILE = str(tmp_path / "stop")
        assert safety.check_emergency_stop() is False

    def test_file_triggers_stop(self, tmp_path):
        stop_file = tmp_path / "stop"
        stop_file.touch()
        safety._EMERGENCY_STOP_FILE = str(stop_file)
        assert safety.check_emergency_stop() is True
        os.remove(str(stop_file))

    def test_env_var_unset_means_no_stop(self):
        original = safety._EMERGENCY_STOP_FILE
        safety._EMERGENCY_STOP_FILE = ""
        assert safety.check_emergency_stop() is False
        safety._EMERGENCY_STOP_FILE = original

    def test_emergency_stop_in_check_action_allowed(self, tmp_path):
        stop_file = tmp_path / "stop"
        stop_file.touch()
        original = safety._EMERGENCY_STOP_FILE
        safety._EMERGENCY_STOP_FILE = str(stop_file)
        allowed, reason = safety.check_action_allowed()
        assert allowed is False
        assert "Emergency stop active" in reason
        os.remove(str(stop_file))
        safety._EMERGENCY_STOP_FILE = original


class TestSafetyIntegration:
    def test_handle_request_respects_budget(self):
        from computer_use.server import handle_request

        safety.configure_safety(max_actions=1)
        try:
            msg1 = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            resp1 = handle_request(msg1)
            assert "error" not in resp1.get("result", {}).get("content", [{}])[0].get("text", "").lower() or resp1.get("result", {}).get("isError") is not True

            msg2 = {"id": 2, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            resp2 = handle_request(msg2)
            assert resp2.get("result", {}).get("isError") is True
        finally:
            safety.configure_safety()

    def test_handle_request_respects_rate_limit(self):
        from computer_use.server import handle_request

        safety.configure_safety(max_per_minute=1)
        try:
            msg1 = {"id": 1, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            handle_request(msg1)

            msg2 = {"id": 2, "method": "tools/call", "params": {"name": "list_apps", "arguments": {}}}
            resp2 = handle_request(msg2)
            assert resp2.get("result", {}).get("isError") is True
        finally:
            safety.configure_safety()
