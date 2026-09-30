"""Real subprocess MCP transport used by the application and diagnostic CLI."""

import os
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from opspilot.tools.operational import ToolResult


class MCPTools:
    def __init__(self, session):
        self.session = session

    async def call(self, name, arguments):
        result = await self.session.call_tool(name, arguments)
        if result.isError:
            # Do not expose upstream exception text, credentials or stack traces.
            raise ValueError(f"MCP tool {name} failed validation or execution")
        if result.structuredContent is None:
            raise ValueError("MCP tool returned no structured content")
        return ToolResult.model_validate(result.structuredContent)

    async def list_tools(self):
        return (await self.session.list_tools()).tools


@asynccontextmanager
async def connect_tools(settings):
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "SYSTEMROOT", "PYTHONPATH"}}
    env.update(
        {
            "OPSPILOT_MODE": settings.mode,
            "OPSPILOT_DATABASE_URL": settings.database_url.get_secret_value(),
            "OPSPILOT_EMBEDDING_MODEL": settings.embedding_model,
            "OPSPILOT_EMBEDDING_DIMENSIONS": str(settings.embedding_dimensions),
            "OPSPILOT_CONTEXT_CHARS": str(settings.context_chars),
            "OPSPILOT_LOG_LEVEL": settings.log_level,
            "OPSPILOT_PROVIDER_TIMEOUT_SECONDS": str(settings.provider_timeout_seconds),
        }
    )
    if settings.openai_api_key:
        env["OPENAI_API_KEY"] = settings.openai_api_key.get_secret_value()
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "opspilot.mcp.server"], env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield MCPTools(session)
