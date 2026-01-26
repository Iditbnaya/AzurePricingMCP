#!/usr/bin/env python3
"""Test the MCP server by simulating stdin/stdout communication."""

import pytest

from azure_pricing_mcp.client import AzurePricingClient
from azure_pricing_mcp.handlers import ToolHandlers
from azure_pricing_mcp.server import create_server
from azure_pricing_mcp.services import PricingService, SKUService
from azure_pricing_mcp.services.retirement import RetirementService


@pytest.fixture
async def services():
    """Create all services for testing."""
    async with AzurePricingClient() as client:
        retirement_service = RetirementService(client)
        pricing_service = PricingService(client, retirement_service)
        sku_service = SKUService(pricing_service)
        tool_handlers = ToolHandlers(pricing_service, sku_service)
        yield {
            "pricing": pricing_service,
            "sku": sku_service,
            "handlers": tool_handlers,
        }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_server(services):
    """Test the MCP server tool handlers."""
    # Simulate tool call through the handler
    result = await services["handlers"].handle_price_search(
        {
            "service_name": "Virtual Machines",
            "sku_name": "Standard_F16",
            "price_type": "Consumption",
            "limit": 10,
        },
    )

    print("Tool call result:")
    for item in result:
        print(f"Type: {type(item)}")
        if hasattr(item, "text"):
            print(f"Text length: {len(item.text)}")
            print(f"Text preview: {item.text[:200]}...")

    assert len(result) > 0
    assert hasattr(result[0], "text")


@pytest.mark.asyncio
async def test_server_creation():
    """Test that server can be created."""
    server, pricing_server = create_server()
    assert server is not None
    assert server.name == "azure-pricing"
    assert pricing_server is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_tool_handlers(services):
    """Test all tool handlers work."""
    # Test price search
    result = await services["handlers"].handle_price_search({"service_name": "Virtual Machines", "limit": 5})
    assert len(result) > 0

    # Test price compare
    result = await services["handlers"].handle_price_compare(
        {"service_name": "Virtual Machines", "regions": ["eastus", "westus"]}
    )
    assert len(result) > 0

    # Test cost estimate
    search = await services["pricing"].search_prices(service_name="Virtual Machines", region="eastus", limit=1)
    if search["items"]:
        sku = search["items"][0]["skuName"]
        result = await services["handlers"].handle_cost_estimate(
            {"service_name": "Virtual Machines", "sku_name": sku, "region": "eastus"}
        )
        assert len(result) > 0

    # Test discover SKUs
    result = await services["handlers"].handle_discover_skus({"service_name": "Virtual Machines", "limit": 10})
    assert len(result) > 0

    # Test SKU discovery
    result = await services["handlers"].handle_sku_discovery({"service_hint": "vm"})
    assert len(result) > 0

    # Test customer discount
    result = await services["handlers"].handle_customer_discount({})
    assert len(result) > 0
