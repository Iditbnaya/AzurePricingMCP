# Integrations

The Azure Pricing MCP Server integrates with AI assistants that support the Model Context Protocol (MCP).

---

## Supported Platforms

- **VS Code** with GitHub Copilot
- **Claude Desktop**
- Any MCP-compatible client

---

## VS Code Integration

### Prerequisites

1. [GitHub Copilot](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot) extension installed
2. Azure Pricing MCP Server installed (see [INSTALL.md](../INSTALL.md))

### Configuration

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

### Restart MCP Server

1. Open Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`)
2. Run: **MCP: List Servers**
3. Click the refresh/restart button next to `azure-pricing`

### Verify Connection

Open Copilot Chat and ask:

```
What's the price of Standard_D32s_v6 in East US 2?
```

You'll see the MCP tools being invoked with real Azure pricing data!

---

## Claude Desktop Integration

### Configuration File Location

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### Configuration

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

### Restart Claude Desktop

After updating the configuration, restart Claude Desktop to load the MCP server.

---

## Troubleshooting

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
