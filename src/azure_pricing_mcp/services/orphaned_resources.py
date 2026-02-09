"""Orphand resources finder for Pricing MCP Server."""

try:
    from azure.mgmt.resource.subscriptions import SubscriptionClient
except ImportError:
    from azure.mgmt.subscription import SubscriptionClient

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from datetime import datetime, timedelta
import requests
import json
import os

# Note: azure.mgmt.web, azure.mgmt.costmanagement, azure.mgmt.resourcegraph
# are imported lazily when needed to avoid requiring them at module import time

COST_LOOKBACK_DAYS = 60  
def get_all_subscriptions():
    credential = DefaultAzureCredential()
    sub_client = SubscriptionClient(credential)
    subs = []
    for sub in sub_client.subscriptions.list():
        sub_id = getattr(sub, 'subscription_id', None) or getattr(sub, 'id', 'Unknown')
        sub_name = getattr(sub, 'display_name', None) or sub_id
        subs.append((sub_id, sub_name))
    return subs


def scan_orphaned_resources_all_subs(days=60, all_subscriptions=True):
    results = []
    subs = get_all_subscriptions() if all_subscriptions else [get_all_subscriptions()[0]]
    for sub_id, sub_name in subs:
        try:
            compute_client = ComputeManagementClient(DefaultAzureCredential(), sub_id)
            network_client = NetworkManagementClient(DefaultAzureCredential(), sub_id)
            orphaned = scan_orphaned_resources(compute_client, network_client, sub_id, days=days)
            results.append({
                "subscription_id": sub_id,
                "subscription_name": sub_name,
                "orphaned_resources": orphaned
            })
        except Exception as e:
            results.append({
                "subscription_id": sub_id,
                "subscription_name": sub_name,
                "error": str(e)
            })
    return results

def automate_find_orphaned_resources_all_subs(api_url: str, days: int = 30):
    payload = {
        "all_subscriptions": True,
        "days": days
    }
    response = requests.post(f"{api_url}/find_orphaned_resources", json=payload)
    print(response.text)

def prompt_user_for_orphaned_resource_scan():
    subs = get_all_subscriptions()
    print("Select a subscription to scan for orphaned resources:")
    for idx, (sub_id, sub_name) in enumerate(subs, 1):
        print(f"{idx}. {sub_name} ({sub_id})")
    print("a. All subscriptions")
    print("t. Top 10 orphaned resources by cost (across all subscriptions)")
    choice = input("Enter number, 'a' for all, or 't' for top 10: ").strip().lower()

    if choice == 'a':
        results = scan_orphaned_resources_all_subs()
        print("\nResults for all subscriptions:")
        for res in results:
            print(f"\nSubscription: {res['subscription_name']} ({res['subscription_id']})")
            if 'error' in res:
                print(f"  Error: {res['error']}")
            else:
                for r in res['orphaned_resources']:
                    print(f"  - {r}")
    elif choice == 't':
        results = scan_orphaned_resources_all_subs()
        all_orphaned = []
        for res in results:
            if 'orphaned_resources' in res:
                all_orphaned.extend(res['orphaned_resources'])
        # Assume each orphaned resource is a dict with 'cost' key
        top10 = sorted(all_orphaned, key=lambda x: x.get('cost', 0), reverse=True)[:10]
        print("\nTop 10 orphaned resources by cost:")
        for r in top10:
            print(r)
    else:
        try:
            idx = int(choice) - 1
            sub_id, sub_name = subs[idx]
            compute_client = ComputeManagementClient(DefaultAzureCredential(), sub_id)
            network_client = NetworkManagementClient(DefaultAzureCredential(), sub_id)
            orphaned = scan_orphaned_resources(compute_client, network_client, sub_id)
            print(f"\nResults for {sub_name} ({sub_id}):")
            for r in orphaned:
                print(f"  - {r}")
        except Exception as e:
            print(f"Invalid selection or error: {e}")

