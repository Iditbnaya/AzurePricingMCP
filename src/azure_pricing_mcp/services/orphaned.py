"""Service for finding orphaned Azure resources."""

import logging
from typing import Any, cast

from .orphaned_resources import handle_find_orphaned_resources

logger = logging.getLogger(__name__)


class OrphanedResourcesService:
    """Service for scanning and identifying orphaned Azure resources."""

    def __init__(self) -> None:
        """Initialize the Orphaned Resources Service."""
        pass

    async def find_orphaned_resources(
        self,
        days: int = 60,
        all_subscriptions: bool = True,
    ) -> list[dict[str, Any]]:
        """Find orphaned resources across Azure subscriptions."""
        logger.info(f"Scanning for orphaned resources (lookback: {days} days, all subs: {all_subscriptions})")

        try:
            request = {"days": days, "all_subscriptions": all_subscriptions}
            results = handle_find_orphaned_resources(request)

            logger.info(f"Found {len(results)} subscription results")
            return cast(list[dict[str, Any]], results)

        except Exception as e:
            logger.error(f"Error finding orphaned resources: {e}")
            raise
