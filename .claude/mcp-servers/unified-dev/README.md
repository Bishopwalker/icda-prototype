# Unified MCP Server - Universal Template

**Model-Agnostic Development Assistant** combining RAG (code search), Memory (session persistence), and multi-model support.

## Overview

This is a **universal template** for a unified MCP server that provides:
- 🔍 **RAG Tools**: Search your codebase with semantic + keyword hybrid search
- 🧠 **Memory Tools**: Persistent session context via Mem0
- 🤖 **Model Tools**: Switch between Claude, Codex, and custom models

## Quick Start

### 1. Copy to Your Project
```bash
# Copy RAG system
cp -r UNIVERSAL_CONTEXT_TEMPLATE/.claude/rag/ your-project/.claude/rag/

# Copy MCP server
cp -r UNIVERSAL_CONTEXT_TEMPLATE/.claude/mcp-servers/unified-dev/ your-project/.claude/mcp-servers/your-project-dev/
```

### 2. Install Dependencies
```bash
cd your-project/.claude/rag && pip install -r rag_requirements.txt
cd ../mcp-servers/your-project-dev && pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
# Edit .env: Set ANTHROPIC_API_KEY, PROJECT_ROOT
```

### 4. Register in MCP Settings
See INSTALLATION.md for detailed setup instructions.

## Customization Guide

**Replace project-specific references:**
- Update `PROJECT_ROOT` in .env
- Rename `your-project-dev` directory
- Update README with your project name
- Create domain-specific chunking strategies

See full documentation at: `.claude/mcp-servers/unified-dev/CUSTOMIZATION.md`

---

**Template Version**: 2.1 (2025-12-02)