def scan_orphaned_resources(compute_client, network_client, subscription_id, days=30):
    import logging
    logger = logging.getLogger(__name__)

    orphaned_resources = []

    # Unattached disks
    logger.info("Scanning for unattached disks...")
    for disk in compute_client.disks.list():
        if not disk.managed_by:
            cost = get_resource_cost_safe(subscription_id, disk.id, days, logger)
            orphaned_resources.append({
                'name': disk.name,
                'type': 'disk',
                'cost': cost,
                'id': disk.id,
                'days': days,
                'resource_group': disk.id.split('/')[4] if '/' in disk.id else 'Unknown'
            })
            logger.info(f"Found orphaned disk: {disk.name} (cost: ${cost:.2f})")

    # Unattached public IPs
    logger.info("Scanning for unattached public IPs...")
    for ip in network_client.public_ip_addresses.list_all():
        if not ip.ip_configuration:
            cost = get_resource_cost_safe(subscription_id, ip.id, days, logger)
            orphaned_resources.append({
                'name': ip.name,
                'type': 'public_ip',
                'cost': cost,
                'id': ip.id,
                'days': days,
                'resource_group': ip.id.split('/')[4] if '/' in ip.id else 'Unknown'
            })
            logger.info(f"Found orphaned public IP: {ip.name} (cost: ${cost:.2f})")

    # Orphaned App Service Plans (no web apps attached)
    logger.info("Scanning for orphaned app service plans...")
    try:
        from azure.mgmt.web import WebSiteManagementClient
        web_client = WebSiteManagementClient(DefaultAzureCredential(), subscription_id)
        for plan in web_client.app_service_plans.list():
            if plan.resource_group:
                web_apps = list(web_client.web_apps.list_by_resource_group(plan.resource_group))
                attached = any(app.server_farm_id == plan.id for app in web_apps)
                if not attached:
                    cost = get_resource_cost_safe(subscription_id, plan.id, days, logger)
                    orphaned_resources.append({
                        'name': plan.name,
                        'type': 'app_service_plan',
                        'cost': cost,
                        'id': plan.id,
                        'days': days,
                        'resource_group': plan.resource_group
                    })
                    logger.info(f"Found orphaned app service plan: {plan.name} (cost: ${cost:.2f})")
    except Exception as e:
        logger.warning(f"Error scanning app service plans: {e}")

    # Orphaned Load Balancers
    logger.info("Scanning for orphaned load balancers...")
    for lb in network_client.load_balancers.list_all():
        if not lb.backend_address_pools or not lb.frontend_ip_configurations:
            cost = get_resource_cost_safe(subscription_id, lb.id, days, logger)
            orphaned_resources.append({
                'name': lb.name,
                'type': 'load_balancer',
                'cost': cost,
                'id': lb.id,
                'days': days,
                'resource_group': lb.id.split('/')[4] if '/' in lb.id else 'Unknown'
            })
            logger.info(f"Found orphaned load balancer: {lb.name} (cost: ${cost:.2f})")

    logger.info(f"Total orphaned resources found: {len(orphaned_resources)}")
    return orphaned_resources

def load_resource_types(filepath=None):
    if filepath is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(current_dir, 'services', 'resource_types.json')
    with open(filepath, 'r') as f:
        return json.load(f)

def find_orphaned_resources_auto(days=30, all_subscriptions=True):
    from azure.mgmt.resourcegraph import ResourceGraphClient
    from azure.mgmt.resourcegraph.models import QueryRequest

    resource_types = load_resource_types()
    credential = DefaultAzureCredential()
    graph_client = ResourceGraphClient(credential)
    subs = [sub_id for sub_id, _ in get_all_subscriptions()] if all_subscriptions else [get_all_subscriptions()[0][0]]
    results = {}
    for resource_type in resource_types:
        query = f"Resources | where type =~ '{resource_type}' and (properties.lastModifiedTime >= ago({days}d) or properties.creationTime >= ago({days}d))"
        query_request = QueryRequest(subscriptions=subs, query=query)
        res = graph_client.resources(query_request)
        results[resource_type] = res.data
    return results

def get_resource_cost_safe(subscription_id, resource_id, days=30, logger=None):
    """Safely get resource cost with error handling.

    Args:
        subscription_id: Azure subscription ID
        resource_id: Full resource ID
        days: Number of days to look back
        logger: Optional logger for debugging

    Returns:
        float: Total cost or 0.0 if unable to calculate
    """
    try:
        return get_resource_cost(subscription_id, resource_id, days)
    except Exception as e:
        if logger:
            logger.debug(f"Unable to get cost for {resource_id}: {e}")
        # Return 0.0 if cost calculation fails (common for resources with no usage)
        return 0.0


