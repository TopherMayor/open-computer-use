"""Safety controls: action budgets, rate limiting, and emergency stop."""
from __future__ import annotations

import os
import time


class ActionBudget:
    """Track and enforce action count limits."""

    def __init__(self, max_actions: int = 0):
        """max_actions=0 means unlimited."""
        self.max_actions = max_actions
        self.count = 0

    def check(self) -> bool:
        """Return True if action is allowed, False if budget exceeded."""
        if self.max_actions <= 0:
            return True
        return self.count < self.max_actions

    def consume(self) -> None:
        """Record one action."""
        self.count += 1

    def remaining(self) -> int:
        """Actions remaining in budget."""
        if self.max_actions <= 0:
            return -1
        return max(0, self.max_actions - self.count)


class RateLimiter:
    """Token-bucket rate limiter."""

    def __init__(self, max_per_minute: int = 0):
        """max_per_minute=0 means unlimited."""
        self.max_per_minute = max_per_minute
        self.timestamps: list[float] = []

    def check(self) -> bool:
        """Return True if action is within rate limit."""
        if self.max_per_minute <= 0:
            return True
        now = time.time()
        window = 60.0
        self.timestamps = [t for t in self.timestamps if now - t < window]
        return len(self.timestamps) < self.max_per_minute

    def consume(self) -> None:
        """Record one action timestamp."""
        self.timestamps.append(time.time())


_budget: ActionBudget = ActionBudget()
_rate_limiter: RateLimiter = RateLimiter()
_EMERGENCY_STOP_FILE = os.environ.get("OPEN_CU_EMERGENCY_STOP_FILE", "")


def configure_safety(max_actions: int = 0, max_per_minute: int = 0) -> None:
    """Configure safety limits. 0 means unlimited."""
    global _budget, _rate_limiter
    _budget = ActionBudget(max_actions)
    _rate_limiter = RateLimiter(max_per_minute)


def check_emergency_stop() -> bool:
    """Return True if emergency stop is active."""
    if not _EMERGENCY_STOP_FILE:
        return False
    return os.path.exists(_EMERGENCY_STOP_FILE)


def check_action_allowed() -> tuple[bool, str]:
    """Check if an action is allowed. Returns (allowed, reason)."""
    if check_emergency_stop():
        return False, f"Emergency stop active — delete {_EMERGENCY_STOP_FILE} to resume"
    if not _budget.check():
        return False, f"Action budget exceeded ({_budget.max_actions} actions)"
    if not _rate_limiter.check():
        return False, f"Rate limit exceeded ({_rate_limiter.max_per_minute}/min)"
    return True, ""


def record_action() -> None:
    """Record that an action was taken."""
    _budget.consume()
    _rate_limiter.consume()
