#!/usr/bin/env python3
"""
Universal Context Template - MCP Server
Model-agnostic development assistant with RAG, Memory, and Context Engineering

Features:
- Code search with semantic + keyword hybrid search
- Persistent memory across sessions
- Agent activation (Kafka, AWS, Spring Boot, Docker, FedRAMP, etc.)
- Template installation to local projects
- Context file management

Usage:
    python server.py              # stdio transport (default)
    MCP_TRANSPORT=sse python server.py  # SSE transport for web

Environment:
    PROJECT_ROOT: Path to user's project for indexing
    CHROMA_PERSIST_DIR: Path to persist vector DB
    MEM0_MODE: local or cloud
    LOG_LEVEL: DEBUG, INFO, WARNING, ERROR
"""

import asyncio
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

# Setup Python path
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))
sys.path.insert(0, str(server_dir.parent.parent))  # For rag imports

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import MCP SDK
from mcp.server import Server
from mcp.types import Tool, TextContent

# Setup logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('uct-mcp')

# Initialize MCP server
app = Server("universal-context-template")

# Global state
_rag_pipeline = None
_memory_service = None
_agents_loaded = {}
_project_root = None


def get_project_root() -> Path:
    """Get the project root path."""
    global _project_root
    if _project_root is None:
        _project_root = Path(os.getenv('PROJECT_ROOT', '/app/project'))
    return _project_root


def load_config() -> dict:
    """Load configuration from config.json"""
    config_path = server_dir / "config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {
        "rag": {"n_results_default": 5, "vector_provider": "chroma"},
        "memory": {"mode": "local"},
        "server": {"transport": "stdio", "log_level": "INFO"}
    }


def initialize_rag():
    """Initialize RAG pipeline."""
    global _rag_pipeline
    try:
        from rag.vector_database import CloudRAGPipeline, VectorProvider

        project_root = get_project_root()
        persist_dir = os.getenv('CHROMA_PERSIST_DIR', '/app/data/chroma')

        _rag_pipeline = CloudRAGPipeline(
            project_root=str(project_root),
            provider=VectorProvider.CHROMA,
            persist_directory=persist_dir
        )
        logger.info(f"RAG initialized for: {project_root}")
        return True
    except Exception as e:
        logger.warning(f"RAG initialization skipped: {e}")
        return False


def initialize_memory():
    """Initialize memory service."""
    global _memory_service
    try:
        from rag.memory_service import MemoryService
        from rag.config import load_config as load_rag_config

        config = load_rag_config()
        _memory_service = MemoryService(config.get_mem0_config())
        logger.info("Memory service initialized")
        return True
    except Exception as e:
        logger.warning(f"Memory initialization skipped: {e}")
        return False


def load_agent(agent_name: str) -> Optional[str]:
    """Load an agent's markdown content."""
    global _agents_loaded

    if agent_name in _agents_loaded:
        return _agents_loaded[agent_name]

    # Map agent names to files
    agent_files = {
        "kafka": "KAFKA_AGENT.md",
        "aws": "AWS_AGENT.md",
        "springboot": "SPRINGBOOT_AGENT.md",
        "springcloud": "SPRINGCLOUD_AGENT.md",
        "docker": "DOCKER_AGENT.md",
        "fedramp": "FEDRAMP_SECURITY_AGENT.md",
        "hardening": "INFRASTRUCTURE_HARDENING_AGENT.md",
        "zerotrust": "ZERO_TRUST_AGENT.md",
    }

    if agent_name.lower() not in agent_files:
        return None

    agent_path = server_dir.parent.parent / "agents" / agent_files[agent_name.lower()]
    if not agent_path.exists():
        # Try alternate location
        agent_path = Path("/app/agents") / agent_files[agent_name.lower()]

    if agent_path.exists():
        content = agent_path.read_text()
        _agents_loaded[agent_name] = content
        return content

    return None


