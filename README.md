# Azure Pricing MCP Server 💰

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.0+-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/msftnadavbh/AzurePricingMCP/actions/workflows/test.yml/badge.svg)](https://github.com/msftnadavbh/AzurePricingMCP/actions/workflows/test.yml)

A **Model Context Protocol (MCP)** server that provides AI assistants with real-time access to Azure retail pricing information. Query VM prices, compare costs across regions, estimate monthly bills, and discover available SKUs—all through natural language.

<p align="center">
  <img src="https://img.shields.io/badge/Azure-Pricing-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white" alt="Azure Pricing"/>
  <img src="https://img.shields.io/badge/VS_Code-MCP-007ACC?style=for-the-badge&logo=visual-studio-code&logoColor=white" alt="VS Code MCP"/>
</p>

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/msftnadavbh/AzurePricingMCP.git
cd AzurePricingMCP

# 2. Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Test the server
python -m azure_pricing_mcp
```

Then configure your AI assistant (VS Code, Claude Desktop, etc.) to use the MCP server.

---

## ✨ Features

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
| ⚠️ **Retirement Warnings** | Automatic alerts for retiring/retired VM SKUs with migration guidance |
| 🎰 **Spot VM Tools** | Eviction rates, price history, and eviction simulation (requires Azure auth) |
| 🐳 **Docker Support** | Run in containers for easy deployment and isolation |

---

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `azure_price_search` | Search Azure retail prices with flexible filtering |
| `azure_price_compare` | Compare prices across regions or SKUs |
| `azure_ri_pricing` | Get Reserved Instance pricing and savings analysis |
| `azure_cost_estimate` | Estimate costs based on usage patterns |
| `azure_region_recommend` | Find cheapest regions for a SKU with savings percentages |
| `azure_discover_skus` | List available SKUs for a specific service |
| `azure_sku_discovery` | Intelligent SKU discovery with fuzzy name matching |
| `get_customer_discount` | Get customer discount information |

### 🎰 Spot VM Tools (Requires Azure Authentication)

| Tool | Description |
|------|-------------|
| `spot_eviction_rates` | Get Spot VM eviction rates for SKUs across regions |
| `spot_price_history` | Get up to 90 days of historical Spot pricing |
| `simulate_eviction` | Trigger eviction simulation on a Spot VM |

> **Note:** Spot VM tools require Azure authentication. See [Spot VM Authentication](#spot-vm-authentication) below.

---

## 📋 Installation

> **📝 New to setup?** Check out [INSTALL.md](INSTALL.md) for detailed instructions or [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) for a step-by-step checklist!  
> **🐳 Prefer Docker?** See [DOCKER.md](DOCKER.md) for containerized deployment!

### Prerequisites

- **Python 3.10+** (or Docker for containerized deployment)
- **pip** (Python package manager)

### Option 1: Docker (Easiest)

```bash
docker build -t azure-pricing-mcp .
docker run -i azure-pricing-mcp
```

### Option 2: Automated Setup

```bash
# Windows PowerShell
.\scripts\setup.ps1

# Linux/Mac/Cross-platform
python scripts/install.py
```

### Option 3: Manual Setup

```bash
# Clone repository
git clone https://github.com/msftnadavbh/AzurePricingMCP.git
cd AzurePricingMCP

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate    # Linux/Mac
.venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## 🖥️ VS Code Integration

### Step 1: Install GitHub Copilot

Ensure you have the [GitHub Copilot](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot) extension installed.

### Step 2: Configure MCP Server

Create or edit `.vscode/mcp.json` in your workspace:

**Option A: Using Python Virtual Environment**
```jsonc
{
  "servers": {
    "azure-pricing": {
      "type": "stdio",
      "command": "/absolute/path/to/AzurePricingMCP/.venv/bin/python",
      "args": ["-m", "azure_pricing_mcp"]
    }
  }
}
```

> **Windows users**: Use the full path with forward slashes or escaped backslashes:
> ```json
> "command": "C:/Users/YourUsername/Projects/AzurePricingMCP/.venv/Scripts/python.exe"
> ```

**Option B: Using Docker (stdio)** 🐳
```json
{
  "servers": {
    "azure-pricing": {
      "type": "stdio",
      "command": "docker",
      "args": ["run", "-i", "--rm", "azure-pricing-mcp:latest"]
    }
  }
}
```

**Option C: Using Docker (SSE - Server-Sent Events)** 🐳
```bash
# First, build and run the container with port mapping
docker build -t azure-pricing-mcp .
docker run -d -p 8080:8080 --name azure-pricing azure-pricing-mcp
```

Then configure `.vscode/mcp.json`:
```json
{
  "servers": {
    "azure-pricing": {
      "type": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

> 💡 **SSE Benefits**: Better isolation through Docker, allows multiple clients to connect to the same server instance, and easier to debug with HTTP endpoints.

### Step 3: Restart MCP Server

1. Open Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`)
2. Run: **MCP: List Servers**
3. Click the refresh/restart button next to `azure-pricing`

### Step 4: Use in Copilot Chat

Open Copilot Chat and ask:

```
What's the price of Standard_D32s_v6 in East US 2?
```

You'll see the MCP tools being invoked with real Azure pricing data!

---

## 🤖 Claude Desktop Integration

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Option A: Using Python**
```json
{
  "mcpServers": {
    "azure-pricing": {
      "command": "python",
      "args": ["-m", "azure_pricing_mcp"],
      "cwd": "/path/to/AzurePricingMCP"
    }
  }
}
```

**Option B: Using Docker** 🐳
```json
{
  "mcpServers": {
    "azure-pricing": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "azure-pricing-mcp:latest"]
    }
  }
}
```

