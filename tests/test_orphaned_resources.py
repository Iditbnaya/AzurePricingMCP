#!/usr/bin/env python3
"""Tests for orphaned Azure resources detection."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_pricing_mcp.formatters import format_orphaned_resources_response
from azure_pricing_mcp.services.orphaned import OrphanedResourcesService
from azure_pricing_mcp.services.orphaned_resources import (
    COST_LOOKBACK_DAYS,
    get_resource_cost_safe,
    scan_orphaned_resources,
    scan_orphaned_resources_all_subs,
)

# ---------------------------------------------------------------------------
# Helpers: build mock Azure SDK objects
# ---------------------------------------------------------------------------


def _make_disk(name, disk_id, managed_by=None):
    """Create a mock Azure disk object."""
    disk = MagicMock()
    disk.name = name
    disk.id = disk_id
    disk.managed_by = managed_by
    return disk


def _make_public_ip(name, ip_id, ip_configuration=None):
    """Create a mock Azure public IP object."""
    ip = MagicMock()
    ip.name = name
    ip.id = ip_id
    ip.ip_configuration = ip_configuration
    return ip


def _make_load_balancer(name, lb_id, backend_pools=None, frontend_configs=None):
    """Create a mock Azure load balancer object."""
    lb = MagicMock()
    lb.name = name
    lb.id = lb_id
    lb.backend_address_pools = backend_pools
    lb.frontend_ip_configurations = frontend_configs
    return lb


def _make_app_service_plan(name, plan_id, resource_group="rg-test"):
    """Create a mock Azure App Service Plan object."""
    plan = MagicMock()
    plan.name = name
    plan.id = plan_id
    plan.resource_group = resource_group
    return plan


def _make_web_app(name, server_farm_id):
    """Create a mock Azure Web App object."""
    app = MagicMock()
    app.name = name
    app.server_farm_id = server_farm_id
    return app


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUB_ID = "00000000-0000-0000-0000-000000000001"
DISK_ID = f"/subscriptions/{SUB_ID}/resourceGroups/rg-test/providers/Microsoft.Compute/disks/orphan-disk-1"
IP_ID = f"/subscriptions/{SUB_ID}/resourceGroups/rg-test/providers/Microsoft.Network/publicIPAddresses/orphan-ip-1"
LB_ID = f"/subscriptions/{SUB_ID}/resourceGroups/rg-test/providers/Microsoft.Network/loadBalancers/orphan-lb-1"
PLAN_ID = f"/subscriptions/{SUB_ID}/resourceGroups/rg-test/providers/Microsoft.Web/serverfarms/orphan-plan-1"


# ===========================================================================
# scan_orphaned_resources unit tests
# ===========================================================================


class TestScanOrphanedResources:
    """Unit tests for scan_orphaned_resources."""

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    def test_detects_unattached_disk(self, mock_cost):
        """Unattached disks (managed_by=None) are reported as orphaned."""
        compute = MagicMock()
        compute.disks.list.return_value = [_make_disk("disk1", DISK_ID)]
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = []

        result = scan_orphaned_resources(compute, network, SUB_ID, days=30)

        assert len(result) == 1
        assert result[0]["name"] == "disk1"
        assert result[0]["type"] == "disk"
        assert result[0]["id"] == DISK_ID
        assert result[0]["resource_group"] == "rg-test"

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    def test_skips_attached_disk(self, mock_cost):
        """Disks with managed_by set should NOT appear in results."""
        compute = MagicMock()
        compute.disks.list.return_value = [
            _make_disk("attached-disk", DISK_ID, managed_by="/subscriptions/.../vm1"),
        ]
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = []

        result = scan_orphaned_resources(compute, network, SUB_ID)

        assert len(result) == 0

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=5.50)
    def test_detects_unattached_public_ip(self, mock_cost):
        """Public IPs without ip_configuration are reported as orphaned."""
        compute = MagicMock()
        compute.disks.list.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = [
            _make_public_ip("ip1", IP_ID),
        ]
        network.load_balancers.list_all.return_value = []

        result = scan_orphaned_resources(compute, network, SUB_ID, days=60)

        assert len(result) == 1
        assert result[0]["name"] == "ip1"
        assert result[0]["type"] == "public_ip"
        assert result[0]["cost"] == 5.50
        assert result[0]["days"] == 60

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    def test_skips_attached_public_ip(self, mock_cost):
        """Public IPs with ip_configuration should NOT appear in results."""
        compute = MagicMock()
        compute.disks.list.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = [
            _make_public_ip("used-ip", IP_ID, ip_configuration=MagicMock()),
        ]
        network.load_balancers.list_all.return_value = []

        result = scan_orphaned_resources(compute, network, SUB_ID)

        assert len(result) == 0

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=12.0)
    def test_detects_orphaned_load_balancer_no_backends(self, mock_cost):
        """Load balancers with no backend pools are orphaned."""
        compute = MagicMock()
        compute.disks.list.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = [
            _make_load_balancer("lb1", LB_ID, backend_pools=None, frontend_configs=[MagicMock()]),
        ]

        result = scan_orphaned_resources(compute, network, SUB_ID, days=30)

        assert len(result) == 1
        assert result[0]["name"] == "lb1"
        assert result[0]["type"] == "load_balancer"
        assert result[0]["cost"] == 12.0

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    def test_detects_orphaned_load_balancer_no_frontends(self, mock_cost):
        """Load balancers with no frontend IP configurations are orphaned."""
        compute = MagicMock()
        compute.disks.list.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = [
            _make_load_balancer("lb2", LB_ID, backend_pools=[MagicMock()], frontend_configs=None),
        ]

        result = scan_orphaned_resources(compute, network, SUB_ID)

        assert len(result) == 1
        assert result[0]["type"] == "load_balancer"

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    def test_skips_healthy_load_balancer(self, mock_cost):
        """Load balancers with both backends and frontends are NOT orphaned."""
        compute = MagicMock()
        compute.disks.list.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = [
            _make_load_balancer(
                "healthy-lb",
                LB_ID,
                backend_pools=[MagicMock()],
                frontend_configs=[MagicMock()],
            ),
        ]

        result = scan_orphaned_resources(compute, network, SUB_ID)

        assert len(result) == 0

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    @patch("azure_pricing_mcp.services.orphaned_resources.DefaultAzureCredential")
    def test_detects_orphaned_app_service_plan(self, mock_cred, mock_cost):
        """App Service Plans with no attached web apps are orphaned."""
        compute = MagicMock()
        compute.disks.list.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = []

        mock_web_client = MagicMock()
        plan = _make_app_service_plan("plan1", PLAN_ID)
        mock_web_client.app_service_plans.list.return_value = [plan]
        # No web apps in the resource group
        mock_web_client.web_apps.list_by_resource_group.return_value = []

        # WebSiteManagementClient is imported lazily inside scan_orphaned_resources
        # via `from azure.mgmt.web import WebSiteManagementClient`.
        # We inject a mock module into sys.modules so the import resolves to our mock.
        mock_web_module = MagicMock()
        mock_web_module.WebSiteManagementClient = MagicMock(return_value=mock_web_client)
        with patch.dict(sys.modules, {"azure.mgmt.web": mock_web_module}):
            result = scan_orphaned_resources(compute, network, SUB_ID, days=30)

        assert any(r["type"] == "app_service_plan" for r in result)

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    @patch("azure_pricing_mcp.services.orphaned_resources.DefaultAzureCredential")
    def test_skips_app_service_plan_with_attached_apps(self, mock_cred, mock_cost):
        """App Service Plans with attached web apps are NOT orphaned."""
        compute = MagicMock()
        compute.disks.list.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = []

        mock_web_client = MagicMock()
        plan = _make_app_service_plan("plan-used", PLAN_ID, resource_group="rg-test")
        mock_web_client.app_service_plans.list.return_value = [plan]
        # Web app points to this plan
        mock_web_client.web_apps.list_by_resource_group.return_value = [
            _make_web_app("my-app", PLAN_ID),
        ]

        mock_web_module = MagicMock()
        mock_web_module.WebSiteManagementClient = MagicMock(return_value=mock_web_client)
        with patch.dict(sys.modules, {"azure.mgmt.web": mock_web_module}):
            result = scan_orphaned_resources(compute, network, SUB_ID, days=30)

        assert not any(r["type"] == "app_service_plan" for r in result)

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    def test_multiple_orphaned_resources(self, mock_cost):
        """Multiple orphaned resource types can be detected in one scan."""
        compute = MagicMock()
        compute.disks.list.return_value = [
            _make_disk("disk-a", DISK_ID),
            _make_disk("disk-b", DISK_ID.replace("orphan-disk-1", "orphan-disk-2")),
        ]
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = [
            _make_public_ip("ip-a", IP_ID),
        ]
        network.load_balancers.list_all.return_value = [
            _make_load_balancer("lb-a", LB_ID, backend_pools=None, frontend_configs=None),
        ]

        result = scan_orphaned_resources(compute, network, SUB_ID, days=30)

        types_found = {r["type"] for r in result}
        assert "disk" in types_found
        assert "public_ip" in types_found
        assert "load_balancer" in types_found
        assert len(result) == 4

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    def test_no_orphaned_resources(self, mock_cost):
        """An empty list is returned when nothing is orphaned."""
        compute = MagicMock()
        compute.disks.list.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = []

        result = scan_orphaned_resources(compute, network, SUB_ID)

        assert result == []

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=42.0)
    def test_cost_is_propagated(self, mock_cost):
        """The cost value returned by get_resource_cost_safe is correctly stored."""
        compute = MagicMock()
        compute.disks.list.return_value = [_make_disk("disk-cost", DISK_ID)]
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = []

        result = scan_orphaned_resources(compute, network, SUB_ID, days=90)

        assert result[0]["cost"] == 42.0
        assert result[0]["days"] == 90

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost_safe", return_value=0.0)
    def test_resource_group_extraction(self, mock_cost):
        """Resource group is correctly extracted from the resource ID."""
        custom_id = f"/subscriptions/{SUB_ID}/resourceGroups/my-custom-rg/providers/Microsoft.Compute/disks/d1"
        compute = MagicMock()
        compute.disks.list.return_value = [_make_disk("d1", custom_id)]
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.load_balancers.list_all.return_value = []

        result = scan_orphaned_resources(compute, network, SUB_ID)

        assert result[0]["resource_group"] == "my-custom-rg"


# ===========================================================================
# scan_orphaned_resources_all_subs tests
# ===========================================================================


class TestScanOrphanedResourcesAllSubs:
    """Tests for scan_orphaned_resources_all_subs."""

    @patch("azure_pricing_mcp.services.orphaned_resources.scan_orphaned_resources", return_value=[])
    @patch("azure_pricing_mcp.services.orphaned_resources.NetworkManagementClient")
    @patch("azure_pricing_mcp.services.orphaned_resources.ComputeManagementClient")
    @patch("azure_pricing_mcp.services.orphaned_resources.DefaultAzureCredential")
    @patch("azure_pricing_mcp.services.orphaned_resources.get_all_subscriptions")
    def test_all_subscriptions(self, mock_get_subs, mock_cred, mock_compute, mock_network, mock_scan):
        """All subscriptions are scanned when all_subscriptions=True."""
        mock_get_subs.return_value = [
            ("sub1", "Sub One"),
            ("sub2", "Sub Two"),
        ]

        results = scan_orphaned_resources_all_subs(days=30, all_subscriptions=True)

        assert len(results) == 2
        assert results[0]["subscription_id"] == "sub1"
        assert results[0]["subscription_name"] == "Sub One"
        assert results[1]["subscription_id"] == "sub2"
        assert mock_scan.call_count == 2

    @patch("azure_pricing_mcp.services.orphaned_resources.scan_orphaned_resources", return_value=[])
    @patch("azure_pricing_mcp.services.orphaned_resources.NetworkManagementClient")
    @patch("azure_pricing_mcp.services.orphaned_resources.ComputeManagementClient")
    @patch("azure_pricing_mcp.services.orphaned_resources.DefaultAzureCredential")
    @patch("azure_pricing_mcp.services.orphaned_resources.get_all_subscriptions")
    def test_single_subscription(self, mock_get_subs, mock_cred, mock_compute, mock_network, mock_scan):
        """Only first subscription is scanned when all_subscriptions=False."""
        mock_get_subs.return_value = [
            ("sub1", "Sub One"),
            ("sub2", "Sub Two"),
        ]

        results = scan_orphaned_resources_all_subs(days=60, all_subscriptions=False)

        assert len(results) == 1
        assert results[0]["subscription_id"] == "sub1"
        assert mock_scan.call_count == 1

    @patch("azure_pricing_mcp.services.orphaned_resources.NetworkManagementClient")
    @patch("azure_pricing_mcp.services.orphaned_resources.ComputeManagementClient")
    @patch("azure_pricing_mcp.services.orphaned_resources.DefaultAzureCredential")
    @patch("azure_pricing_mcp.services.orphaned_resources.get_all_subscriptions")
    def test_error_handling_per_subscription(self, mock_get_subs, mock_cred, mock_compute, mock_network):
        """Errors in one subscription don't stop scanning others."""
        mock_get_subs.return_value = [
            ("sub-fail", "Failing Sub"),
            ("sub-ok", "Good Sub"),
        ]
        # First call raises, second call succeeds
        mock_compute.side_effect = [Exception("auth error"), MagicMock()]
        mock_network.return_value = MagicMock()

        results = scan_orphaned_resources_all_subs(days=30, all_subscriptions=True)

        assert len(results) == 2
        assert "error" in results[0]
        assert "auth error" in results[0]["error"]
        # Second subscription should still have results (even if empty)
        assert "subscription_id" in results[1]