# =============================================================================
# MCP Tools Registration
# =============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available MCP tools"""
    return [
        # === Template Installation Tools ===
        Tool(
            name="install_template",
            description="Install Universal Context Template to a target project directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_path": {
                        "type": "string",
                        "description": "Path where to install the template"
                    },
                    "include_agents": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include agent files"
                    },
                    "include_rag": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include RAG system"
                    }
                },
                "required": ["target_path"]
            }
        ),
        Tool(
            name="list_agents",
            description="List all available specialized agents",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="activate_agent",
            description="Activate a specialized agent (kafka, aws, springboot, docker, fedramp, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": ["kafka", "aws", "springboot", "springcloud", "docker", "fedramp", "hardening", "zerotrust"],
                        "description": "Name of agent to activate"
                    },
                    "task": {
                        "type": "string",
                        "description": "Task to perform with the agent"
                    }
                },
                "required": ["agent_name"]
            }
        ),

        # === RAG Tools ===
        Tool(
            name="search_code",
            description="Search the codebase using hybrid semantic + keyword search",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "n_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="index_project",
            description="Index or re-index the project codebase for search",
            inputSchema={
                "type": "object",
                "properties": {
                    "force_reindex": {
                        "type": "boolean",
                        "default": False,
                        "description": "Force complete re-indexing"
                    }
                }
            }
        ),
        Tool(
            name="get_code_stats",
            description="Get statistics about the indexed codebase",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # === Memory Tools ===
        Tool(
            name="save_memory",
            description="Save persistent memory for later retrieval",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "content": {"type": "string"},
                    "memory_type": {
                        "type": "string",
                        "enum": ["session", "decision", "learning", "code_context"],
                        "default": "session"
                    },
                    "metadata": {"type": "object"}
                },
                "required": ["session_id", "content"]
            }
        ),
        Tool(
            name="search_memory",
            description="Search across all saved memories",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "session_id": {"type": "string"},
                    "n_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_session_context",
            description="Get all context for a session including memories and recent code changes",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"}
                },
                "required": ["session_id"]
            }
        ),

        # === Context Tools ===
        Tool(
            name="get_context_files",
            description="Get list of all context files (.claude/*.md)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="read_context_file",
            description="Read a specific context file",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of context file (e.g., CLAUDE.md, INDEX.md)"
                    }
                },
                "required": ["filename"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    try:
        result = await _handle_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({
            "error": str(e),
            "tool": name
        }))]


async def _handle_tool(name: str, arguments: dict) -> dict:
    """Route and handle tool calls."""

    # === Template Installation ===
    if name == "install_template":
        return await _install_template(**arguments)

    elif name == "list_agents":
        return {
            "agents": [
                {"name": "kafka", "description": "Apache Kafka - Event streaming, producers, consumers"},
                {"name": "aws", "description": "AWS - Cloud architecture, IaC, serverless"},
                {"name": "springboot", "description": "Spring Boot - REST APIs, JPA, Security"},
                {"name": "springcloud", "description": "Spring Cloud - Microservices, service mesh"},
                {"name": "docker", "description": "Docker - Containers, Compose, Kubernetes"},
                {"name": "fedramp", "description": "FedRAMP - NIST 800-53, GovCloud compliance"},
                {"name": "hardening", "description": "Hardening - CIS benchmarks, seccomp, SBOM"},
                {"name": "zerotrust", "description": "Zero Trust - Identity-aware proxy, OPA, microsegmentation"},
            ]
        }

    elif name == "activate_agent":
        agent_name = arguments.get("agent_name")
        task = arguments.get("task", "")
        content = load_agent(agent_name)
        if content:
            return {
                "agent": agent_name,
                "activated": True,
                "task": task,
                "instructions": content[:2000] + "..." if len(content) > 2000 else content,
                "message": f"Agent '{agent_name}' activated. Following its expertise for: {task}"
            }
        return {"error": f"Agent '{agent_name}' not found"}

    # === RAG Tools ===
    elif name == "search_code":
        if _rag_pipeline is None:
            initialize_rag()
        if _rag_pipeline:
            results = _rag_pipeline.query(
                arguments.get("query"),
                n_results=arguments.get("n_results", 5)
            )
            return results
        return {"error": "RAG not initialized. Index project first."}

    elif name == "index_project":
        if _rag_pipeline is None:
            initialize_rag()
        if _rag_pipeline:
            force = arguments.get("force_reindex", False)
            _rag_pipeline.index_project(force_reindex=force)
            return {"status": "indexed", "project": str(get_project_root())}
        return {"error": "Failed to initialize RAG"}

    elif name == "get_code_stats":
        if _rag_pipeline:
            return _rag_pipeline.get_stats()
        return {"error": "RAG not initialized"}

    # === Memory Tools ===
    elif name == "save_memory":
        if _memory_service is None:
            initialize_memory()
        if _memory_service:
            _memory_service.save_session_memory(
                session_id=arguments["session_id"],
                content=arguments["content"],
                metadata=arguments.get("metadata", {})
            )
            return {"status": "saved", "session_id": arguments["session_id"]}
        return {"error": "Memory service not initialized"}

    elif name == "search_memory":
        if _memory_service is None:
            initialize_memory()
        if _memory_service:
            results = _memory_service.search_memory(
                query=arguments["query"],
                n_results=arguments.get("n_results", 5)
            )
            return {"results": results}
        return {"error": "Memory service not initialized"}

    elif name == "get_session_context":
        if _memory_service is None:
            initialize_memory()
        if _memory_service:
            memories = _memory_service.get_session_memory(
                session_id=arguments["session_id"]
            )
            return {"session_id": arguments["session_id"], "memories": memories}
        return {"error": "Memory service not initialized"}

    # === Context Tools ===
    elif name == "get_context_files":
        context_dir = server_dir.parent.parent
        files = []
        for f in context_dir.glob("*.md"):
            files.append({"name": f.name, "path": str(f)})
        return {"context_files": files}

    elif name == "read_context_file":
        filename = arguments["filename"]
        context_dir = server_dir.parent.parent
        filepath = context_dir / filename
        if filepath.exists():
            return {"filename": filename, "content": filepath.read_text()}
        return {"error": f"File not found: {filename}"}

    return {"error": f"Unknown tool: {name}"}