---

## 💬 Example Queries

Once configured, ask your AI assistant:

| Query Type | Example |
|------------|---------|
| **Basic Pricing** | "What's the price of a D4s_v3 VM in West US 2?" |
| **Multi-Node** | "Price for 20 Standard_D32s_v6 nodes in East US 2" |
| **Comparison** | "Compare VM prices between East US and West Europe" |
| **Cost Estimate** | "Estimate monthly cost for D8s_v5 running 12 hours/day" |
| **SKU Discovery** | "What App Service plans are available?" |
| **Savings Plans** | "Show savings plan options for virtual machines" |
| **Storage** | "What are the blob storage pricing tiers?" |
| **Spot Eviction** | "What are the eviction rates for D4s_v4 in eastus?" |
| **Spot History** | "Show me Spot price history for D2s_v4 in westus2" |

### Sample Response

```
Standard_D32s_v6 in East US 2:
- Linux On-Demand: $1.613/hour → $23,550/month for 20 nodes
- 1-Year Savings:  $1.113/hour → $16,250/month (31% savings)
- 3-Year Savings:  $0.742/hour → $10,833/month (54% savings)
```

---

## ⚠️ Retirement Status Warnings

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

## 🎰 Spot VM Authentication

Spot VM tools (`spot_eviction_rates`, `spot_price_history`, `simulate_eviction`) require Azure authentication because they query the Azure Resource Graph API, which is not publicly accessible.

### Authentication Options

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

For least-privilege access, create a custom role with only the permissions you need.

### What if I'm not authenticated?

The Spot VM tools will return a friendly message with authentication instructions:

```
🔐 Azure Authentication Required

To use Spot VM tools, you need to authenticate with Azure.
Please run `az login` or set AZURE_* environment variables.
```

All other pricing tools continue to work without authentication.

---

## 🧪 Testing

### Verify Installation

```bash
# Run the server directly (should start without errors)
python -m azure_pricing_mcp

# Run tests
pytest tests/
```

### Test MCP Connection in VS Code

1. Open Command Palette → **MCP: List Servers**
2. Verify `azure-pricing` shows 8 tools
3. Open Copilot Chat and ask a pricing question

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/AzurePricingMCP.git
cd AzurePricingMCP

# Create development environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Make your changes
# ...

# Test your changes
pytest tests/
```

### Contribution Guidelines

1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to your branch (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

### Code Style

- Follow PEP 8 guidelines
- Add type hints for function parameters and return values
- Include docstrings for public functions
- Run `black`, `ruff`, and `mypy` before submitting
- Test your changes with `pytest tests/`

---

## 📁 Project Structure

```
AzurePricingMCP/
├── src/
│   └── azure_pricing_mcp/
│       ├── __init__.py       # Package initialization
│       ├── __main__.py       # Module entry point
│       ├── server.py         # Main MCP server implementation
│       ├── handlers.py       # Tool handlers
│       ├── client.py         # Azure Pricing API client
│       ├── config.py         # Configuration constants
│       ├── formatters.py     # Response formatting
│       ├── models.py         # Data models
│       ├── tools.py          # Tool definitions
│       └── services/         # Business logic services
│           ├── pricing.py    # Pricing operations
│           ├── retirement.py # VM retirement tracking
│           └── sku.py        # SKU discovery
├── scripts/
│   ├── install.py            # Installation script
│   ├── setup.ps1             # PowerShell setup script
│   └── run_server.py         # Server runner
├── tests/                    # Test suite
├── docs/                     # Additional documentation
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Package configuration
├── README.md                 # This file
├── QUICK_START.md            # Quick start guide
└── INSTALL.md                # Detailed installation guide
```

---

## 🔌 API Reference

This server uses the [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices):

```
https://prices.azure.com/api/retail/prices
```

**No authentication required** - The Azure Retail Prices API is publicly accessible.

---

## 📚 Additional Documentation

- **[QUICK_START.md](QUICK_START.md)** - Step-by-step setup guide
- **[INSTALL.md](INSTALL.md)** - Detailed installation instructions
- **[DOCKER.md](DOCKER.md)** - Docker containerization guide 🐳
- **[USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)** - Detailed usage examples and API responses
- **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)** - Installation verification checklist

---

## ⚠️ Troubleshooting

### Tools not appearing in VS Code

1. **Check Python syntax**: Run `python -m azure_pricing_mcp` to check for errors
2. **Verify path**: Use absolute paths in `.vscode/mcp.json`
3. **Restart server**: Command Palette → MCP: List Servers → Restart

### "No module named 'mcp'"

```bash
# Ensure you're in the virtual environment
source .venv/bin/activate
pip install mcp>=1.0.0
```

### Connection errors

- Check your internet connection
- The Azure Pricing API may rate-limit requests (automatic retry is built-in)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Original Author**: [@charris-msft](https://github.com/charris-msft)
- **Current Maintainer + Version 2.3**: [@msftnadavbh](https://github.com/msftnadavbh)
- **Contributors**: 
  - [@notoriousmic](https://github.com/notoriousmic) - Testing infrastructure and best practices
- [Model Context Protocol](https://modelcontextprotocol.io/) - The protocol that makes this possible
- [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) - Microsoft's public pricing API
- All open-source contributors

---

## 📬 Support

- **Issues**: [GitHub Issues](https://github.com/msftnadavbh/AzurePricingMCP/issues)
- **Discussions**: [GitHub Discussions](https://github.com/msftnadavbh/AzurePricingMCP/discussions)

---

<p align="center">
  Made with ❤️ for the Azure community
</p>
