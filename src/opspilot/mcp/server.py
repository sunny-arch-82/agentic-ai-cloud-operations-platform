"""Official MCP SDK stdio server. Logs go only to stderr."""

from datetime import datetime
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from opspilot.core.config import Settings
from opspilot.core.logging import configure
from opspilot.schemas.contracts import Service
from opspilot.storage.db import Database
from opspilot.tools.operational import OperationalTools, ToolResult


def build_server(settings=None):
    settings = settings or Settings()
    tools = OperationalTools(Database(settings), settings)
    server = FastMCP("OpsPilot operational evidence")
    read_only = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )

    @server.tool(annotations=read_only)
    async def search_knowledge(
        query: str,
        service: Service,
        reference_time: datetime,
        mode: Literal["semantic", "lexical", "hybrid"] = "hybrid",
        limit: int = 5,
    ) -> ToolResult:
        """Search published operational knowledge within a service/dependency scope."""
        return await tools.call(
            "search_knowledge",
            {
                "query": query,
                "service": service,
                "reference_time": reference_time,
                "mode": mode,
                "limit": limit,
            },
        )

    @server.tool(annotations=read_only)
    async def search_incidents(
        query: str,
        service: Service,
        reference_time: datetime,
        mode: Literal["semantic", "lexical", "hybrid"] = "hybrid",
        limit: int = 5,
    ) -> ToolResult:
        """Search historical incident documents published before reference_time."""
        return await tools.call(
            "search_incidents",
            {
                "query": query,
                "service": service,
                "reference_time": reference_time,
                "mode": mode,
                "limit": limit,
            },
        )

    @server.tool(annotations=read_only)
    async def get_document_section(
        section_id: str, service: Service, reference_time: datetime
    ) -> ToolResult:
        """Read a source section by its stable identifier and temporal/service scope."""
        return await tools.call(
            "get_document_section",
            {"section_id": section_id, "service": service, "reference_time": reference_time},
        )

    @server.tool(annotations=read_only)
    async def inspect_logs(
        dataset_id: str,
        service: Service,
        start: datetime,
        end: datetime,
        reference_time: datetime,
        limit: int = 100,
    ) -> ToolResult:
        """Return bounded timestamped logs and deterministic code counts."""
        return await tools.call(
            "inspect_logs",
            {
                "dataset_id": dataset_id,
                "service": service,
                "start": start,
                "end": end,
                "reference_time": reference_time,
                "limit": limit,
            },
        )

    @server.tool(annotations=read_only)
    async def fetch_service_metrics(
        dataset_id: str,
        service: Service,
        start: datetime,
        end: datetime,
        reference_time: datetime,
        limit: int = 100,
    ) -> ToolResult:
        """Aggregate metric samples into baseline/current windows with units and counts."""
        return await tools.call(
            "fetch_service_metrics",
            {
                "dataset_id": dataset_id,
                "service": service,
                "start": start,
                "end": end,
                "reference_time": reference_time,
                "limit": limit,
            },
        )

    @server.tool(annotations=read_only)
    async def list_service_changes(
        dataset_id: str,
        service: Service,
        start: datetime,
        end: datetime,
        reference_time: datetime,
        limit: int = 100,
    ) -> ToolResult:
        """List timestamped deployment/configuration changes; cannot execute changes."""
        return await tools.call(
            "list_service_changes",
            {
                "dataset_id": dataset_id,
                "service": service,
                "start": start,
                "end": end,
                "reference_time": reference_time,
                "limit": limit,
            },
        )

    return server


def main():
    settings = Settings()
    configure(settings.log_level)
    build_server(settings).run(transport="stdio")


if __name__ == "__main__":
    main()
