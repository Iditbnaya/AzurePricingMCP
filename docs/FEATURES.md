# Features

The Azure Pricing MCP Server provides comprehensive Azure pricing intelligence through AI assistants.

---

## Core Features

| Feature | Description |
|---------|-------------|
| 🔍 **Price Search** | Search Azure prices with filters (service, region, SKU, price type) |
| ⚖️ **Price Comparison** | Compare costs across regions or between different SKUs |
| 💡 **Cost Estimation** | Calculate monthly/yearly costs based on usage hours |
| 🎫 **Reserved Instances** | Compare 1-year and 3-year RI pricing with break-even analysis |
| 💰 **Savings Plans** | View 1-year and 3-year savings plan pricing |
| 🎯 **Smart SKU Discovery** | Fuzzy matching for service names ("vm" → "Virtual Machines") |
| 🌍 **Region Recommendations** | Find the cheapest Azure regions for any SKU with savings analysis |
| 💱 **Multi-Currency** | Support for USD, EUR, GBP, and more |
| 📊 **Real-time Data** | Live data from Azure Retail Prices API |
| 🏷️ **Customer Discounts** | Apply discount percentages to all pricing queries |

---

## Retirement Warnings

The server automatically checks VM SKUs against Microsoft's official retirement documentation and warns you when querying SKUs that are:

| Status | Icon | Description |
|--------|------|-------------|
| **Retirement Announced** | ⚠️ | SKU has a planned retirement date - migrate soon |
| **Retired** | 🚫 | SKU is no longer available for new deployments |
| **Previous Generation** | ℹ️ | Newer versions available - consider upgrading |

### Example Warning Output

```
⚠️ RETIREMENT WARNING: Lsv2-series
   Status: Retirement Announced
   Retirement Date: 11/15/28
   Recommendation: Migrate to Lsv3, Lasv3, Lsv4, or Lasv4 series
   Migration Guide: https://learn.microsoft.com/azure/virtual-machines/...

ℹ️ PREVIOUS GENERATION: Ev3-series
   Status: Newer versions available
   Recommendation: Consider upgrading to Ev5 or Ev6 series
```

The retirement data is fetched dynamically from Microsoft's official documentation and cached for 24 hours.

---

## Spot VM Tools

Spot VM tools provide intelligence for Azure Spot Virtual Machines, helping you make informed decisions about cost vs. eviction risk.

### Available Capabilities

- **Eviction Rates** - Query real-time eviction risk by SKU and region (0-5%, 5-10%, 10-15%, 15-20%, 20%+)
- **Price History** - Get up to 90 days of historical Spot pricing data
- **Eviction Simulation** - Test your workload's resilience by triggering simulated evictions

### Authentication Required

Spot VM tools require Azure authentication because they query the Azure Resource Graph API.

**Option 1: Azure CLI (Recommended for development)**
```bash
az login
```

**Option 2: Environment Variables (Recommended for production/CI)**
```bash
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
```

**Option 3: Managed Identity (When running in Azure)**
No configuration needed - uses the VM/App Service identity automatically.

### Required Permissions

| Tool | Permission | Built-in Role |
|------|------------|---------------|
| `spot_eviction_rates` | `Microsoft.ResourceGraph/resources/read` | Reader |
| `spot_price_history` | `Microsoft.ResourceGraph/resources/read` | Reader |
| `simulate_eviction` | `Microsoft.Compute/virtualMachines/simulateEviction/action` | VM Contributor |

### What if I'm not authenticated?

The Spot VM tools will return a friendly message with authentication instructions. All other pricing tools continue to work without authentication.

---

## Orphaned Resource Detection

Detect orphaned Azure resources across subscriptions and calculate their real wasted cost using the Azure Cost Management API.

### Detected Resource Types

| Resource Type | Detection Criteria |
|---------------|--------------------|
| Unattached Disks | Managed disks with no `managedBy` (not attached to any VM) |
| Orphaned Public IPs | Public IPs not associated with any IP configuration or NAT gateway |
| Empty App Service Plans | App Service Plans with zero hosted apps |
| Orphaned SQL Elastic Pools | SQL Elastic Pools with no databases in the pool |
| Orphaned Application Gateways | Application gateways with no backend address pools or targets |
| Orphaned NAT Gateways | NAT gateways not associated with any subnet |
| Orphaned Load Balancers | Load balancers with no backend address pools |
| Orphaned Private DNS Zones | Private DNS zones with no virtual network links |
| Orphaned Private Endpoints | Private endpoints with no connections or unapproved connections |
| Orphaned Virtual Network Gateways | Virtual network gateways with no IP configurations |
| Orphaned DDoS Protection Plans | DDoS protection plans with no associated virtual networks |

### Authentication Required

Orphaned resource scanning requires the same Azure authentication as Spot VM tools (see above).

### Required Permissions

| Permission | Built-in Role | Purpose |
|------------|---------------|---------|
| `Microsoft.ResourceGraph/resources/read` | Reader | Query Resource Graph for orphaned resources |
| `Microsoft.CostManagement/query/action` | Cost Management Reader | Look up historical cost per resource |

### Example Usage

```
"Find all orphaned resources across my Azure subscriptions"
"Scan for unattached disks and show me how much they cost"
"Check for orphaned resources in the last 30 days"
```

---

## Docker Support

Run in containers for easy deployment and isolation. See [INSTALL.md](../INSTALL.md) for Docker setup instructions.
