import sys

import pytest

from ma_cli.mcp import MCPClient, MCPServerConfig


SERVER = r'''
import json, sys
for line in sys.stdin:
    req = json.loads(line)
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        result = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": "fake-mcp", "version": "1"},
        }
    elif method == "tools/list":
        result = {"tools": [{"name": "echo", "description": "Echo input", "inputSchema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}}]}
    elif method == "resources/list":
        result = {"resources": [{"uri": "memory://hello", "name": "hello", "mimeType": "text/plain"}], "resourceTemplates": []}
    elif method == "prompts/list":
        result = {"prompts": [{"name": "hello", "description": "hello"}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": req["params"]["arguments"]["text"]}]}
    elif method == "resources/read":
        result = {"contents": [{"uri": req["params"]["uri"], "text": "hello"}]}
    elif method == "prompts/get":
        result = {"description": "hello", "messages": [{"role": "user", "content": {"type": "text", "text": "hello"}}]}
    elif method == "ping":
        result = {}
    elif method == "notifications/initialized":
        continue
    else:
        result = {}
    if rid is not None:
        print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}), flush=True)
'''


@pytest.mark.asyncio
async def test_mcp_stdio_full_surface_and_schema_validation():
    config = MCPServerConfig(
        name="test",
        transport="stdio",
        command=sys.executable,
        args=["-u", "-c", SERVER],
        allow_command=True,
        reconnect_attempts=0,
    )
    client = MCPClient(config)
    await client.connect()
    try:
        assert client.server_info["name"] == "fake-mcp"
        assert "echo" in client.tools
        result = await client.call_tool("echo", {"text": "AIO-CLi"})
        assert result["content"][0]["text"] == "AIO-CLi"
        resource = await client.read_resource("memory://hello")
        assert resource["contents"][0]["text"] == "hello"
        prompt = await client.get_prompt("hello")
        assert prompt["messages"][0]["role"] == "user"
        assert await client.ping() == {}
        with pytest.raises(Exception):
            await client.call_tool("echo", {})
    finally:
        await client.close()
