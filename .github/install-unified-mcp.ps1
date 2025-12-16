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

# Check if .github directory exists
if (-not (Test-Path ".github")) {
    Write-Host "Creating .github directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path ".github" | Out-Null
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
Copy-Item -Path "$TemplatePath\.github\rag" -Destination ".github\" -Recurse -Force
Write-Host "✅ RAG system installed" -ForegroundColor Green

# Install MCP server
Write-Host "📦 Installing Unified MCP Server..." -ForegroundColor Yellow
if (-not (Test-Path ".github\mcp-servers")) {
    New-Item -ItemType Directory -Path ".github\mcp-servers" | Out-Null
}
Copy-Item -Path "$TemplatePath\.github\mcp-servers\unified-dev" -Destination ".github\mcp-servers\" -Recurse -Force
Write-Host "✅ MCP server installed" -ForegroundColor Green

# Install dependencies
Write-Host ""
Write-Host "📦 Installing Python dependencies..." -ForegroundColor Yellow
Push-Location ".github\rag"
pip install -r rag_requirements.txt
Pop-Location

Push-Location ".github\mcp-servers\unified-dev"
pip install -r requirements.txt
Pop-Location

Write-Host "✅ Dependencies installed" -ForegroundColor Green

# Setup environment
Write-Host ""
Write-Host "⚙️  Setting up environment..." -ForegroundColor Yellow

if (-not (Test-Path ".github\rag\.env")) {
    Copy-Item ".github\rag\.env.example" ".github\rag\.env"
    Write-Host "✅ Created .github\rag\.env (edit with your API keys)" -ForegroundColor Green
}

if (-not (Test-Path ".github\mcp-servers\unified-dev\.env")) {
    Copy-Item ".github\mcp-servers\unified-dev\.env.example" ".github\mcp-servers\unified-dev\.env"
    Write-Host "✅ Created .github\mcp-servers\unified-dev\.env" -ForegroundColor Green
}

# Update PROJECT_ROOT in .env
$envContent = Get-Content ".github\mcp-servers\unified-dev\.env" -Raw
$envContent = $envContent -replace "PROJECT_ROOT=.*", "PROJECT_ROOT=$PROJECT_ROOT"
$envContent | Set-Content ".github\mcp-servers\unified-dev\.env"

Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "✅ Installation Complete!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .github\mcp-servers\unified-dev\.env with your API keys"
Write-Host "   - Required: ANTHROPIC_API_KEY"
Write-Host "   - Optional: OPENAI_API_KEY, CUSTOM_MODEL_API_KEY"
Write-Host ""
Write-Host "2. Add to .github\mcp_settings.json:"
Write-Host '   {' -ForegroundColor Gray
Write-Host '     "mcpServers": {' -ForegroundColor Gray
Write-Host '       "your-project-dev": {' -ForegroundColor Gray
Write-Host '         "command": "python",' -ForegroundColor Gray
Write-Host '         "args": [".github/mcp-servers/unified-dev/server.py"],' -ForegroundColor Gray
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
Write-Host "3. Create chunking strategy for your codebase in .github\rag\"
Write-Host ""
Write-Host "4. Restart Claude Code to activate the MCP server"
Write-Host ""
