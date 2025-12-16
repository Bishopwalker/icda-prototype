"""
MCP Knowledge Server - Simple RAG Document Management for ICDA
=============================================================

This MCP server provides tools for uploading, indexing, and searching
knowledge documents. Integrates with the existing ICDA OpenSearch/Titan
infrastructure.

Tools:
  - upload_document: Add a document to the knowledge base
  - search_knowledge: Search indexed documents
  - list_documents: List all indexed documents
  - delete_document: Remove a document
  - watch_folder: Auto-index documents dropped into a folder
"""

import asyncio
import json
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from knowledge_index import KnowledgeIndex
from document_processor import DocumentProcessor
from enforcer import EnforcerOrchestrator, BatchKnowledgeItem

load_dotenv()

# Initialize MCP server
server = Server("knowledge-server")

# Global instances (initialized on startup)
knowledge_index: KnowledgeIndex | None = None
doc_processor: DocumentProcessor | None = None
enforcer_orchestrator: EnforcerOrchestrator | None = None

# Configuration from environment
WATCH_FOLDER = os.getenv("KNOWLEDGE_WATCH_FOLDER", "./knowledge_docs")
INDEX_NAME = os.getenv("KNOWLEDGE_INDEX", "icda-knowledge")


async def get_index() -> KnowledgeIndex:
    """Lazy initialization of knowledge index."""
    global knowledge_index
    if knowledge_index is None:
        knowledge_index = KnowledgeIndex(INDEX_NAME)
        await knowledge_index.connect()
    return knowledge_index


def get_processor() -> DocumentProcessor:
    """Lazy initialization of document processor."""
    global doc_processor
    if doc_processor is None:
        doc_processor = DocumentProcessor()
    return doc_processor


async def get_enforcer() -> EnforcerOrchestrator:
    """Lazy initialization of enforcer orchestrator."""
    global enforcer_orchestrator
    if enforcer_orchestrator is None:
        enforcer_orchestrator = EnforcerOrchestrator(index_name=INDEX_NAME)
        # Connect to same OpenSearch as knowledge index
        index = await get_index()
        if hasattr(index, 'client'):
            enforcer_orchestrator.set_clients(opensearch_client=index.client)
    return enforcer_orchestrator


# ============== MCP Tools ==============

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Register available tools."""
    return [
        Tool(
            name="upload_document",
            description="""Upload and index a document for RAG knowledge retrieval.
            
Supports: .txt, .md, .pdf, .docx, .json
Documents are chunked, embedded via Titan, and indexed in OpenSearch.

Example: upload_document(file_path="/path/to/design_doc.md", tags=["architecture", "api"])
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the document file"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for filtering (e.g., ['api', 'architecture'])",
                        "default": []
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category (e.g., 'design', 'requirements', 'meeting-notes')",
                        "default": "general"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="upload_text",
            description="""Upload raw text content directly as a knowledge document.
            
Useful for quick notes, code snippets, or content not in a file.

Example: upload_text(title="API Endpoints", content="...", tags=["api"])
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title/name for this knowledge entry"
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to index"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for filtering",
                        "default": []
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category",
                        "default": "general"
                    }
                },
                "required": ["title", "content"]
            }
        ),
        Tool(
            name="search_knowledge",
            description="""Search the knowledge base using semantic similarity.
            
Returns relevant chunks from indexed documents based on your query.
Use this to find context about the ICDA project, APIs, decisions, etc.

Example: search_knowledge(query="how does address verification work", limit=5)
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default: 5)",
                        "default": 5
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (optional)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_documents",
            description="""List all documents in the knowledge base.
            
Shows document names, categories, tags, chunk counts, and upload dates.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max documents to return (default: 50)",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="delete_document",
            description="""Delete a document and all its chunks from the knowledge base.

