"""
Azure Pricing MCP Server

A Model Context Protocol server that provides tools for querying Azure retail pricing.
"""

import asyncio
import logging
from typing import Any

from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from .client import AzurePricingClient
from .handlers import ToolHandlers, register_tool_handlers
from .services import PricingService, RetirementService, SKUService
from .tools import get_tool_definitions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AzurePricingServer:
    """Azure Pricing MCP Server - coordinates all services."""

    def __init__(self) -> None:
        self._client = AzurePricingClient()
        self._retirement_service = RetirementService(self._client)
        self._pricing_service = PricingService(self._client, self._retirement_service)
        self._sku_service = SKUService(self._pricing_service)
        self._tool_handlers = ToolHandlers(self._pricing_service, self._sku_service)

    async def __aenter__(self) -> "AzurePricingServer":
        """Async context manager entry."""
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._client.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def tool_handlers(self) -> ToolHandlers:
        """Get the tool handlers instance."""
        return self._tool_handlers


def create_server() -> tuple[Server, AzurePricingServer]:
    """Create and configure the MCP server instance."""
    server = Server("azure-pricing")
    pricing_server = AzurePricingServer()

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        """List available tools."""
        return get_tool_definitions()

    # Create a wrapper that manages the client session
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> Any:
        """Handle tool calls with proper session management."""
        async with pricing_server:
            handlers = pricing_server.tool_handlers
            
            if name == "azure_price_search":
                return await handlers.handle_price_search(arguments)
            elif name == "azure_price_compare":
                return await handlers.handle_price_compare(arguments)
            elif name == "azure_cost_estimate":
                return await handlers.handle_cost_estimate(arguments)
            elif name == "azure_discover_skus":
                return await handlers.handle_discover_skus(arguments)
            elif name == "azure_sku_discovery":
                return await handlers.handle_sku_discovery(arguments)
            elif name == "azure_region_recommend":
                return await handlers.handle_region_recommend(arguments)
            elif name == "azure_ri_pricing":
                return await handlers.handle_ri_pricing(arguments)
            elif name == "get_customer_discount":
                return await handlers.handle_customer_discount(arguments)
            else:
                from mcp.types import TextContent
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server, pricing_server


async def main() -> None:
    """Main entry point for the server."""
    import argparse

    parser = argparse.ArgumentParser(description="Azure Pricing MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport type: stdio (for local MCP clients) or http (for remote access)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind HTTP server (default: 127.0.0.1, use 0.0.0.0 for Docker)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for HTTP server (default: 8080)",
    )

    args, _ = parser.parse_known_args()

    server, _ = create_server()

    if args.transport == "http":
        # Use HTTP transport for remote access (Docker use case)
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import Response
        from starlette.routing import Mount, Route

        logger.info(f"Starting HTTP MCP server on {args.host}:{args.port}")

        sse = SseServerTransport("/messages/")

        async def handle_sse(request: Request) -> Response:
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                initialization_options = server.create_initialization_options(
                    notification_options=NotificationOptions(tools_changed=True)
                )
                await server.run(streams[0], streams[1], initialization_options)
            return Response()

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ]
        )

        import uvicorn

        config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
        server_instance = uvicorn.Server(config)
        await server_instance.serve()
    else:
        # Use stdio transport for local MCP clients (VS Code, Claude Desktop)
        logger.info("Starting stdio MCP server")
        async with stdio_server() as (read_stream, write_stream):
            initialization_options = server.create_initialization_options(
                notification_options=NotificationOptions(tools_changed=True)
            )
            await server.run(read_stream, write_stream, initialization_options)


def run() -> None:
    """Synchronous entry point for the console script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