# ===========================================================================
# get_resource_cost_safe tests
# ===========================================================================


class TestGetResourceCostSafe:
    """Tests for get_resource_cost_safe."""

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost", return_value=123.45)
    def test_returns_cost_on_success(self, mock_get_cost):
        """Returns the cost when get_resource_cost succeeds."""
        cost = get_resource_cost_safe(SUB_ID, DISK_ID, days=30)

        assert cost == 123.45
        mock_get_cost.assert_called_once_with(SUB_ID, DISK_ID, 30)

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost", side_effect=Exception("API error"))
    def test_returns_zero_on_failure(self, mock_get_cost):
        """Returns 0.0 when get_resource_cost raises an exception."""
        cost = get_resource_cost_safe(SUB_ID, DISK_ID, days=30)

        assert cost == 0.0

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost", side_effect=Exception("API error"))
    def test_logs_error_when_logger_provided(self, mock_get_cost):
        """Debug message is logged when logger is provided and cost fails."""
        logger = MagicMock()

        cost = get_resource_cost_safe(SUB_ID, DISK_ID, days=30, logger=logger)

        assert cost == 0.0
        logger.debug.assert_called_once()

    @patch("azure_pricing_mcp.services.orphaned_resources.get_resource_cost", side_effect=Exception("API error"))
    def test_no_error_without_logger(self, mock_get_cost):
        """No exception is raised when logger is not provided."""
        cost = get_resource_cost_safe(SUB_ID, DISK_ID, days=30, logger=None)

        assert cost == 0.0


