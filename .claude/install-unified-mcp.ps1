# Universal MCP Server Installation Script (Windows PowerShell)
# Installs RAG + Unified MCP Server from template

param(
    [string]$TemplatePath = "..\UNIVERSAL_CONTEXT_TEMPLATE"
)

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Universal MCP Server Installation" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Get project root
$PROJECT_ROOT = (Get-Location).Path
Write-Host "Project root: $PROJECT_ROOT"

# Check if .claude directory exists
if (-not (Test-Path ".claude")) {
    Write-Host "Creating .claude directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path ".claude" | Out-Null
}

# Check if template exists
if (-not (Test-Path $TemplatePath)) {
    Write-Host "❌ Template not found at: $TemplatePath" -ForegroundColor Red
    Write-Host "Usage: .\install-unified-mcp.ps1 -TemplatePath C:\path\to\UNIVERSAL_CONTEXT_TEMPLATE"
    exit 1
}

Write-Host "✅ Template found at: $TemplatePath" -ForegroundColor Green
Write-Host ""

# Install RAG system
Write-Host "📦 Installing RAG system..." -ForegroundColor Yellow
Copy-Item -Path "$TemplatePath\.claude\rag" -Destination ".claude\" -Recurse -Force
Write-Host "✅ RAG system installed" -ForegroundColor Green

# Install MCP server
Write-Host "📦 Installing Unified MCP Server..." -ForegroundColor Yellow
if (-not (Test-Path ".claude\mcp-servers")) {
    New-Item -ItemType Directory -Path ".claude\mcp-servers" | Out-Null
}
Copy-Item -Path "$TemplatePath\.claude\mcp-servers\unified-dev" -Destination ".claude\mcp-servers\" -Recurse -Force
Write-Host "✅ MCP server installed" -ForegroundColor Green

# Install dependencies
Write-Host ""
Write-Host "📦 Installing Python dependencies..." -ForegroundColor Yellow
Push-Location ".claude\rag"
pip install -r rag_requirements.txt
Pop-Location

Push-Location ".claude\mcp-servers\unified-dev"
pip install -r requirements.txt
Pop-Location

Write-Host "✅ Dependencies installed" -ForegroundColor Green

# Setup environment
Write-Host ""
Write-Host "⚙️  Setting up environment..." -ForegroundColor Yellow

if (-not (Test-Path ".claude\rag\.env")) {
    Copy-Item ".claude\rag\.env.example" ".claude\rag\.env"
    Write-Host "✅ Created .claude\rag\.env (edit with your API keys)" -ForegroundColor Green
}

if (-not (Test-Path ".claude\mcp-servers\unified-dev\.env")) {
    Copy-Item ".claude\mcp-servers\unified-dev\.env.example" ".claude\mcp-servers\unified-dev\.env"
    Write-Host "✅ Created .claude\mcp-servers\unified-dev\.env" -ForegroundColor Green
}

# Update PROJECT_ROOT in .env
$envContent = Get-Content ".claude\mcp-servers\unified-dev\.env" -Raw
$envContent = $envContent -replace "PROJECT_ROOT=.*", "PROJECT_ROOT=$PROJECT_ROOT"
$envContent | Set-Content ".claude\mcp-servers\unified-dev\.env"

Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "✅ Installation Complete!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .claude\mcp-servers\unified-dev\.env with your API keys"
Write-Host "   - Required: ANTHROPIC_API_KEY"
Write-Host "   - Optional: OPENAI_API_KEY, CUSTOM_MODEL_API_KEY"
Write-Host ""
Write-Host "2. Add to .claude\mcp_settings.json:"
Write-Host '   {' -ForegroundColor Gray
Write-Host '     "mcpServers": {' -ForegroundColor Gray
Write-Host '       "your-project-dev": {' -ForegroundColor Gray
Write-Host '         "command": "python",' -ForegroundColor Gray
Write-Host '         "args": [".claude/mcp-servers/unified-dev/server.py"],' -ForegroundColor Gray
Write-Host "         `"cwd`": `"$PROJECT_ROOT`"," -ForegroundColor Gray
Write-Host '         "env": {' -ForegroundColor Gray
Write-Host "           `"PYTHONPATH`": `"$PROJECT_ROOT`"," -ForegroundColor Gray
Write-Host "           `"PROJECT_ROOT`": `"$PROJECT_ROOT`"" -ForegroundColor Gray
Write-Host '         },' -ForegroundColor Gray
Write-Host '         "description": "Unified development assistant"' -ForegroundColor Gray
Write-Host '       }' -ForegroundColor Gray
Write-Host '     }' -ForegroundColor Gray
Write-Host '   }' -ForegroundColor Gray
Write-Host ""
Write-Host "3. Create chunking strategy for your codebase in .claude\rag\"
Write-Host ""
Write-Host "4. Restart Claude Code to activate the MCP server"
Write-Host ""
