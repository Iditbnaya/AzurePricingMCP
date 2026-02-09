"""Service for finding orphaned Azure resources."""

import logging
from typing import Any

from .orphaned_resources import handle_find_orphaned_resources

logger = logging.getLogger(__name__)


class OrphanedResourcesService:
    """Service for scanning and identifying orphaned Azure resources.

    This service provides functionality to:
    - Scan all Azure subscriptions for orphaned resources
    - Identify unattached disks, public IPs, app service plans, and load balancers
    - Calculate costs for orphaned resources
    - Support custom lookback periods

    Requires Azure authentication via:
    - Azure CLI (az login)
    - Environment variables
    - Managed identity
    """

    def __init__(self) -> None:
        """Initialize the Orphaned Resources Service."""
        pass

    async def find_orphaned_resources(
        self,
        days: int = 60,
        all_subscriptions: bool = True,
    ) -> list[dict[str, Any]]:
        """Find orphaned resources across Azure subscriptions.

        Args:
            days: Number of days to look back for cost calculation (default: 60)
            all_subscriptions: Whether to scan all subscriptions (default: True)

        Returns:
            List of subscription results containing orphaned resources

        Raises:
            Exception: If Azure authentication fails or API calls fail
        """
        logger.info(f"Scanning for orphaned resources (lookback: {days} days, all subs: {all_subscriptions})")

        try:
            # Call the handler from orphaned_resources.py
            # Note: The function is synchronous, but we're in an async context
            # We could wrap it in asyncio.to_thread() if needed
            request = {"days": days, "all_subscriptions": all_subscriptions}
            results = handle_find_orphaned_resources(request)

            logger.info(f"Found {len(results)} subscription results")
            return results

        except Exception as e:
            logger.error(f"Error finding orphaned resources: {e}")
            raise