# ===========================================================================
# COST_LOOKBACK_DAYS constant test
# ===========================================================================


class TestConstants:
    """Tests for module-level constants."""

    def test_cost_lookback_days_value(self):
        """COST_LOOKBACK_DAYS should be 60."""
        assert COST_LOOKBACK_DAYS == 60


# ===========================================================================
# OrphanedResourcesService tests
# ===========================================================================


class TestOrphanedResourcesService:
    """Tests for the OrphanedResourcesService async wrapper."""

    @pytest.mark.asyncio
    @patch(
        "azure_pricing_mcp.services.orphaned.handle_find_orphaned_resources",
        return_value=[
            {
                "subscription_id": SUB_ID,
                "subscription_name": "Test Sub",
                "orphaned_resources": [
                    {
                        "name": "disk1",
                        "type": "disk",
                        "cost": 10.0,
                        "id": DISK_ID,
                        "days": 60,
                        "resource_group": "rg-test",
                    },
                ],
            }
        ],
    )
    async def test_find_orphaned_resources_default_args(self, mock_handler):
        """Service calls handler with correct default arguments."""
        service = OrphanedResourcesService()
        results = await service.find_orphaned_resources()

        mock_handler.assert_called_once_with({"days": 60, "all_subscriptions": True})
        assert len(results) == 1
        assert results[0]["subscription_id"] == SUB_ID

    @pytest.mark.asyncio
    @patch(
        "azure_pricing_mcp.services.orphaned.handle_find_orphaned_resources",
        return_value=[],
    )
    async def test_find_orphaned_resources_custom_args(self, mock_handler):
        """Service passes custom days and all_subscriptions to handler."""
        service = OrphanedResourcesService()
        results = await service.find_orphaned_resources(days=30, all_subscriptions=False)

        mock_handler.assert_called_once_with({"days": 30, "all_subscriptions": False})
        assert results == []

    @pytest.mark.asyncio
    @patch(
        "azure_pricing_mcp.services.orphaned.handle_find_orphaned_resources",
        side_effect=Exception("Azure auth failed"),
    )
    async def test_find_orphaned_resources_raises_on_error(self, mock_handler):
        """Service re-raises exceptions from the handler."""
        service = OrphanedResourcesService()

        with pytest.raises(Exception, match="Azure auth failed"):
            await service.find_orphaned_resources()


