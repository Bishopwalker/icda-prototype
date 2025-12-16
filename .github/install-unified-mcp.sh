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

# Check if .github directory exists
if [ ! -d ".github" ]; then
    echo "Creating .github directory..."
    mkdir -p .github
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
cp -r "$TEMPLATE_PATH/.github/rag" .github/
echo "✅ RAG system installed"

# Install MCP server
echo "📦 Installing Unified MCP Server..."
mkdir -p .github/mcp-servers
cp -r "$TEMPLATE_PATH/.github/mcp-servers/unified-dev" .github/mcp-servers/
echo "✅ MCP server installed"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
cd .github/rag
pip install -r rag_requirements.txt
cd ../mcp-servers/unified-dev
pip install -r requirements.txt
cd "$PROJECT_ROOT"
echo "✅ Dependencies installed"

# Setup environment
echo ""
echo "⚙️  Setting up environment..."
if [ ! -f ".github/rag/.env" ]; then
    cp .github/rag/.env.example .github/rag/.env
    echo "✅ Created .github/rag/.env (edit with your API keys)"
fi

if [ ! -f ".github/mcp-servers/unified-dev/.env" ]; then
    cp .github/mcp-servers/unified-dev/.env.example .github/mcp-servers/unified-dev/.env
    echo "✅ Created .github/mcp-servers/unified-dev/.env"
fi

# Update PROJECT_ROOT in .env
sed -i "s|PROJECT_ROOT=.*|PROJECT_ROOT=$PROJECT_ROOT|g" .github/mcp-servers/unified-dev/.env

echo ""
echo "===================================="
echo "✅ Installation Complete!"
echo "===================================="
echo ""
echo "Next steps:"
echo "1. Edit .github/mcp-servers/unified-dev/.env with your API keys"
echo "   - Required: ANTHROPIC_API_KEY"
echo "   - Optional: OPENAI_API_KEY, CUSTOM_MODEL_API_KEY"
echo ""
echo "2. Add to .github/mcp_settings.json:"
echo '   {'
echo '     "mcpServers": {'
echo '       "your-project-dev": {'
echo '         "command": "python",'
echo '         "args": [".github/mcp-servers/unified-dev/server.py"],'
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
echo "3. Create chunking strategy for your codebase in .github/rag/"
echo ""
echo "4. Restart Claude Code to activate the MCP server"
echo ""
