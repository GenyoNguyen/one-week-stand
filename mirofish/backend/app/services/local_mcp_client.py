"""Synchronous bridge to MiroFish's local stdio MCP server."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..config import Config
from ..utils.logger import get_logger


logger = get_logger("mirofish.local_mcp")


class LocalMCPClient:
    """Discover and invoke local MCP tools using one stdio process per operation."""

    def __init__(self):
        backend_dir = Path(__file__).resolve().parents[2]
        if Config.MCP_SERVER_COMMAND:
            command = Config.MCP_SERVER_COMMAND
            args = Config.MCP_SERVER_ARGS
        else:
            command = sys.executable
            args = [str(backend_dir / "mcp_server.py")]
        allowed_env = ("HOME", "LANG", "LC_ALL", "PATH", "TMPDIR", "VIRTUAL_ENV")
        env = {key: os.environ[key] for key in allowed_env if key in os.environ}
        env.update({
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "MIROFISH_MCP_DATA_DIR": Config.MCP_DATA_DIR,
            "MIROFISH_TABLE_SCHEMA_PATH": Config.MCP_TABLE_SCHEMA_PATH,
        })
        self.server_params = StdioServerParameters(command=command, args=args, env=env)
        self._tools: Optional[list[dict[str, Any]]] = None

    @staticmethod
    def _run(coroutine):
        return asyncio.run(coroutine)

    async def _list_tools(self) -> list[dict[str, Any]]:
        async with asyncio.timeout(Config.MCP_TIMEOUT_SECONDS):
            async with stdio_client(self.server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    response = await session.list_tools()
                    return [
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "input_schema": tool.inputSchema,
                        }
                        for tool in response.tools
                    ]

    def list_tools(self) -> list[dict[str, Any]]:
        if self._tools is None:
            try:
                self._tools = self._run(self._list_tools())
            except TimeoutError as exc:
                raise RuntimeError(
                    f"MCP tool discovery timed out after {Config.MCP_TIMEOUT_SECONDS:g}s"
                ) from exc
        return self._tools

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        error_message = None
        output = ""
        async with asyncio.timeout(Config.MCP_TIMEOUT_SECONDS):
            async with stdio_client(self.server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments=arguments)
                    if result.isError:
                        messages = [getattr(content, "text", str(content)) for content in result.content]
                        error_message = "\n".join(messages)
                    elif result.structuredContent is not None:
                        output = json.dumps(result.structuredContent, ensure_ascii=False)
                    else:
                        output = "\n".join(getattr(content, "text", str(content)) for content in result.content)
        if error_message:
            raise RuntimeError(error_message)
        return output

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        try:
            return self._run(self._call_tool(name, arguments))
        except TimeoutError as exc:
            raise RuntimeError(
                f"MCP tool {name} timed out after {Config.MCP_TIMEOUT_SECONDS:g}s"
            ) from exc
