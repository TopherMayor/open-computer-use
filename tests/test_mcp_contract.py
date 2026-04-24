from __future__ import annotations

from mcp_client import MCPClient


class TestMCPContract:
    def test_server_starts_over_stdio(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            assert client.proc is not None
            assert client.proc.returncode is None
        finally:
            client.close()

    def test_initialize_returns_server_info(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.initialize()
            assert "result" in result
            server_info = result["result"]["serverInfo"]
            assert server_info["name"] == "gsd-computer-use"
            assert "version" in server_info
        finally:
            client.close()

    def test_tools_list_returns_all_tools(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tools_list()
            assert "result" in result
            tools = result["result"]["tools"]
            tool_names = [t["name"] for t in tools]
            expected = [
                "get_app_state",
                "list_apps",
                "click",
                "drag",
                "press_key",
                "type_text",
                "scroll",
                "set_value",
                "perform_secondary_action",
                "analyze_screenshot",
                "screenshot_diff",
            ]
            for name in expected:
                assert name in tool_names, f"Missing tool: {name}"
        finally:
            client.close()

    def test_every_tool_has_input_schema(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tools_list()
            tools = result["result"]["tools"]
            for tool in tools:
                assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"
                assert tool["inputSchema"]["type"] == "object"
        finally:
            client.close()

    def test_invalid_tool_name_returns_error(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("nonexistent_tool", {})
            assert "result" in result
            content = result["result"]["content"]
            assert any(c.get("type") == "text" for c in content)
            text_content = next((c for c in content if c.get("type") == "text"), {})
            assert "error" in text_content.get("text", "").lower()
        finally:
            client.close()

    def test_missing_required_arguments_returns_error(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.tool_call("get_app_state", {})
            assert "result" in result
            content = result["result"]["content"]
            text_content = next((c for c in content if c.get("type") == "text"), {})
            assert "error" in text_content.get("text", "").lower()
        finally:
            client.close()

    def test_resources_list_returns_empty(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.send({"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}})
            assert "result" in result
            resources = result["result"]["resources"]
            assert resources == []
        finally:
            client.close()

    def test_prompts_list_returns_empty(self):
        client = MCPClient(backend="fake")
        client.start()
        try:
            result = client.send({"jsonrpc": "2.0", "id": 5, "method": "prompts/list", "params": {}})
            assert "result" in result
            prompts = result["result"]["prompts"]
            assert prompts == []
        finally:
            client.close()