Example: delete_document(document_id="abc123")
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The document ID to delete (from list_documents)"
                    }
                },
                "required": ["document_id"]
            }
        ),
        Tool(
            name="get_stats",
            description="Get statistics about the knowledge base (document count, total chunks, index size).",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="reindex_all",
            description="""Re-process and reindex all documents.

Useful after upgrading embedding models or changing chunk settings.
WARNING: This will delete and recreate the entire index.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to proceed"
                    }
                },
                "required": ["confirm"]
            }
        ),
        # ============== 5-Agent Enforcer Tools ==============
        Tool(
            name="enforce_document",
            description="""Process a document through the 5-agent enforcer pipeline.

The pipeline validates and indexes knowledge with quality gates:
1. IntakeGuard - Validates format, detects PR/batch content
2. SemanticMiner - Extracts entities, patterns, rules
3. ContextLinker - Links to existing knowledge
4. QualityEnforcer - Russian Olympic Judge validation
5. IndexSync - Indexes to OpenSearch with embeddings

Returns detailed results from each agent and all quality gate outcomes.

Example: enforce_document(file_path="/path/to/pr-rules.md")
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to document file to process"
                    },
                    "content": {
                        "type": "string",
                        "description": "Or provide raw content directly (if no file_path)"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata to attach",
                        "default": {}
                    }
                }
            }
        ),
        Tool(
            name="enforce_batch",
            description="""Process multiple items through the 5-agent enforcer pipeline.

Handles batches of addresses, rules, or examples with parallel processing.
Each item goes through all 5 agents with quality validation.

Example: enforce_batch(items=[{"id": "1", "content": "..."}, ...], parallel_limit=5)
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "content": {"type": "string"},
                                "content_type": {"type": "string", "default": "unknown"},
                                "context": {"type": "object", "default": {}}
                            },
                            "required": ["id", "content"]
                        },
                        "description": "List of items to process"
                    },
                    "parallel_limit": {
                        "type": "integer",
                        "description": "Max concurrent processing (default: 5)",
                        "default": 5
                    }
                },
                "required": ["items"]
            }
        ),
        Tool(
            name="get_enforcer_stats",
            description="""Get statistics from the 5-agent enforcer pipeline.

Returns processing counts, success rates, and per-agent metrics.
""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="search_pr_knowledge",
            description="""Search for Puerto Rico specific knowledge.

Filters results to only PR-relevant content (urbanization, ZIP 006-009, etc).

Example: search_pr_knowledge(query="urbanization requirements", limit=10)
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for PR knowledge"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    try:
        if name == "upload_document":
            result = await handle_upload_document(
                arguments["file_path"],
                arguments.get("tags", []),
                arguments.get("category", "general")
            )
        elif name == "upload_text":
            result = await handle_upload_text(
                arguments["title"],
                arguments["content"],
                arguments.get("tags", []),
                arguments.get("category", "general")
            )
        elif name == "search_knowledge":
            result = await handle_search(
                arguments["query"],
                arguments.get("limit", 5),
                arguments.get("tags"),
                arguments.get("category")
            )
        elif name == "list_documents":
            result = await handle_list_documents(
                arguments.get("category"),
                arguments.get("limit", 50)
            )
        elif name == "delete_document":
            result = await handle_delete_document(arguments["document_id"])
        elif name == "get_stats":
            result = await handle_get_stats()
        elif name == "reindex_all":
            if not arguments.get("confirm"):
                result = {"error": "Must set confirm=true to reindex"}
            else:
                result = await handle_reindex_all()
        # 5-Agent Enforcer Tools
        elif name == "enforce_document":
            result = await handle_enforce_document(
                arguments.get("file_path"),
                arguments.get("content"),
                arguments.get("metadata", {})
            )
        elif name == "enforce_batch":
            result = await handle_enforce_batch(
                arguments["items"],
                arguments.get("parallel_limit", 5)
            )
        elif name == "get_enforcer_stats":
            result = await handle_get_enforcer_stats()
        elif name == "search_pr_knowledge":
            result = await handle_search_pr_knowledge(
                arguments["query"],
                arguments.get("limit", 10)
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
            
    except Exception as e:
        result = {"error": str(e)}
    
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


# ============== Tool Handlers ==============

async def handle_upload_document(
    file_path: str,
    tags: list[str],
    category: str
) -> dict:
    """Process and index a document file."""
    path = Path(file_path)
    
    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}
    
    # Process document into chunks
    processor = get_processor()
    chunks = processor.process_file(path)
    
    if not chunks:
        return {"success": False, "error": "Failed to extract content from file"}
    
    # Generate document ID from content hash
    content_hash = hashlib.sha256(
        "".join(c["text"] for c in chunks).encode()
    ).hexdigest()[:12]
    doc_id = f"{path.stem}_{content_hash}"
    
    # Index chunks
    index = await get_index()
    result = await index.index_document(
        doc_id=doc_id,
        filename=path.name,
        chunks=chunks,
        tags=tags,
        category=category,
        source_path=str(path)
    )
    
    return {
        "success": True,
        "document_id": doc_id,
        "filename": path.name,
        "chunks_indexed": result["indexed"],
        "category": category,
        "tags": tags
    }


async def handle_upload_text(
    title: str,
    content: str,
    tags: list[str],
    category: str
) -> dict:
    """Index raw text content."""
    processor = get_processor()
    chunks = processor.chunk_text(content, title)
    
    # Generate document ID
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    doc_id = f"{title.replace(' ', '_').lower()}_{content_hash}"
    
    index = await get_index()
    result = await index.index_document(
        doc_id=doc_id,
        filename=title,
        chunks=chunks,
        tags=tags,
        category=category,
        source_path="<direct_upload>"
    )
    
    return {
        "success": True,
        "document_id": doc_id,
        "title": title,
        "chunks_indexed": result["indexed"],
        "category": category,
        "tags": tags
    }


async def handle_search(
    query: str,
    limit: int,
    tags: list[str] | None,
    category: str | None
) -> dict:
    """Search the knowledge base."""
    index = await get_index()
    results = await index.search(
        query=query,
        limit=limit,
        tags=tags,
        category=category
    )
    
    return {
        "success": True,
        "query": query,
        "results": results["hits"],
        "total_matches": results["total"]
    }


async def handle_list_documents(category: str | None, limit: int) -> dict:
    """List indexed documents."""
    index = await get_index()
    docs = await index.list_documents(category=category, limit=limit)
    
    return {
        "success": True,
        "documents": docs,
        "count": len(docs)
    }


async def handle_delete_document(doc_id: str) -> dict:
    """Delete a document."""
    index = await get_index()
    result = await index.delete_document(doc_id)
    
    return {
        "success": result["deleted"] > 0,
        "document_id": doc_id,
        "chunks_deleted": result["deleted"]
    }


async def handle_get_stats() -> dict:
    """Get index statistics."""
    index = await get_index()
    stats = await index.get_stats()
    
    return {
        "success": True,
        **stats
    }


async def handle_reindex_all() -> dict:
    """Reindex everything (dangerous!)."""
    index = await get_index()
    result = await index.reindex_all()

    return {
        "success": True,
        "message": "Reindex complete",
        **result
    }


# ============== Enforcer Tool Handlers ==============

async def handle_enforce_document(
    file_path: str | None,
    content: str | None,
    metadata: dict
) -> dict:
    """Process document through 5-agent enforcer pipeline."""
    if not file_path and not content:
        return {"success": False, "error": "Must provide file_path or content"}

    # Read file content if path provided
    if file_path:
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        content = path.read_text(encoding="utf-8")
        filename = path.name
    else:
        filename = metadata.get("title", "direct_upload.txt")

    # Get enforcer and process
    enforcer = await get_enforcer()
    result = await enforcer.process(
        content=content,
        filename=filename,
        metadata=metadata
    )

    return {
        "success": result.success,
        "document_id": result.index.doc_id if result.index else None,
        "gates_passed": result.gates_passed,
        "gates_failed": result.gates_failed,
        "quality_score": result.quality.overall_score if result.quality else 0.0,
        "chunks_created": result.index.chunks_created if result.index else 0,
        "is_pr_relevant": result.intake.is_pr_relevant if result.intake else False,
        "total_time_ms": result.total_time_ms,
        "agent_timings": result.agent_timings,
    }


async def handle_enforce_batch(
    items: list[dict],
    parallel_limit: int
) -> dict:
    """Process batch through 5-agent enforcer pipeline."""
    # Convert to BatchKnowledgeItem objects
    batch_items = [
        BatchKnowledgeItem(
            id=item["id"],
            content=item["content"],
            content_type=item.get("content_type", "unknown"),
            context=item.get("context", {})
        )
        for item in items
    ]

    # Get enforcer and process batch
    enforcer = await get_enforcer()
    results, summary = await enforcer.process_batch(
        items=batch_items,
        parallel_limit=parallel_limit
    )

    return {
        "success": summary.success_rate > 0.5,
        "summary": summary.to_dict(),
        "results": [r.to_dict() for r in results],
    }


async def handle_get_enforcer_stats() -> dict:
    """Get enforcer pipeline statistics."""
    enforcer = await get_enforcer()
    stats = enforcer.get_stats()

    return {
        "success": True,
        **stats
    }


async def handle_search_pr_knowledge(query: str, limit: int) -> dict:
    """Search for PR-specific knowledge."""
    index = await get_index()

    # Search with PR filter
    results = await index.search(
        query=query,
        limit=limit,
        filters={"pr_relevant": True}
    )

    return {
        "success": True,
        "query": query,
        "filter": "pr_relevant=true",
        "results": results.get("hits", []),
        "total_matches": results.get("total", 0)
    }


# ============== Main Entry ==============

async def main():
    """Run the MCP server."""
    print("🚀 Starting MCP Knowledge Server...")
    print(f"   Index: {INDEX_NAME}")
    print(f"   Watch folder: {WATCH_FOLDER}")
    
    # Ensure watch folder exists
    Path(WATCH_FOLDER).mkdir(parents=True, exist_ok=True)
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
