# Universal Context Template - MCP Server Installation

**Professional distribution via Docker MCP Server**

## Quick Install (One Command)

### Option 1: Docker Hub (Recommended)

```bash
# Pull and run
docker pull yourusername/uct-mcp:latest

# Add to Claude Code settings
```

### Option 2: Build Locally

```bash
# Clone or download the template
git clone https://github.com/yourusername/universal-context-template.git
cd universal-context-template/.claude/mcp-servers/unified-dev

# Build
docker-compose build

# Run
docker-compose up -d
```

---

## Configure Claude Code

Add this to your Claude Code MCP settings (`~/.config/claude/settings.json` or equivalent):

### For Docker (stdio transport)

```json
{
  "mcpServers": {
    "universal-context": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "${workspaceFolder}:/app/project",
        "universal-context-mcp:latest"
      ]
    }
  }
}
```

### For Docker with SSE (web transport)

```json
{
  "mcpServers": {
    "universal-context": {
      "transport": "sse",
      "url": "http://localhost:3000/sse"
    }
  }
}
```

Start the SSE server:
```bash
docker-compose --profile sse up -d
```

### For Local Python (no Docker)

```json
{
  "mcpServers": {
    "universal-context": {
      "command": "python",
      "args": ["/path/to/.claude/mcp-servers/unified-dev/server.py"],
      "env": {
        "PROJECT_ROOT": "${workspaceFolder}"
      }
    }
  }
}
```

---

## Available MCP Tools

Once connected, these tools are available:

### Template Installation
| Tool | Description |
|------|-------------|
| `install_template` | Install template to any project directory |
| `list_agents` | List all 8 specialized agents |
| `activate_agent` | Activate an agent (kafka, aws, fedramp, etc.) |

### Code Search (RAG)
| Tool | Description |
|------|-------------|
| `search_code` | Semantic + keyword hybrid search |
| `index_project` | Index/re-index project codebase |
| `get_code_stats` | Get indexing statistics |

### Memory
| Tool | Description |
|------|-------------|
| `save_memory` | Save persistent memory |
| `search_memory` | Search saved memories |
| `get_session_context` | Get full session context |

### Context Files
| Tool | Description |
|------|-------------|
| `get_context_files` | List all .claude/*.md files |
| `read_context_file` | Read specific context file |

---

## Usage Examples

### Install Template to New Project

In Claude Code, say:
> "Install the universal context template to /path/to/my-new-project"

The MCP server will use `install_template` tool to copy all files.

### Activate an Agent

> "Activate the FedRAMP agent and help me implement NIST 800-53 controls"

The MCP server will load the FedRAMP agent expertise.

### Search Code

> "Search for database connection handling in my codebase"

The MCP server uses RAG to find relevant code.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ROOT` | `/app/project` | Path to user's project |
| `CHROMA_PERSIST_DIR` | `/app/data/chroma` | Vector DB storage |
| `MEM0_MODE` | `local` | Memory mode (local/cloud) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MCP_TRANSPORT` | `stdio` | Transport (stdio/sse) |
| `MCP_PORT` | `3000` | Port for SSE transport |

---

## Docker Hub Distribution

### Push to Docker Hub

```bash
# Login
docker login

# Tag
docker tag universal-context-mcp:latest yourusername/uct-mcp:latest
docker tag universal-context-mcp:latest yourusername/uct-mcp:2.2

# Push
docker push yourusername/uct-mcp:latest
docker push yourusername/uct-mcp:2.2
```

### Users Pull

```bash
docker pull yourusername/uct-mcp:latest
```

---

## Troubleshooting

### "MCP server not connecting"

1. Check Docker is running: `docker ps`
2. Check image exists: `docker images | grep uct-mcp`
3. Check logs: `docker logs uct-mcp-server`

### "RAG not working"

1. Make sure project is mounted: `-v /your/project:/app/project`
2. Index the project first: use `index_project` tool

### "Permission denied"

Run with user mapping:
```bash
docker run --rm -i -u $(id -u):$(id -g) -v ...
```

---

## Security Notes

- Container runs as non-root user (UID 10001)
- Read-only filesystem supported
- No sensitive data stored in image
- FedRAMP Moderate compliant configuration

---

## Support

- Documentation: See `.claude/agents/` for agent docs
- Issues: GitHub Issues
- Security: See `SECURITY_COMPLIANCE.md`

---

**Version:** 2.2 | **Compliance:** FedRAMP Moderate | **Agents:** 8