# ===========================================================================
# format_orphaned_resources_response tests
# ===========================================================================


class TestFormatOrphanedResourcesResponse:
    """Tests for the orphaned resources response formatter."""

    def test_empty_result(self):
        """Empty result list returns a fallback message."""
        output = format_orphaned_resources_response([])
        assert "No subscriptions found" in output or "no orphaned resources" in output.lower()

    def test_no_orphaned_resources_in_subscription(self):
        """A subscription with zero orphaned resources shows a clean message."""
        result = [
            {
                "subscription_id": SUB_ID,
                "subscription_name": "Clean Sub",
                "orphaned_resources": [],
            }
        ]
        output = format_orphaned_resources_response(result)

        assert "Clean Sub" in output
        assert "No orphaned resources found" in output
        assert "Total Orphaned Resources:** 0" in output

    def test_subscription_with_error(self):
        """Subscription errors are displayed in the output."""
        result = [
            {
                "subscription_id": SUB_ID,
                "subscription_name": "Broken Sub",
                "error": "Access denied",
            }
        ]
        output = format_orphaned_resources_response(result)

        assert "Broken Sub" in output
        assert "Access denied" in output

    def test_single_orphaned_resource(self):
        """A single orphaned resource is shown with correct details."""
        result = [
            {
                "subscription_id": SUB_ID,
                "subscription_name": "My Sub",
                "orphaned_resources": [
                    {
                        "name": "unused-disk",
                        "type": "disk",
                        "cost": 25.50,
                        "id": DISK_ID,
                        "days": 60,
                        "resource_group": "rg-test",
                    },
                ],
            }
        ]
        output = format_orphaned_resources_response(result)

        assert "My Sub" in output
        assert "unused-disk" in output
        assert "rg-test" in output
        assert "$25.50" in output
        assert "Total Orphaned Resources:** 1" in output
        assert "Total Estimated Cost:** $25.50" in output

    def test_multiple_resources_sorted_by_cost(self):
        """Resources are sorted by cost in descending order."""
        result = [
            {
                "subscription_id": SUB_ID,
                "subscription_name": "Sub",
                "orphaned_resources": [
                    {
                        "name": "cheap",
                        "type": "public_ip",
                        "cost": 1.0,
                        "id": IP_ID,
                        "days": 60,
                        "resource_group": "rg",
                    },
                    {
                        "name": "expensive",
                        "type": "disk",
                        "cost": 100.0,
                        "id": DISK_ID,
                        "days": 60,
                        "resource_group": "rg",
                    },
                    {
                        "name": "medium",
                        "type": "load_balancer",
                        "cost": 50.0,
                        "id": LB_ID,
                        "days": 60,
                        "resource_group": "rg",
                    },
                ],
            }
        ]
        output = format_orphaned_resources_response(result)

        # Expensive should appear before cheap in the table
        pos_expensive = output.index("expensive")
        pos_medium = output.index("medium")
        pos_cheap = output.index("cheap")
        assert pos_expensive < pos_medium < pos_cheap

    def test_total_cost_aggregation(self):
        """Total cost is correctly summed across all resources."""
        result = [
            {
                "subscription_id": "sub1",
                "subscription_name": "Sub 1",
                "orphaned_resources": [
                    {"name": "r1", "type": "disk", "cost": 10.0, "id": DISK_ID, "days": 60, "resource_group": "rg"},
                ],
            },
            {
                "subscription_id": "sub2",
                "subscription_name": "Sub 2",
                "orphaned_resources": [
                    {"name": "r2", "type": "public_ip", "cost": 20.0, "id": IP_ID, "days": 60, "resource_group": "rg"},
                ],
            },
        ]
        output = format_orphaned_resources_response(result)

        assert "Total Orphaned Resources:** 2" in output
        assert "Total Estimated Cost:** $30.00" in output

    def test_recommendations_section_present(self):
        """The recommendations section is included in the output."""
        result = [
            {
                "subscription_id": SUB_ID,
                "subscription_name": "Sub",
                "orphaned_resources": [
                    {"name": "r1", "type": "disk", "cost": 0.0, "id": DISK_ID, "days": 60, "resource_group": "rg"},
                ],
            }
        ]
        output = format_orphaned_resources_response(result)

        assert "Recommendations" in output
        assert "Review" in output
        assert "Delete" in output

    def test_resource_type_emojis(self):
        """Each resource type gets the correct emoji prefix."""
        result = [
            {
                "subscription_id": SUB_ID,
                "subscription_name": "Sub",
                "orphaned_resources": [
                    {"name": "d1", "type": "disk", "cost": 0.0, "id": DISK_ID, "days": 60, "resource_group": "rg"},
                    {"name": "ip1", "type": "public_ip", "cost": 0.0, "id": IP_ID, "days": 60, "resource_group": "rg"},
                    {
                        "name": "asp1",
                        "type": "app_service_plan",
                        "cost": 0.0,
                        "id": PLAN_ID,
                        "days": 60,
                        "resource_group": "rg",
                    },
                    {
                        "name": "lb1",
                        "type": "load_balancer",
                        "cost": 0.0,
                        "id": LB_ID,
                        "days": 60,
                        "resource_group": "rg",
                    },
                ],
            }
        ]
        output = format_orphaned_resources_response(result)

        assert "\U0001f4be" in output  # disk
        assert "\U0001f310" in output  # public ip
        assert "\u2699" in output  # app service plan
        assert "\u2696" in output  # load balancer

    def test_subscriptions_with_orphans_count(self):
        """Subscriptions with orphans are counted correctly."""
        result = [
            {
                "subscription_id": "sub1",
                "subscription_name": "Has Orphans",
                "orphaned_resources": [
                    {"name": "r1", "type": "disk", "cost": 0.0, "id": DISK_ID, "days": 60, "resource_group": "rg"},
                ],
            },
            {
                "subscription_id": "sub2",
                "subscription_name": "No Orphans",
                "orphaned_resources": [],
            },
            {
                "subscription_id": "sub3",
                "subscription_name": "Errored",
                "error": "timeout",
            },
        ]
        output = format_orphaned_resources_response(result)

        assert "Subscriptions Scanned:** 3" in output
        assert "Subscriptions with Orphans:** 1" in output


