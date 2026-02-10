"""Unit tests for orphaned resources feature.

Tests cover:
- OrphanedResourceScanner (scanning logic, cost lookup, auth checks)
- OrphanedResourcesService (async service wrapper)
- format_orphaned_resources_response (formatter output)
- Tool definition presence
- Handler wiring
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_pricing_mcp.formatters import format_orphaned_resources_response
from azure_pricing_mcp.handlers import ToolHandlers
from azure_pricing_mcp.services.orphaned import OrphanedResourcesService
from azure_pricing_mcp.services.orphaned_resources import (
    COST_LOOKBACK_DAYS,
    OrphanedResourceScanner,
)
from azure_pricing_mcp.tools import get_tool_definitions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_credential_manager():
    """Create a mock credential manager that appears authenticated."""
    mgr = MagicMock()
    mgr.get_initialization_error.return_value = None
    mgr.is_authenticated.return_value = True
    mgr.get_token.return_value = "fake-token"
    mgr.get_authentication_help_message.return_value = "Run: az login"
    mgr.get_required_permissions_message.return_value = "Reader role required"
    return mgr


@pytest.fixture
def unauthenticated_credential_manager():
    """Create a mock credential manager that is NOT authenticated."""
    mgr = MagicMock()
    mgr.get_initialization_error.return_value = None
    mgr.is_authenticated.return_value = False
    mgr.get_authentication_help_message.return_value = "Run: az login"
    return mgr


@pytest.fixture
def scanner(mock_credential_manager):
    return OrphanedResourceScanner(credential_manager=mock_credential_manager)


@pytest.fixture
def service(mock_credential_manager):
    return OrphanedResourcesService(credential_manager=mock_credential_manager)


# ---------------------------------------------------------------------------
# Tool definition tests
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_find_orphaned_resources_tool_exists(self):
        """The find_orphaned_resources tool must be registered."""
        tools = get_tool_definitions()
        names = [t.name for t in tools]
        assert "find_orphaned_resources" in names

    def test_find_orphaned_resources_schema(self):
        """Schema must declare days (int) and all_subscriptions (bool)."""
        tools = get_tool_definitions()
        tool = next(t for t in tools if t.name == "find_orphaned_resources")
        props = tool.inputSchema["properties"]
        assert "days" in props
        assert props["days"]["type"] == "integer"
        assert "all_subscriptions" in props
        assert props["all_subscriptions"]["type"] == "boolean"


# ---------------------------------------------------------------------------
# Scanner – authentication
# ---------------------------------------------------------------------------


class TestScannerAuth:
    @pytest.mark.asyncio
    async def test_scan_returns_auth_error_when_not_authenticated(self, unauthenticated_credential_manager):
        """Scanner.scan() should return an error dict when unauthenticated."""
        scanner = OrphanedResourceScanner(credential_manager=unauthenticated_credential_manager)
        result = await scanner.scan()
        assert result["error"] == "authentication_required"
        assert "help" in result

    @pytest.mark.asyncio
    async def test_scan_returns_auth_error_on_init_failure(self):
        """Scanner.scan() should surface initialization errors."""
        mgr = MagicMock()
        mgr.get_initialization_error.return_value = "azure-identity not installed"
        mgr.get_authentication_help_message.return_value = "Install it"
        scanner = OrphanedResourceScanner(credential_manager=mgr)
        result = await scanner.scan()
        assert result["error"] == "authentication_required"


# ---------------------------------------------------------------------------
# Scanner – subscription handling (review comment #3)
# ---------------------------------------------------------------------------


class TestScannerSubscriptions:
    @pytest.mark.asyncio
    async def test_scan_handles_empty_subscriptions(self, scanner):
        """Scanner must not crash on an empty subscription list."""
        scanner._get_subscriptions = AsyncMock(return_value=[])
        result = await scanner.scan()
        assert result["total_orphaned"] == 0
        assert "No accessible" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_scan_all_subscriptions_false_uses_first_only(self, scanner):
        """all_subscriptions=False should scope to the first subscription."""
        subs = [
            {"id": "sub-1", "name": "First"},
            {"id": "sub-2", "name": "Second"},
        ]
        scanner._get_subscriptions = AsyncMock(return_value=subs)
        scanner._execute_resource_graph_query = AsyncMock(return_value={"data": []})

        await scanner.scan(all_subscriptions=False)

        # Verify only sub-1 was passed to graph queries
        for call in scanner._execute_resource_graph_query.call_args_list:
            sub_ids = call[1].get("subscription_ids") or call[0][1]
            assert sub_ids == ["sub-1"]

    @pytest.mark.asyncio
    async def test_scan_subscription_api_error_propagates(self, scanner):
        """If subscription listing fails, error dict is returned directly."""
        scanner._get_subscriptions = AsyncMock(return_value={"error": "api_error", "message": "forbidden"})
        result = await scanner.scan()
        assert result["error"] == "api_error"


# ---------------------------------------------------------------------------
# Scanner – resource graph query failure handling
# ---------------------------------------------------------------------------


class TestScannerResourceGraph:
    @pytest.mark.asyncio
    async def test_partial_graph_failure_does_not_abort(self, scanner):
        """If one resource type query fails, others still proceed."""
        subs = [{"id": "sub-1", "name": "Test"}]
        scanner._get_subscriptions = AsyncMock(return_value=subs)
        scanner._get_resource_cost = AsyncMock(return_value=0.0)

        call_count = 0

        async def mixed_results(query, subscription_ids=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"error": "api_error", "message": "bad query"}
            return {
                "data": [
                    {
                        "id": f"/subs/sub-1/rg/rg1/providers/x/{call_count}",
                        "name": f"res-{call_count}",
                        "type": "test",
                        "location": "eastus",
                        "resourceGroup": "rg1",
                        "subscriptionId": "sub-1",
                    }
                ]
            }

        scanner._execute_resource_graph_query = mixed_results
        result = await scanner.scan()
        # 5 queries total, first fails, other 4 each return 1 resource
        assert result["total_orphaned"] == 4


# ---------------------------------------------------------------------------
# Scanner – cost lookup
# ---------------------------------------------------------------------------


class TestScannerCostLookup:
    @pytest.mark.asyncio
    async def test_cost_is_summed_correctly(self, scanner):
        subs = [{"id": "sub-1", "name": "Test"}]
        scanner._get_subscriptions = AsyncMock(return_value=subs)
        scanner._execute_resource_graph_query = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "/subs/sub-1/rg/rg1/providers/x/disk1",
                        "name": "disk1",
                        "type": "microsoft.compute/disks",
                        "location": "eastus",
                        "resourceGroup": "rg1",
                        "subscriptionId": "sub-1",
                    },
                    {
                        "id": "/subs/sub-1/rg/rg1/providers/x/disk2",
                        "name": "disk2",
                        "type": "microsoft.compute/disks",
                        "location": "eastus",
                        "resourceGroup": "rg1",
                        "subscriptionId": "sub-1",
                    },
                ]
            }
        )
        scanner._get_resource_cost = AsyncMock(return_value=12.50)

        result = await scanner.scan(days=30)
        # 5 queries × 2 resources each × $12.50 = $125.00
        assert result["total_estimated_cost"] == 125.00
        assert result["lookback_days"] == 30

    @pytest.mark.asyncio
    async def test_cost_none_treated_as_zero(self, scanner):
        """If cost lookup returns None, total should not blow up."""
        subs = [{"id": "sub-1", "name": "Test"}]
        scanner._get_subscriptions = AsyncMock(return_value=subs)
        scanner._execute_resource_graph_query = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "/subs/sub-1/rg/rg1/providers/x/disk1",
                        "name": "disk1",
                        "type": "microsoft.compute/disks",
                        "location": "eastus",
                        "resourceGroup": "rg1",
                        "subscriptionId": "sub-1",
                    }
                ]
            }
        )
        scanner._get_resource_cost = AsyncMock(return_value=None)

        result = await scanner.scan()
        assert result["total_estimated_cost"] == 0.0


# ---------------------------------------------------------------------------
# OrphanedResourcesService (review comment #5 — genuinely async)
# ---------------------------------------------------------------------------


class TestOrphanedResourcesService:
    @pytest.mark.asyncio
    async def test_delegates_to_scanner(self, service):
        """Service.find_orphaned_resources must await the scanner."""
        expected = {
            "subscriptions": [],
            "total_orphaned": 0,
            "total_estimated_cost": 0.0,
            "lookback_days": 60,
        }
        service._scanner.scan = AsyncMock(return_value=expected)

        result = await service.find_orphaned_resources(days=30, all_subscriptions=False)
        service._scanner.scan.assert_awaited_once_with(days=30, all_subscriptions=False)
        assert result == expected

    @pytest.mark.asyncio
    async def test_passes_all_subscriptions_flag(self, service):
        """Service must thread through the all_subscriptions parameter (review #2)."""
        service._scanner.scan = AsyncMock(return_value={"total_orphaned": 0, "subscriptions": []})
        await service.find_orphaned_resources(all_subscriptions=False)
        _, kwargs = service._scanner.scan.call_args
        assert kwargs["all_subscriptions"] is False


# ---------------------------------------------------------------------------
# Formatter (review comment #7 — by_type must be used)
# ---------------------------------------------------------------------------


class TestFormatter:
    def test_no_orphans_message(self):
        result = {
            "subscriptions": [{"subscription_id": "s1", "orphaned_resources": []}],
            "total_orphaned": 0,
            "total_estimated_cost": 0.0,
            "lookback_days": 60,
            "currency": "USD",
        }
        output = format_orphaned_resources_response(result)
        assert "No Orphaned Resources Found" in output

    def test_groups_by_type_in_output(self):
        """Review comment #7: by_type grouping must produce per-type sections."""
        result = {
            "subscriptions": [
                {
                    "subscription_id": "sub-1",
                    "subscription_name": "Test",
                    "orphaned_resources": [
                        {
                            "name": "disk1",
                            "orphan_type": "Unattached Disk",
                            "resourceGroup": "rg1",
                            "location": "eastus",
                            "estimated_cost_usd": 10.0,
                        },
                        {
                            "name": "nic1",
                            "orphan_type": "Orphaned NIC",
                            "resourceGroup": "rg1",
                            "location": "eastus",
                            "estimated_cost_usd": 0.0,
                        },
                        {
                            "name": "disk2",
                            "orphan_type": "Unattached Disk",
                            "resourceGroup": "rg2",
                            "location": "westus2",
                            "estimated_cost_usd": 5.50,
                        },
                    ],
                }
            ],
            "total_orphaned": 3,
            "total_estimated_cost": 15.50,
            "lookback_days": 60,
            "currency": "USD",
            "note": "Scanned 1 subscription(s).",
        }
        output = format_orphaned_resources_response(result)

        # Must contain per-type section headers
        assert "Unattached Disk (2)" in output
        assert "Orphaned NIC (1)" in output
        # Summary table
        assert "| Orphaned NIC | 1 |" in output
        assert "| Unattached Disk | 2 |" in output
        # Detail rows
        assert "disk1" in output
        assert "disk2" in output
        assert "nic1" in output

    def test_error_result_formatted(self):
        """Auth error dicts should render via _format_spot_error."""
        result = {
            "error": "authentication_required",
            "message": "Azure auth required.",
            "help": "Run: az login",
        }
        output = format_orphaned_resources_response(result)
        assert "Authentication Required" in output

    def test_cost_none_shows_na(self):
        """Resources with None cost should display N/A."""
        result = {
            "subscriptions": [
                {
                    "subscription_id": "sub-1",
                    "subscription_name": "Test",
                    "orphaned_resources": [
                        {
                            "name": "ip1",
                            "orphan_type": "Orphaned Public IP",
                            "resourceGroup": "rg1",
                            "location": "eastus",
                            "estimated_cost_usd": None,
                        },
                    ],
                }
            ],
            "total_orphaned": 1,
            "total_estimated_cost": 0.0,
            "lookback_days": 60,
            "currency": "USD",
            "note": "",
        }
        output = format_orphaned_resources_response(result)
        assert "N/A" in output


# ---------------------------------------------------------------------------
# Handler integration
# ---------------------------------------------------------------------------


class TestHandler:
    @pytest.mark.asyncio
    async def test_handler_exists_on_tool_handlers(self):
        """ToolHandlers must expose handle_find_orphaned_resources."""
        pricing = MagicMock()
        sku = MagicMock()
        handlers = ToolHandlers(pricing, sku)
        assert hasattr(handlers, "handle_find_orphaned_resources")

    @pytest.mark.asyncio
    async def test_handler_returns_text_content(self):
        """Handler must return a list of TextContent."""
        pricing = MagicMock()
        sku = MagicMock()
        mock_orphaned = MagicMock()
        mock_orphaned.find_orphaned_resources = AsyncMock(
            return_value={
                "subscriptions": [],
                "total_orphaned": 0,
                "total_estimated_cost": 0.0,
                "lookback_days": 60,
                "currency": "USD",
            }
        )
        handlers = ToolHandlers(pricing, sku, orphaned_service=mock_orphaned)
        result = await handlers.handle_find_orphaned_resources({"days": 30, "all_subscriptions": False})
        assert len(result) == 1
        assert result[0].type == "text"
        assert "No Orphaned Resources Found" in result[0].text

    @pytest.mark.asyncio
    async def test_handler_lazy_creates_service(self):
        """If no orphaned_service provided, handler should create one lazily."""
        pricing = MagicMock()
        sku = MagicMock()
        handlers = ToolHandlers(pricing, sku)
        svc = handlers._get_orphaned_service()
        assert isinstance(svc, OrphanedResourcesService)
        # Second call returns same instance
        assert handlers._get_orphaned_service() is svc


# ---------------------------------------------------------------------------
# Default lookback constant
# ---------------------------------------------------------------------------


class TestConstants:
    def test_default_lookback_days(self):
        assert COST_LOOKBACK_DAYS == 60