async def _install_template(target_path: str, include_agents: bool = True, include_rag: bool = True) -> dict:
    """Install template to target directory."""
    target = Path(target_path)
    target.mkdir(parents=True, exist_ok=True)

    # Source locations
    template_root = server_dir.parent.parent.parent  # Go up to template root
    claude_dir = server_dir.parent.parent  # .claude directory

    copied = []

    # Copy .claude directory
    target_claude = target / ".claude"
    target_claude.mkdir(exist_ok=True)

    # Copy context files
    for f in claude_dir.glob("*.md"):
        shutil.copy2(f, target_claude / f.name)
        copied.append(f".claude/{f.name}")

    # Copy commands
    if (claude_dir / "commands").exists():
        shutil.copytree(claude_dir / "commands", target_claude / "commands", dirs_exist_ok=True)
        copied.append(".claude/commands/")

    # Copy agents
    if include_agents and (claude_dir / "agents").exists():
        shutil.copytree(claude_dir / "agents", target_claude / "agents", dirs_exist_ok=True)
        copied.append(".claude/agents/")

    # Copy RAG
    if include_rag and (claude_dir / "rag").exists():
        shutil.copytree(claude_dir / "rag", target_claude / "rag", dirs_exist_ok=True)
        copied.append(".claude/rag/")

    # Copy root files
    root_files = ["PLANNING.md", "TASK.md", "SECURITY_COMPLIANCE.md"]
    for f in root_files:
        src = template_root / f
        if src.exists():
            shutil.copy2(src, target / f)
            copied.append(f)

    return {
        "status": "installed",
        "target": str(target),
        "files_copied": copied,
        "next_steps": [
            "Open project in Claude Code",
            "Run /context-init to load context",
            "Customize .claude/CLAUDE.md for your standards"
        ]
    }


# =============================================================================
# Server Entry Point
# =============================================================================

async def main():
    """Main entry point"""
    logger.info("Universal Context Template MCP Server starting...")

    transport = os.getenv('MCP_TRANSPORT', 'stdio')

    if transport == 'sse':
        # SSE transport for web clients
        from mcp.server.sse import sse_server
        port = int(os.getenv('MCP_PORT', '3000'))

        logger.info(f"Starting SSE server on port {port}")
        async with sse_server(port=port) as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    else:
        # stdio transport (default)
        from mcp.server.stdio import stdio_server

        logger.info("Server running on stdio")
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
