from __future__ import annotations

import json
import os
import subprocess
from typing import Any


class MCPClient:
    def __init__(self, backend: str = "fake"):
        self.env = {**os.environ, "OPEN_CU_BACKEND": backend, "PYTHONPATH": os.getcwd()}
        self.proc = None

    def start(self) -> None:
        self.proc = subprocess.Popen(
            ["python3", "scripts/open_computer_use_mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env,
        )

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        if self.proc is None:
            self.start()
        assert self.proc is not None
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        response = self.proc.stdout.readline()
        return json.loads(response) if response else {}

    def initialize(self) -> dict[str, Any]:
        return self.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    def tools_list(self) -> dict[str, Any]:
        return self.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

    def tool_call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.send({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })

    def close(self) -> None:
        if self.proc:
            self.proc.stdin.close()
            self.proc.wait(timeout=2)
            self.proc = None