def get_resource_cost(subscription_id, resource_id, days=30):
    """Get the cost of a specific Azure resource over the past N days.

    Uses Azure Cost Management API to query actual costs. This requires
    the 'azure-mgmt-costmanagement' package to be installed.

    Args:
        subscription_id: Azure subscription ID
        resource_id: Full resource ID (e.g., /subscriptions/.../resourceGroups/.../providers/...)
        days: Number of days to look back (default: 30)

    Returns:
        float: Total cost for the resource over the specified period

    Raises:
        Exception: If cost query fails or resource not found
    """
    from azure.mgmt.costmanagement import CostManagementClient
    from azure.mgmt.costmanagement.models import (
        QueryDefinition,
        QueryDataset,
        QueryAggregation,
        QueryTimePeriod,
        QueryFilter,
        QueryComparisonExpression
    )

    credential = DefaultAzureCredential()
    cost_client = CostManagementClient(credential, "https://management.azure.com")

    # Use the subscription scope for the query
    scope = f"/subscriptions/{subscription_id}"

    # Build query to filter by resource ID
    query_filter = QueryFilter(
        dimensions=QueryComparisonExpression(
            name="ResourceId",
            operator="In",
            values=[resource_id]
        )
    )

    # Build the cost query
    query_def = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(
            from_property=datetime.utcnow() - timedelta(days=days),
            to=datetime.utcnow()
        ),
        dataset=QueryDataset(
            granularity="None",
            aggregation={
                "totalCost": QueryAggregation(
                    name="Cost",
                    function="Sum"
                )
            },
            filter=query_filter
        )
    )

    try:
        result = cost_client.query.usage(scope, parameters=query_def)
        total_cost = 0.0

        if result and hasattr(result, 'rows') and result.rows:
            # The cost is typically in the first column
            for row in result.rows:
                if row and len(row) > 0:
                    total_cost += float(row[0]) if row[0] else 0.0

        return total_cost
    except Exception as e:
        # Cost query might fail if resource has no cost data
        raise Exception(f"Cost query failed: {str(e)}")

# In your cost/activity query logic, use COST_LOOKBACK_DAYS instead of a hardcoded 30
# For example:
# start_date = datetime.utcnow() - timedelta(days=COST_LOOKBACK_DAYS)
# end_date = datetime.utcnow()
# ...existing code for querying costs/resources using start_date and end_date...

# Example usage:
# automate_find_orphaned_resources_all_subs("http://localhost:8000", days=60)

if __name__ == "__main__":
    resource_types = load_resource_types()
    print("Loaded resource types:")
    for rtype in resource_types:
        print(rtype)
    # Automatically scan all subscriptions for orphaned resources for the last 30 days
    results = scan_orphaned_resources_all_subs(days=30, all_subscriptions=True)
    print("Orphaned resources scan results:")
    for res in results:
        print(f"\nSubscription: {res['subscription_name']} ({res['subscription_id']})")
        if 'error' in res:
            print(f"  Error: {res['error']}")
        else:
            for r in res['orphaned_resources']:
                print(f"  - {r}")

# Handler for MCP server: always scan all subscriptions for the last 60 days by default

def handle_find_orphaned_resources(request=None):
    # Use user-supplied days if present, else default to 60
    days = 60
    if request and isinstance(request, dict):
        days = request.get('days', 60)
    results = scan_orphaned_resources_all_subs(days=days, all_subscriptions=True)
    return results

def prompt_user_for_orphaned_resource_scan_auto():
    days = input("Enter number of days to look back: ").strip()
    try:
        days = int(days)
    except:
        days = 30
    all_subs = input("Check all subscriptions? (y/n): ").strip().lower() == 'y'
    results = find_orphaned_resources_auto(days=days, all_subscriptions=all_subs)
    for rtype, items in results.items():
        print(f"\nResource type: {rtype}")
        for item in items:
            print(item)