# ===========================================================================
# handle_find_orphaned_resources (MCP handler) tests
# ===========================================================================


class TestHandleFindOrphanedResourcesMCP:
    """Tests for the MCP server handler integration."""

    @pytest.fixture
    def tool_handlers(self):
        """Create ToolHandlers with mocked services for orphaned resources."""
        from azure_pricing_mcp.handlers import ToolHandlers

        mock_pricing = AsyncMock()
        mock_sku = AsyncMock()
        handlers = ToolHandlers(mock_pricing, mock_sku)
        return handlers

    def test_lazy_initialization(self, tool_handlers):
        """OrphanedResourcesService is lazily created on first access."""
        assert tool_handlers._orphaned_resources_service is None
        service = tool_handlers._get_orphaned_resources_service()
        assert service is not None
        assert isinstance(service, OrphanedResourcesService)

    def test_lazy_initialization_reuses_instance(self, tool_handlers):
        """Subsequent calls return the same service instance."""
        service1 = tool_handlers._get_orphaned_resources_service()
        service2 = tool_handlers._get_orphaned_resources_service()
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_handler_returns_text_content(self, tool_handlers):
        """The handler returns a list with TextContent objects."""
        mock_service = AsyncMock(spec=OrphanedResourcesService)
        mock_service.find_orphaned_resources.return_value = []
        tool_handlers._orphaned_resources_service = mock_service

        result = await tool_handlers.handle_find_orphaned_resources({})

        assert len(result) == 1
        assert hasattr(result[0], "text")
        assert result[0].type == "text"

    @pytest.mark.asyncio
    async def test_handler_passes_default_arguments(self, tool_handlers):
        """The handler uses default days=60 and all_subscriptions=True."""
        mock_service = AsyncMock(spec=OrphanedResourcesService)
        mock_service.find_orphaned_resources.return_value = []
        tool_handlers._orphaned_resources_service = mock_service

        await tool_handlers.handle_find_orphaned_resources({})

        mock_service.find_orphaned_resources.assert_called_once_with(
            days=60,
            all_subscriptions=True,
        )

    @pytest.mark.asyncio
    async def test_handler_passes_custom_arguments(self, tool_handlers):
        """The handler forwards custom arguments to the service."""
        mock_service = AsyncMock(spec=OrphanedResourcesService)
        mock_service.find_orphaned_resources.return_value = []
        tool_handlers._orphaned_resources_service = mock_service

        await tool_handlers.handle_find_orphaned_resources({"days": 90, "all_subscriptions": False})

        mock_service.find_orphaned_resources.assert_called_once_with(
            days=90,
            all_subscriptions=False,
        )

    @pytest.mark.asyncio
    async def test_handler_formats_response(self, tool_handlers):
        """The handler formats actual orphaned resources into readable output."""
        mock_service = AsyncMock(spec=OrphanedResourcesService)
        mock_service.find_orphaned_resources.return_value = [
            {
                "subscription_id": SUB_ID,
                "subscription_name": "Test",
                "orphaned_resources": [
                    {
                        "name": "disk1",
                        "type": "disk",
                        "cost": 15.0,
                        "id": DISK_ID,
                        "days": 60,
                        "resource_group": "rg-test",
                    },
                ],
            }
        ]
        tool_handlers._orphaned_resources_service = mock_service

        result = await tool_handlers.handle_find_orphaned_resources({})

        assert "disk1" in result[0].text
        assert "$15.00" in result[0].text
        assert "rg-test" in result[0].text
