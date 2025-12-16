#!/bin/bash
# Universal MCP Server Installation Script
# Installs RAG + Unified MCP Server from template

set -e

echo "===================================="
echo "Universal MCP Server Installation"
echo "===================================="
echo ""

# Get project root
PROJECT_ROOT=$(pwd)
echo "Project root: $PROJECT_ROOT"

# Check if .claude directory exists
if [ ! -d ".claude" ]; then
    echo "Creating .claude directory..."
    mkdir -p .claude
fi

# Check if template exists
TEMPLATE_PATH="${1:-../UNIVERSAL_CONTEXT_TEMPLATE}"
if [ ! -d "$TEMPLATE_PATH" ]; then
    echo "❌ Template not found at: $TEMPLATE_PATH"
    echo "Usage: ./install-unified-mcp.sh /path/to/UNIVERSAL_CONTEXT_TEMPLATE"
    exit 1
fi

echo "✅ Template found at: $TEMPLATE_PATH"
echo ""

# Install RAG system
echo "📦 Installing RAG system..."
cp -r "$TEMPLATE_PATH/.claude/rag" .claude/
echo "✅ RAG system installed"

# Install MCP server
echo "📦 Installing Unified MCP Server..."
mkdir -p .claude/mcp-servers
cp -r "$TEMPLATE_PATH/.claude/mcp-servers/unified-dev" .claude/mcp-servers/
echo "✅ MCP server installed"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
cd .claude/rag
pip install -r rag_requirements.txt
cd ../mcp-servers/unified-dev
pip install -r requirements.txt
cd "$PROJECT_ROOT"
echo "✅ Dependencies installed"

# Setup environment
echo ""
echo "⚙️  Setting up environment..."
if [ ! -f ".claude/rag/.env" ]; then
    cp .claude/rag/.env.example .claude/rag/.env
    echo "✅ Created .claude/rag/.env (edit with your API keys)"
fi

if [ ! -f ".claude/mcp-servers/unified-dev/.env" ]; then
    cp .claude/mcp-servers/unified-dev/.env.example .claude/mcp-servers/unified-dev/.env
    echo "✅ Created .claude/mcp-servers/unified-dev/.env"
fi

# Update PROJECT_ROOT in .env
sed -i "s|PROJECT_ROOT=.*|PROJECT_ROOT=$PROJECT_ROOT|g" .claude/mcp-servers/unified-dev/.env

echo ""
echo "===================================="
echo "✅ Installation Complete!"
echo "===================================="
echo ""
echo "Next steps:"
echo "1. Edit .claude/mcp-servers/unified-dev/.env with your API keys"
echo "   - Required: ANTHROPIC_API_KEY"
echo "   - Optional: OPENAI_API_KEY, CUSTOM_MODEL_API_KEY"
echo ""
echo "2. Add to .claude/mcp_settings.json:"
echo '   {'
echo '     "mcpServers": {'
echo '       "your-project-dev": {'
echo '         "command": "python",'
echo '         "args": [".claude/mcp-servers/unified-dev/server.py"],'
echo "         \"cwd\": \"$PROJECT_ROOT\","
echo '         "env": {'
echo "           \"PYTHONPATH\": \"$PROJECT_ROOT\","
echo "           \"PROJECT_ROOT\": \"$PROJECT_ROOT\""
echo '         },'
echo '         "description": "Unified development assistant"'
echo '       }'
echo '     }'
echo '   }'
echo ""
echo "3. Create chunking strategy for your codebase in .claude/rag/"
echo ""
echo "4. Restart Claude Code to activate the MCP server"
echo ""
