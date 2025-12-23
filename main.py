"""
ICDA Prototype - Intelligent Customer Data Access
Run with: uvicorn main:app --reload --port 8000

Supports two modes:
- LITE MODE: No AWS credentials - basic search, autocomplete, keyword knowledge search
- FULL MODE: With AWS credentials - AI queries, semantic search, vector embeddings
"""

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Must be before importing config

from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
import asyncio
import tempfile
import shutil

from icda.config import Config
from icda.cache import RedisCache
from icda.embeddings import EmbeddingClient
from icda.vector_index import VectorIndex
from icda.database import CustomerDB
from icda.nova import NovaClient
from icda.router import Router
from icda.session import SessionManager
from icda.knowledge import KnowledgeManager
from icda.knowledge_watcher import KnowledgeWatcher
from icda.knowledge_index_state import (
    compute_file_hash, load_index_state, save_index_state,
    update_file_state, remove_file_state, needs_reindex,
    get_stale_files, get_orphaned_entries, mark_full_reindex, get_stats as get_state_stats
)
from icda.download_tokens import DownloadTokenManager
from icda.progress_tracker import ProgressTracker, format_bytes, format_duration

# LLM Enforcer imports (provider-agnostic)
from icda.llm import LLMEnforcer, create_llm_client

# Address verification imports
from icda.address_index import AddressIndex
from icda.address_completer import NovaAddressCompleter
from icda.address_pipeline import AddressPipeline
from icda.address_router import router as address_router, configure_router
from icda.agents.orchestrator import AddressAgentOrchestrator
from icda.indexes.zip_database import ZipDatabase
from icda.indexes.address_vector_index import AddressVectorIndex

cfg = Config()  # Fresh instance after dotenv loaded

BASE_DIR = Path(__file__).parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
KNOWLEDGE_DATA_DIR = KNOWLEDGE_DIR / "data"
KNOWLEDGE_UPLOADED_DIR = KNOWLEDGE_DIR / "data-uploaded"
INDEX_STATE_FILE = KNOWLEDGE_DIR / ".index_state.json"

# Supported knowledge file extensions for auto-indexing
KNOWLEDGE_EXTENSIONS = {".md", ".txt", ".json", ".pdf", ".docx", ".doc", ".odt", ".odf", ".csv", ".xls", ".xlsx"}

# Globals
_cache: RedisCache = None
_embedder: EmbeddingClient = None
_vector_index: VectorIndex = None
_db: CustomerDB = None
_nova: NovaClient = None
_sessions: SessionManager = None
_router: Router = None
_knowledge: KnowledgeManager = None
_knowledge_watcher: KnowledgeWatcher = None
_index_state: dict = None

# Address verification globals
_address_index: AddressIndex = None
_address_completer: NovaAddressCompleter = None
_address_pipeline: AddressPipeline = None
_zip_database: ZipDatabase = None
_address_vector_index: AddressVectorIndex = None
_orchestrator: AddressAgentOrchestrator = None

# LLM Enforcer global (supports any secondary LLM provider)
_enforcer: LLMEnforcer = None

# Download Token Manager global
_download_manager: DownloadTokenManager = None

# Progress Tracker global (for real-time indexing progress)
_progress_tracker: ProgressTracker = None


def _extract_tags_from_content(content: str, filepath: Path) -> list[str]:
    """Extract tags from file content or infer from filename/path."""
    tags = []

    # Extract from YAML frontmatter if present
    if content.startswith("---"):
        lines = content.split("\n")
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                    continue
                else:
                    break
            if in_frontmatter and line.startswith("tags:"):
                tag_part = line.split(":", 1)[1].strip()
                if tag_part.startswith("["):
                    tags.extend([t.strip().strip('"\'') for t in tag_part.strip("[]").split(",")])

    # Infer from filepath
    filename_lower = filepath.stem.lower()
    if "puerto" in filename_lower or "pr-" in filename_lower:
        tags.extend(["puerto-rico", "urbanization"])
    if "address" in filename_lower:
        tags.append("addressing")
    if "example" in filename_lower:
        tags.append("examples")

    return list(set(tags))


async def auto_index_knowledge_documents(knowledge_manager: KnowledgeManager, state: dict = None) -> dict:
    """
    Auto-index all documents from /knowledge directory using content hash tracking.

    Uses hash comparison to avoid re-indexing unchanged files and cleans up orphaned entries.
    """
    if not knowledge_manager or not knowledge_manager.available:
        return {"indexed": 0, "skipped": 0, "failed": 0, "orphans_removed": 0}

    if not KNOWLEDGE_DIR.exists():
        return {"indexed": 0, "skipped": 0, "failed": 0, "orphans_removed": 0}

    # Load or use provided state
    if state is None:
        state = load_index_state(INDEX_STATE_FILE)

    indexed = 0
    skipped = 0
    failed = 0

    # Ensure data directories exist
    KNOWLEDGE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_UPLOADED_DIR.mkdir(parents=True, exist_ok=True)

    # Recursively find all knowledge files
    for filepath in KNOWLEDGE_DIR.rglob("*"):
        if not filepath.is_file():
            continue
        if filepath.suffix.lower() not in KNOWLEDGE_EXTENSIONS:
            continue
        if filepath.name.startswith(".") or filepath.name.lower() == "readme.md":
            continue

        relative_path = filepath.relative_to(KNOWLEDGE_DIR)
        filename = str(relative_path).replace("\\", "/")

        # Check if file needs reindexing using content hash
        try:
            current_hash = compute_file_hash(filepath)
        except Exception as e:
            print(f"  [ERROR] Hash failed: {filename} - {e}")
            failed += 1
            continue

        if not needs_reindex(state, filename, current_hash):
            skipped += 1
            continue

        category = filepath.parent.name if filepath.parent != KNOWLEDGE_DIR else "general"

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            tags = _extract_tags_from_content(content, filepath)

            result = await knowledge_manager.index_document(
                content=filepath,
                filename=filename,
                tags=tags,
                category=category
            )

            if result.get("success"):
                print(f"  [OK] Indexed: {filename} ({result.get('chunks_indexed', 0)} chunks)")
                update_file_state(
                    state,
                    filename,
                    result.get("doc_id", ""),
                    current_hash,
                    result.get("chunks_indexed", 0)
                )
                indexed += 1
            else:
                print(f"  [FAIL] Failed: {filename} - {result.get('error')}")
                failed += 1
        except Exception as e:
            print(f"  [ERROR] Error: {filename} - {e}")
            failed += 1

    # Clean up orphaned entries (files that were deleted)
    orphans = get_orphaned_entries(state, KNOWLEDGE_DIR)
    orphans_removed = 0
    for orphan_path, doc_id in orphans:
        if doc_id:
            try:
                await knowledge_manager.delete_document(doc_id)
                print(f"  [CLEANUP] Removed orphan: {orphan_path}")
                orphans_removed += 1
            except Exception as e:
                print(f"  [ERROR] Failed to remove orphan: {orphan_path} - {e}")
        remove_file_state(state, orphan_path)

    # Save updated state
    save_index_state(INDEX_STATE_FILE, state)

    return {"indexed": indexed, "skipped": skipped, "failed": failed, "orphans_removed": orphans_removed}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache, _embedder, _vector_index, _db, _nova, _sessions, _router, _knowledge, _knowledge_watcher
    global _address_index, _address_completer, _address_pipeline
    global _zip_database, _address_vector_index, _orchestrator
    global _enforcer, _download_manager, _index_state, _progress_tracker

    print("\n" + "="*50)
    print("  ICDA Startup")
    print("="*50 + "\n")

    # Startup - Redis is REQUIRED
    _cache = RedisCache(cfg.cache_ttl)
    await _cache.connect(cfg.redis_url)
    # Clear stale cache entries on startup to ensure fresh responses
    await _cache.clear()
    print("  Cache cleared on startup (removing stale entries)")
    if not _cache.available:
        print("\n[FATAL] Redis is REQUIRED but not available!")
        print("        Start Redis with: docker-compose up -d redis")
        raise RuntimeError("Redis is required for ICDA")

    # Initialize progress tracker for real-time indexing feedback
    _progress_tracker = ProgressTracker(_cache)
    print(f"  Progress tracker: {'enabled' if _progress_tracker.available else 'disabled (no Redis)'}")

    _embedder = EmbeddingClient(cfg.aws_region, cfg.titan_embed_model, cfg.embed_dimensions)

    # OpenSearch is REQUIRED
    _vector_index = VectorIndex(_embedder, cfg.opensearch_index)
    await _vector_index.connect(cfg.opensearch_host, cfg.aws_region)
    if not _vector_index.available:
        print("\n[FATAL] OpenSearch is REQUIRED but not available!")
        print("        Start OpenSearch with: docker-compose up -d opensearch")
        raise RuntimeError("OpenSearch is required for ICDA")

    _db = CustomerDB(BASE_DIR / "customer_data.json")
    print(f"Customer database: {len(_db.customers)} customers loaded")
    print(f"  Available states: {', '.join(_db.get_available_states()[:10])}{'...' if len(_db.available_states) > 10 else ''}")

    # ============================================================
    # AUTO-INDEX: Sync customer data to OpenSearch if needed
    # This ensures the vector index stays in sync when you:
    # - Switch to a different JSON file
    # - Connect to a database
    # - Update the customer data
    # ============================================================
    if _vector_index.available and _embedder.available:
        indexed_count = await _vector_index.customer_count()
        db_count = len(_db.customers)
        
        # Reindex if counts don't match or index is empty
        if indexed_count != db_count:
            print(f"\n  Auto-indexing customers (DB: {db_count:,}, Index: {indexed_count:,})...")
            result = await _vector_index.index_customers(_db.customers, batch_size=100)
            print(f"  Indexed {result.get('indexed', 0):,} customers into OpenSearch")
            if result.get('errors', 0) > 0:
                print(f"  Warnings: {result['errors']} indexing errors")
        else:
            print(f"  Customer index: {indexed_count:,} customers (in sync)")
    else:
        print("  Customer indexing skipped (OpenSearch or embeddings not available)")

    _sessions = SessionManager(_cache)

    # Initialize download token manager
    _download_manager = DownloadTokenManager(_cache)
    print(f"Download token manager: threshold={_download_manager.pagination_threshold}, preview={_download_manager.preview_size}")

    # Initialize address verification
    print("\nInitializing address verification...")
    _address_index = AddressIndex()
    _address_index.build_from_customers(_db.customers)
    print(f"  Address index: {_address_index.total_addresses} addresses")

    _zip_database = ZipDatabase()
    _zip_database.build_from_customers(_db.customers)
    print(f"  ZIP database: {_zip_database.total_zips} ZIPs")

    _address_completer = NovaAddressCompleter(cfg.aws_region, cfg.nova_model, _address_index)
    _address_pipeline = AddressPipeline(_address_index, _address_completer)

    _address_vector_index = None
    if cfg.opensearch_host and _embedder.available:
        _address_vector_index = AddressVectorIndex(_embedder)
        connected = await _address_vector_index.connect(cfg.opensearch_host, cfg.aws_region)
        if connected:
            print("  Address vector index: connected")
        else:
            _address_vector_index = None

    _orchestrator = AddressAgentOrchestrator(
        address_index=_address_index,
        zip_database=_zip_database,
        vector_index=_address_vector_index,
    )
    configure_router(_address_pipeline, _orchestrator)
    print("  Address verification: ready")

    # Initialize knowledge base BEFORE NovaClient so it can use RAG
    print("\nInitializing knowledge base...")
    opensearch_client = _vector_index.client if _vector_index.available else None
    _knowledge = KnowledgeManager(_embedder, opensearch_client)
    await _knowledge.ensure_index()

    # Auto-index knowledge documents (scans /knowledge folder recursively)
    # Load index state for hash-based change detection
    _index_state = load_index_state(INDEX_STATE_FILE)
    if KNOWLEDGE_DIR.exists():
        print("Auto-indexing knowledge documents from /knowledge folder...")
        result = await auto_index_knowledge_documents(_knowledge, _index_state)
        if result["indexed"]:
            print(f"  New/Modified: {result['indexed']}")
        if result["skipped"]:
            print(f"  Unchanged (skipped): {result['skipped']}")
        if result.get("orphans_removed"):
            print(f"  Orphans removed: {result['orphans_removed']}")
        if result["failed"]:
            print(f"  Failed: {result['failed']}")

    stats = await _knowledge.get_stats()
    print(f"  Knowledge base: {stats.get('unique_documents', 0)} docs, {stats.get('total_chunks', 0)} chunks ({stats.get('backend', 'unknown')})")

    # Start knowledge file watcher for auto-indexing new files
    async def index_file_callback(filepath: Path) -> dict:
        """Callback for file watcher to index new/modified files."""
        global _index_state
        try:
            relative_path = str(filepath.relative_to(KNOWLEDGE_DIR)).replace("\\", "/")
            content_hash = compute_file_hash(filepath)

            # Check if actually changed
            if _index_state and not needs_reindex(_index_state, relative_path, content_hash):
                return {"success": True, "skipped": True, "reason": "unchanged"}

            content = filepath.read_text(encoding="utf-8", errors="ignore")
            tags = _extract_tags_from_content(content, filepath)
            category = filepath.parent.name if filepath.parent != KNOWLEDGE_DIR else "general"

            result = await _knowledge.index_document(
                content=filepath,
                filename=relative_path,
                tags=tags,
                category=category
            )

            # Update index state on success
            if result.get("success") and _index_state is not None:
                update_file_state(
                    _index_state,
                    relative_path,
                    result.get("doc_id", ""),
                    content_hash,
                    result.get("chunks_indexed", 0)
                )
                save_index_state(INDEX_STATE_FILE, _index_state)

            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    _knowledge_watcher = KnowledgeWatcher(KNOWLEDGE_DIR, index_file_callback)
    _knowledge_watcher.start()

    # Initialize LLM Enforcer FIRST (optional, graceful degradation if no API key)
    # This must be done before NovaClient so it can be passed to the orchestrator
    # Supports any secondary LLM: Gemini, OpenAI, Claude, OpenRouter
    print("\nInitializing LLM Enforcer...")
    llm_client = create_llm_client(
        provider=cfg.secondary_llm_provider,
        model=cfg.secondary_llm_model if cfg.secondary_llm_model else None,
    )
    _enforcer = LLMEnforcer(
        client=llm_client,
        chunk_threshold=cfg.enforcer_chunk_threshold,
        query_sample_rate=cfg.enforcer_query_sample_rate,
        validation_interval_hours=cfg.enforcer_validation_interval,
    )
    if _enforcer.available:
        print(f"  Enforcer: enabled (provider: {llm_client.provider}, model: {llm_client.config.model})")
        print(f"  - L1 Chunk Gate: threshold {cfg.enforcer_chunk_threshold}")
        print(f"  - L2 Index Validation: every {cfg.enforcer_validation_interval}h")
        print(f"  - L3 Query Review: {int(cfg.enforcer_query_sample_rate * 100)}% sample")
    else:
        print("  Enforcer: disabled (no LLM API key found)")

    # Initialize NovaClient with 11-agent pipeline + LLM enforcer
    print("\nInitializing AI query pipeline...")

    # Build model routing config from settings
    model_config = {
        "nova_lite_model": cfg.nova_lite_model,
        "nova_pro_model": cfg.nova_pro_model,
        "model_routing_threshold": cfg.model_routing_threshold,
    }
    print(f"  Model routing: micro={cfg.nova_model}, lite={cfg.nova_lite_model}, pro={cfg.nova_pro_model}")

    _nova = NovaClient(
        region=cfg.aws_region,
        model=cfg.nova_model,
        db=_db,
        vector_index=_vector_index,
        knowledge=_knowledge,  # Pass knowledge manager for RAG
        address_orchestrator=_orchestrator,
        session_store=_sessions,
        llm_enforcer=_enforcer,  # Pass LLM enforcer for quality validation
        use_orchestrator=True,  # Enable 11-agent pipeline
        download_manager=_download_manager,  # Pass download manager for pagination
        model_config=model_config,  # Pass model routing config
        cache=_cache,  # Pass cache for memory storage
    )
    if _nova.available:
        if _nova.orchestrator:
            enforcer_status = f" + {llm_client.provider} enforcer" if _enforcer.available else ""
            memory_status = "enabled" if _nova.orchestrator._memory_agent.available else "disabled"
            print(f"  Nova AI: enabled with 11-agent orchestrator{enforcer_status}")
            print(f"    - KnowledgeAgent: {'enabled' if _nova.orchestrator._knowledge_agent.available else 'disabled'}")
            print(f"    - MemoryAgent: {memory_status}")
            print(f"    - PersonalityAgent: Witty Expert")
        else:
            print(f"  Nova AI: enabled (simple mode)")
    else:
        print("  Nova AI: disabled (no AWS credentials)")

    _router = Router(_cache, _vector_index, _db, _nova, _sessions)

    # Print mode summary
    mode = "FULL" if _nova.available and _embedder.available else "LITE"
    print("\n" + "="*50)
    print(f"  ICDA Running in {mode} MODE")
    print("="*50)
    if mode == "LITE":
        print("  (Add AWS credentials to .env for AI features)")
    print(f"\n  API: http://localhost:8000")
    print(f"  Docs: http://localhost:8000/docs\n")

    yield

    # Shutdown
    if _knowledge_watcher:
        _knowledge_watcher.stop()
    await _cache.close()
    await _vector_index.close()
    if _address_vector_index:
        await _address_vector_index.close()


app = FastAPI(title="ICDA", version="0.7.0", lifespan=lifespan)
app.include_router(address_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Sanitized global exception handler - never exposes internal details."""
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later."
            }
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


class GuardrailSettings(BaseModel):
    pii: bool = True
    financial: bool = True
    credentials: bool = True
    offtopic: bool = True


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    bypass_cache: bool = False
    guardrails: GuardrailSettings | None = None
    session_id: str | None = None  # For conversation continuity


@app.post("/api/query")
async def query(req: QueryRequest):
    guards = req.guardrails.model_dump() if req.guardrails else None
    return await _router.route(req.query, req.bypass_cache, guards, req.session_id)


@app.get("/api/query/download/{token}")
async def download_results(token: str, format: str = "json"):
    """Download full results using download token.

    Args:
        token: Download token from paginated query response.
        format: Output format ('json' or 'csv').

    Returns:
        Full result set in requested format.
    """
    if not _download_manager:
        return {"success": False, "error": "Download manager not available"}

    result = await _download_manager.get_full_results_async(token)
    if not result:
        return {"success": False, "error": "Invalid or expired download token"}

    if format == "csv":
        import csv
        import io
        from fastapi.responses import StreamingResponse

        data = result["data"]
        if not data:
            return {"success": False, "error": "No data to download"}

        output = io.StringIO()
        if data:
            # Get all unique keys from all records
            all_keys = set()
            for record in data:
                all_keys.update(record.keys())
            fieldnames = sorted(all_keys)

            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=icda_results_{token[:8]}.csv"}
        )

    # Default: JSON format
    return result


@app.get("/api/query/paginate/{token}")
async def paginate_results(token: str, offset: int = 0, limit: int = 15):
    """Get a page of results using download token for inline pagination.

    Args:
        token: Download token from paginated query response.
        offset: Starting index for results (0-based).
        limit: Maximum number of results to return.

    Returns:
        Paginated result set with metadata.
    """
    if not _download_manager:
        return {"success": False, "error": "Download manager not available"}

    result = await _download_manager.get_full_results_async(token)
    if not result:
        return {"success": False, "error": "Invalid or expired download token"}

    data = result.get("data", [])
    total = len(data)
    page_data = data[offset:offset + limit]

    return {
        "success": True,
        "data": page_data,
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": offset + limit < total,
        "remaining": max(0, total - offset - limit),
    }


@app.get("/api/health")
async def health():
    """Health check with mode status - flat structure for frontend compatibility"""
    nova_ok = _nova.available if _nova else False
    embedder_ok = _embedder.available if _embedder else False
    redis_ok = _cache.available if _cache else False
    opensearch_ok = _vector_index.available if _vector_index else False
    mode = "FULL" if nova_ok and embedder_ok else "LITE"

    # Flat structure expected by frontend
    return {
        "status": "healthy",
        "mode": mode,
        "redis": redis_ok,
        "opensearch": opensearch_ok,
        "embedder": embedder_ok,
        "nova": nova_ok,
        "customers": len(_db.customers) if _db else 0,
        # Extended info
        "knowledge": _knowledge.available if _knowledge else False,
    }


@app.get("/api/cache/stats")
async def cache_stats():
    return await _cache.stats()


@app.delete("/api/cache")
async def clear_cache():
    await _cache.clear()
    return {"status": "cleared"}


@app.get("/api/autocomplete/{field}")
async def autocomplete(field: str, q: str, limit: int = 10, fuzzy: bool = False):
    """Autocomplete for address, name, or city fields."""
    if fuzzy:
        return _db.autocomplete_fuzzy(field, q, limit)
    return _db.autocomplete(field, q, limit)


@app.get("/api/search/semantic")
async def semantic_search(q: str, limit: int = 10, state: str = None, city: str = None,
                          min_moves: int = None, status: str = None, customer_type: str = None):
    """Semantic search (requires OpenSearch + embeddings)"""
    filters = {}
    if state:
        filters["state"] = state
    if city:
        filters["city"] = city
    if min_moves:
        filters["min_moves"] = min_moves
    if status:
        filters["status"] = status
    if customer_type:
        filters["customer_type"] = customer_type

    return await _vector_index.search_customers_semantic(q, limit, filters if filters else None)


@app.get("/api/search/hybrid")
async def hybrid_search(q: str, limit: int = 10, state: str = None, min_moves: int = None):
    """Hybrid text + semantic search"""
    filters = {}
    if state:
        filters["state"] = state
    if min_moves:
        filters["min_moves"] = min_moves

    return await _vector_index.search_customers_hybrid(q, limit, filters if filters else None)


@app.get("/api/index/status")
async def index_status():
    return {
        "opensearch_available": _vector_index.available if _vector_index else False,
        "customer_index": _vector_index.customer_index if _vector_index else None,
        "indexed_customers": await _vector_index.customer_count() if _vector_index else 0
    }


@app.get("/api/data/states")
async def get_available_states():
    """Get all states available in the current data source.
    
    This is dynamically derived from the actual data, not hardcoded.
    Use this to know what states you can query for.
    """
    if not _db:
        return {"success": False, "error": "Database not loaded"}
    
    states = _db.get_available_states()
    counts = _db.get_state_counts()
    
    return {
        "success": True,
        "total_states": len(states),
        "total_customers": len(_db.customers),
        "states": [
            {
                "code": code,
                "name": _db.STATE_CODE_TO_NAME.get(code, code),
                "customer_count": counts.get(code, 0)
            }
            for code in states
        ]
    }


@app.post("/api/data/reindex")
async def reindex_customer_data(force: bool = False, async_mode: bool = False):
    """Trigger reindexing of customer data into OpenSearch.

    Use this when:
    - You've switched to a new data source
    - You've updated the customer data file
    - The index seems out of sync

    Args:
        force: If True, delete and recreate the index. If False, only reindex if counts differ.
        async_mode: If True, run in background and return operation_id for progress tracking.
    """
    if not _vector_index or not _vector_index.available:
        return {"success": False, "error": "OpenSearch not available"}
    if not _embedder or not _embedder.available:
        return {"success": False, "error": "Embeddings not available"}
    if not _db:
        return {"success": False, "error": "Database not loaded"}

    indexed_count = await _vector_index.customer_count()
    db_count = len(_db.customers)

    if not force and indexed_count == db_count:
        return {
            "success": True,
            "message": "Index already in sync",
            "indexed": indexed_count,
            "db_count": db_count
        }

    # Async mode: run in background with progress tracking
    if async_mode and _progress_tracker:
        op_id = await _progress_tracker.start_operation(
            operation_type="customer_index",
            total_items=db_count,
            total_batches=db_count // 100 + 1,
        )

        async def run_reindex():
            try:
                if force:
                    await _progress_tracker.update_progress(op_id, phase="Deleting old index")
                    await _vector_index.delete_customer_index()
                    await _cache.clear()

                await _progress_tracker.update_progress(op_id, phase="Indexing customers")

                # Progress callback for batch updates
                async def on_progress(processed: int, total: int):
                    batch = processed // 100
                    bytes_est = processed * 200  # ~200 bytes per customer
                    embeddings_est = processed  # 1 embedding per customer
                    await _progress_tracker.update_progress(
                        op_id,
                        processed=processed,
                        batch=batch,
                        bytes_processed=bytes_est,
                        embeddings=embeddings_est,
                        message=f"Indexed {processed:,} of {total:,} customers",
                    )

                # Create sync wrapper for async callback
                def sync_progress(processed: int, total: int):
                    asyncio.create_task(on_progress(processed, total))

                result = await _vector_index.index_customers(
                    _db.customers,
                    batch_size=100,
                    progress_callback=sync_progress,
                )

                await _progress_tracker.complete_operation(
                    op_id,
                    success=True,
                    message=f"Indexed {result.get('indexed', 0):,} customers ({result.get('errors', 0)} errors)",
                )
            except Exception as e:
                await _progress_tracker.complete_operation(
                    op_id,
                    success=False,
                    error=str(e),
                )

        # Start background task
        asyncio.create_task(run_reindex())

        return {
            "success": True,
            "async": True,
            "operation_id": op_id,
            "total_items": db_count,
            "stream_url": f"/api/data/reindex/stream/{op_id}",
            "status_url": f"/api/data/reindex/status/{op_id}",
        }

    # Synchronous mode (original behavior)
    if force:
        await _vector_index.delete_customer_index()
        await _cache.clear()

    result = await _vector_index.index_customers(_db.customers, batch_size=100)

    return {
        "success": True,
        "indexed": result.get("indexed", 0),
        "errors": result.get("errors", 0),
        "previous_count": indexed_count,
        "db_count": db_count,
        "available_states": _db.get_available_states()
    }


@app.get("/api/data/reindex/stream/{operation_id}")
async def stream_reindex_progress(operation_id: str):
    """Stream reindex progress via Server-Sent Events.

    Connect to this endpoint to receive real-time progress updates.
    Events: 'progress' (ongoing), 'complete' (finished), 'error' (failed)
    """
    if not _progress_tracker:
        return {"success": False, "error": "Progress tracking not available"}

    async def event_stream():
        async for event in _progress_tracker.stream_progress(operation_id):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/api/data/reindex/status/{operation_id}")
async def get_reindex_status(operation_id: str):
    """Get current status of a reindex operation."""
    if not _progress_tracker:
        return {"success": False, "error": "Progress tracking not available"}

    state = await _progress_tracker.get_progress(operation_id)
    if not state:
        return {"success": False, "error": "Operation not found"}

    return {
        "success": True,
        "operation": state.to_dict(),
        "formatted": {
            "elapsed": format_duration(state.elapsed_seconds),
            "remaining": format_duration(state.estimated_remaining_seconds) if state.estimated_remaining_seconds > 0 else "calculating...",
            "data_processed": format_bytes(state.bytes_processed),
            "rate": f"{state.items_per_second:.0f} items/sec" if state.items_per_second > 0 else "starting...",
        },
    }


@app.get("/api/data/reindex/active")
async def get_active_reindex_operations():
    """Get all active reindex operations."""
    if not _progress_tracker:
        return {"success": False, "error": "Progress tracking not available", "operations": []}

    operations = await _progress_tracker.get_active_operations()
    return {
        "success": True,
        "operations": [op.to_dict() for op in operations],
        "count": len(operations),
    }


# ==================== Knowledge Base API ====================

@app.get("/api/knowledge/stats")
async def knowledge_stats():
    if not _knowledge or not _knowledge.available:
        return {"available": False, "error": "Knowledge base not initialized"}
    return await _knowledge.get_stats()


@app.get("/api/knowledge/documents")
async def list_knowledge_documents(category: Optional[str] = None, limit: int = 50):
    if not _knowledge or not _knowledge.available:
        return {"success": False, "documents": [], "error": "Not available"}
    docs = await _knowledge.list_documents(category=category, limit=limit)
    return {"success": True, "documents": docs, "count": len(docs)}


@app.post("/api/knowledge/upload")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    category: str = Form("uploaded")
):
    """Upload and persist a document to the knowledge base."""
    global _index_state

    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    # Ensure upload directory exists
    KNOWLEDGE_UPLOADED_DIR.mkdir(parents=True, exist_ok=True)

    # Generate unique filename (handle duplicates)
    original_name = Path(file.filename).name
    target_path = KNOWLEDGE_UPLOADED_DIR / original_name
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while target_path.exists():
            target_path = KNOWLEDGE_UPLOADED_DIR / f"{stem}_{counter}{suffix}"
            counter += 1

    # Write file permanently
    with open(target_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    relative_path = str(target_path.relative_to(KNOWLEDGE_DIR)).replace("\\", "/")

    try:
        # Compute hash and index
        content_hash = compute_file_hash(target_path)

        result = await _knowledge.index_document(
            content=target_path,
            filename=relative_path,
            tags=tag_list,
            category=category
        )

        # Update index state
        if result.get("success") and _index_state is not None:
            update_file_state(
                _index_state,
                relative_path,
                result.get("doc_id", ""),
                content_hash,
                result.get("chunks_indexed", 0)
            )
            save_index_state(INDEX_STATE_FILE, _index_state)

        return {
            **result,
            "persisted_path": relative_path,
            "content_hash": content_hash
        }
    except Exception as e:
        # Clean up file on failure
        target_path.unlink(missing_ok=True)
        return {"success": False, "error": str(e)}


@app.post("/api/knowledge/upload-text")
async def upload_knowledge_text(
    title: str = Form(...),
    content: str = Form(...),
    tags: Optional[str] = Form(None),
    category: str = Form("general")
):
    """Upload raw text to the knowledge base."""
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    return await _knowledge.index_document(
        content=content,
        filename=title,
        tags=tag_list,
        category=category
    )


class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: int = 5
    tags: list[str] | None = None
    category: str | None = None


@app.post("/api/knowledge/search")
async def search_knowledge(req: KnowledgeSearchRequest):
    """Search the knowledge base."""
    if not _knowledge or not _knowledge.available:
        return {"success": False, "hits": [], "error": "Not available"}
    return await _knowledge.search(query=req.query, limit=req.limit, tags=req.tags, category=req.category)


@app.get("/api/knowledge/search")
async def search_knowledge_get(
    q: str,
    limit: int = 5,
    tags: Optional[str] = None,
    category: Optional[str] = None
):
    """Search the knowledge base (GET version)."""
    if not _knowledge or not _knowledge.available:
        return {"success": False, "hits": [], "error": "Not available"}
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()] if tags else None
    return await _knowledge.search(query=q, limit=limit, tags=tag_list, category=category)


@app.delete("/api/knowledge/documents/{doc_id}")
async def delete_knowledge_document(doc_id: str):
    """Delete a document from the knowledge base."""
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Not available"}
    result = await _knowledge.delete_document(doc_id)
    return {"success": result.get("deleted", 0) > 0, "doc_id": doc_id, **result}


@app.post("/api/knowledge/reindex")
async def reindex_knowledge_documents(force: bool = False):
    """
    Manually trigger re-indexing of knowledge documents.

    Args:
        force: If True, delete all documents and reindex everything.
               If False, only index new/modified files (incremental).
    """
    global _index_state

    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    if force:
        # Delete all documents and clear index state
        docs = await _knowledge.list_documents(limit=1000)
        deleted = 0
        for doc in docs:
            await _knowledge.delete_document(doc["doc_id"])
            deleted += 1
        # Clear index state for full reindex
        from icda.knowledge_index_state import create_empty_state, mark_full_reindex
        _index_state = create_empty_state()
        mark_full_reindex(_index_state)
        print(f"  Force reindex: deleted {deleted} documents")

    # Reload state for incremental reindex
    if _index_state is None:
        _index_state = load_index_state(INDEX_STATE_FILE)

    result = await auto_index_knowledge_documents(_knowledge, _index_state)
    return {"success": True, "mode": "full" if force else "incremental", **result}


# ==================== Admin API ====================

class AdminChunkUpdate(BaseModel):
    """Model for updating chunk metadata."""
    tags: list[str] | None = None
    category: str | None = None
    quality_score: float | None = None


class AdminSearchTest(BaseModel):
    """Model for testing search queries."""
    query: str
    limit: int = 10
    index: str | None = None
    filters: dict | None = None
    explain: bool = False


class AdminSavedQuery(BaseModel):
    """Model for saving test queries."""
    name: str
    query: str
    index: str | None = None
    filters: dict | None = None
    notes: str | None = None


# In-memory store for saved queries (would be Redis in production)
_saved_queries: dict = {}
_saved_query_counter: int = 0


@app.get("/api/admin/chunks")
async def admin_list_chunks(
    offset: int = 0,
    limit: int = 50,
    category: str | None = None,
    min_quality: float | None = None,
    max_quality: float | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
):
    """List all chunks with pagination and filtering."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}
    if not _knowledge or not _knowledge.available:
        return {"success": False, "chunks": [], "error": "Knowledge base not available"}

    all_docs = await _knowledge.list_documents(category=category, limit=1000)
    chunks = []

    for doc in all_docs:
        doc_chunks = await _knowledge.get_document_chunks(doc.get("doc_id", ""))
        for chunk in doc_chunks:
            quality = chunk.get("quality_score", 1.0)
            if min_quality and quality < min_quality:
                continue
            if max_quality and quality > max_quality:
                continue
            chunks.append({
                "chunk_id": chunk.get("chunk_id", ""),
                "doc_id": doc.get("doc_id", ""),
                "filename": doc.get("filename", "unknown"),
                "content": chunk.get("content", "")[:500],
                "content_length": len(chunk.get("content", "")),
                "category": doc.get("category", "general"),
                "tags": doc.get("tags", []),
                "quality_score": quality,
                "created_at": chunk.get("created_at", ""),
            })

    if sort_by == "quality_score":
        chunks.sort(key=lambda x: x.get("quality_score", 0), reverse=(sort_order == "desc"))
    elif sort_by == "content_length":
        chunks.sort(key=lambda x: x.get("content_length", 0), reverse=(sort_order == "desc"))
    else:
        chunks.sort(key=lambda x: x.get("created_at", ""), reverse=(sort_order == "desc"))

    total = len(chunks)
    paginated = chunks[offset:offset + limit]

    return {
        "success": True,
        "chunks": paginated,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total
    }


@app.get("/api/admin/chunks/{chunk_id}")
async def admin_get_chunk(chunk_id: str):
    """Get detailed information about a specific chunk."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    all_docs = await _knowledge.list_documents(limit=1000)
    for doc in all_docs:
        doc_chunks = await _knowledge.get_document_chunks(doc.get("doc_id", ""))
        for chunk in doc_chunks:
            if chunk.get("chunk_id") == chunk_id:
                return {
                    "success": True,
                    "chunk": {
                        "chunk_id": chunk_id,
                        "doc_id": doc.get("doc_id", ""),
                        "filename": doc.get("filename", "unknown"),
                        "content": chunk.get("content", ""),
                        "content_length": len(chunk.get("content", "")),
                        "category": doc.get("category", "general"),
                        "tags": doc.get("tags", []),
                        "quality_score": chunk.get("quality_score", 1.0),
                        "embedding_preview": chunk.get("embedding", [])[:10] if chunk.get("embedding") else None,
                        "embedding_dimensions": len(chunk.get("embedding", [])) if chunk.get("embedding") else 0,
                        "created_at": chunk.get("created_at", ""),
                        "metadata": chunk.get("metadata", {})
                    }
                }

    return {"success": False, "error": "Chunk not found"}


@app.patch("/api/admin/chunks/{chunk_id}")
async def admin_update_chunk(chunk_id: str, update: AdminChunkUpdate):
    """Update chunk metadata (tags, category, quality_score)."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    return {"success": False, "error": "Chunk updates not yet implemented"}


@app.delete("/api/admin/chunks/{chunk_id}")
async def admin_delete_chunk(chunk_id: str):
    """Delete a specific chunk."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    return {"success": False, "error": "Individual chunk deletion not yet implemented"}


@app.post("/api/admin/chunks/{chunk_id}/reembed")
async def admin_reembed_chunk(chunk_id: str):
    """Regenerate embedding for a specific chunk."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}
    if not _embedder or not _embedder.available:
        return {"success": False, "error": "Embedding service not available"}

    return {"success": False, "error": "Re-embedding not yet implemented"}


@app.get("/api/admin/chunks/embeddings/visualization")
async def admin_embedding_visualization(sample_size: int = 100):
    """Get 2D projection of chunk embeddings for visualization (t-SNE/UMAP style)."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}
    if not _knowledge or not _knowledge.available:
        return {"success": False, "points": [], "error": "Knowledge base not available"}

    return {
        "success": True,
        "points": [],
        "message": "Embedding visualization requires sklearn/umap - not yet implemented"
    }


@app.get("/api/admin/index/stats")
async def admin_index_stats():
    """Get detailed statistics for all indexes."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    stats = {
        "knowledge": {},
        "customers": {},
        "addresses": {},
        "services": {},
        "enforcer": {}
    }

    if _knowledge and _knowledge.available:
        kb_stats = await _knowledge.get_stats()
        stats["knowledge"] = kb_stats

    if _vector_index and _vector_index.available:
        customer_count = await _vector_index.customer_count()
        stats["customers"] = {
            "indexed": customer_count,
            "index_name": _vector_index.customer_index
        }

    if _address_vector_index:
        stats["addresses"] = {
            "available": True,
            "total_addresses": _address_index.total_addresses if _address_index else 0
        }

    stats["services"] = {
        "redis": _cache.available if _cache else False,
        "opensearch": _vector_index.available if _vector_index else False,
        "embeddings": _embedder.available if _embedder else False,
        "nova_ai": _nova.available if _nova else False
    }

    if _enforcer:
        stats["enforcer"] = _enforcer.get_metrics()

    return {"success": True, "stats": stats}


@app.get("/api/admin/index/health")
async def admin_index_health():
    """Get health status of all indexes."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    health = {
        "overall": "healthy",
        "indexes": {},
        "issues": []
    }

    if _knowledge and _knowledge.available:
        kb_stats = await _knowledge.get_stats()
        kb_health = "healthy"
        if kb_stats.get("total_chunks", 0) == 0:
            kb_health = "empty"
            health["issues"].append("Knowledge base has no chunks indexed")
        health["indexes"]["knowledge"] = {
            "status": kb_health,
            "chunks": kb_stats.get("total_chunks", 0),
            "documents": kb_stats.get("unique_documents", 0)
        }
    else:
        health["indexes"]["knowledge"] = {"status": "unavailable"}
        health["issues"].append("Knowledge base not available")

    if _vector_index and _vector_index.available:
        customer_count = await _vector_index.customer_count()
        health["indexes"]["customers"] = {
            "status": "healthy" if customer_count > 0 else "empty",
            "count": customer_count
        }
    else:
        health["indexes"]["customers"] = {"status": "unavailable"}
        health["issues"].append("Customer index not available")

    if len(health["issues"]) > 0:
        health["overall"] = "degraded"

    return {"success": True, "health": health}


@app.post("/api/admin/index/reindex")
async def admin_trigger_reindex(index_name: str = "all"):
    """Trigger re-indexing of specified index."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    results = {}

    if index_name in ("all", "knowledge"):
        if _knowledge and _knowledge.available:
            state = load_index_state(INDEX_STATE_FILE) if _index_state is None else _index_state
            result = await auto_index_knowledge_documents(_knowledge, state)
            results["knowledge"] = result
        else:
            results["knowledge"] = {"error": "Not available"}

    if index_name in ("all", "customers"):
        if _vector_index and _vector_index.available and _db:
            count = await _vector_index.index_customers(_db.customers)
            results["customers"] = {"indexed": count}
        else:
            results["customers"] = {"error": "Not available"}

    return {"success": True, "results": results}


@app.delete("/api/admin/index/{index_name}")
async def admin_clear_index(index_name: str):
    """Clear all data from specified index."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    if index_name == "knowledge":
        if _knowledge and _knowledge.available:
            docs = await _knowledge.list_documents(limit=1000)
            deleted = 0
            for doc in docs:
                result = await _knowledge.delete_document(doc.get("doc_id", ""))
                deleted += result.get("deleted", 0)
            return {"success": True, "deleted": deleted}
        return {"success": False, "error": "Knowledge base not available"}

    return {"success": False, "error": f"Unknown index: {index_name}"}


@app.get("/api/admin/index/export")
async def admin_export_stats():
    """Export comprehensive index statistics for reporting."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    from datetime import datetime

    stats = await admin_index_stats()
    health = await admin_index_health()

    return {
        "success": True,
        "export": {
            "timestamp": datetime.utcnow().isoformat(),
            "stats": stats.get("stats", {}),
            "health": health.get("health", {}),
            "config": {
                "opensearch_host": cfg.opensearch_host,
                "redis_url": bool(cfg.redis_url),
                "federation_enabled": cfg.enable_federation,
                "enforcer_enabled": cfg.enable_llm_enforcer,
                "admin_enabled": cfg.admin_enabled
            }
        }
    }


@app.post("/api/admin/search/test")
async def admin_test_search(req: AdminSearchTest):
    """Test a search query with debug information."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    import time
    start = time.time()

    results = []
    debug_info = {
        "query": req.query,
        "index": req.index or "knowledge",
        "filters": req.filters,
        "explain": req.explain
    }

    if (req.index or "knowledge") == "knowledge":
        if _knowledge and _knowledge.available:
            search_result = await _knowledge.search(
                query=req.query,
                limit=req.limit,
                tags=req.filters.get("tags") if req.filters else None,
                category=req.filters.get("category") if req.filters else None
            )
            results = search_result.get("hits", [])
            debug_info["backend"] = search_result.get("backend", "unknown")
            debug_info["search_type"] = search_result.get("search_type", "unknown")
    elif req.index == "customers":
        if _vector_index and _vector_index.available:
            search_result = await _vector_index.search_customers_semantic(
                req.query,
                req.limit,
                req.filters
            )
            results = search_result.get("hits", [])

    elapsed = time.time() - start
    debug_info["elapsed_ms"] = round(elapsed * 1000, 2)
    debug_info["result_count"] = len(results)

    return {
        "success": True,
        "results": results,
        "debug": debug_info if req.explain else None
    }


@app.post("/api/admin/search/saved")
async def admin_save_query(req: AdminSavedQuery):
    """Save a test query for later use."""
    global _saved_query_counter

    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    _saved_query_counter += 1
    query_id = f"sq_{_saved_query_counter}"

    from datetime import datetime
    _saved_queries[query_id] = {
        "id": query_id,
        "name": req.name,
        "query": req.query,
        "index": req.index,
        "filters": req.filters,
        "notes": req.notes,
        "created_at": datetime.utcnow().isoformat()
    }

    return {"success": True, "query_id": query_id}


@app.get("/api/admin/search/saved")
async def admin_list_saved_queries():
    """List all saved test queries."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    return {
        "success": True,
        "queries": list(_saved_queries.values()),
        "count": len(_saved_queries)
    }


@app.delete("/api/admin/search/saved/{query_id}")
async def admin_delete_saved_query(query_id: str):
    """Delete a saved test query."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    if query_id in _saved_queries:
        del _saved_queries[query_id]
        return {"success": True, "deleted": query_id}

    return {"success": False, "error": "Query not found"}


@app.post("/api/admin/search/saved/{query_id}/run")
async def admin_run_saved_query(query_id: str):
    """Run a saved test query."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    if query_id not in _saved_queries:
        return {"success": False, "error": "Query not found"}

    saved = _saved_queries[query_id]
    return await admin_test_search(AdminSearchTest(
        query=saved["query"],
        index=saved.get("index"),
        filters=saved.get("filters"),
        explain=True
    ))


@app.get("/api/admin/enforcer/metrics")
async def admin_enforcer_metrics():
    """Get LLM Enforcer pipeline metrics."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    if not _enforcer:
        return {
            "success": True,
            "available": False,
            "metrics": None,
            "message": "Enforcer not initialized"
        }

    return {
        "success": True,
        "available": _enforcer.available,
        "metrics": _enforcer.get_metrics(),
        "config": {
            "provider": cfg.secondary_llm_provider,
            "model": cfg.secondary_llm_model or "auto",
            "chunk_threshold": cfg.enforcer_chunk_threshold,
            "query_sample_rate": cfg.enforcer_query_sample_rate,
            "validation_interval_hours": cfg.enforcer_validation_interval
        }
    }


@app.get("/api/admin/chunks/quality")
async def admin_chunks_quality(threshold: float = 0.6, limit: int = 50):
    """Get chunks below quality threshold for review."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}
    if not _knowledge or not _knowledge.available:
        return {"success": False, "chunks": [], "error": "Knowledge base not available"}

    all_docs = await _knowledge.list_documents(limit=1000)
    low_quality = []

    for doc in all_docs:
        doc_chunks = await _knowledge.get_document_chunks(doc.get("doc_id", ""))
        for chunk in doc_chunks:
            quality = chunk.get("quality_score", 1.0)
            if quality < threshold:
                low_quality.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "doc_id": doc.get("doc_id", ""),
                    "filename": doc.get("filename", "unknown"),
                    "content_preview": chunk.get("content", "")[:200],
                    "quality_score": quality,
                    "category": doc.get("category", "general"),
                })

    low_quality.sort(key=lambda x: x.get("quality_score", 0))
    return {
        "success": True,
        "chunks": low_quality[:limit],
        "total_below_threshold": len(low_quality),
        "threshold": threshold
    }


@app.post("/api/admin/enforcer/evaluate-chunk")
async def admin_evaluate_chunk(chunk_id: str, content: str, source: str = "manual"):
    """Manually trigger L1 chunk quality evaluation."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    if not _enforcer or not _enforcer.available:
        return {"success": False, "error": "Enforcer not available"}

    result = await _enforcer.evaluate_chunk(
        chunk_id=chunk_id,
        content=content,
        source=source,
        content_type="text"
    )

    return {
        "success": True,
        "result": {
            "passed": result.passed,
            "overall_score": result.overall_score,
            "coherence": result.quality.coherence,
            "completeness": result.quality.completeness,
            "relevance": result.quality.relevance,
            "issues": result.quality.issues,
            "suggestions": result.quality.suggestions
        }
    }


@app.post("/api/admin/enforcer/validate-index")
async def admin_validate_index():
    """Manually trigger L2 index validation."""
    if not cfg.admin_enabled:
        return {"success": False, "error": "Admin API disabled"}

    if not _enforcer or not _enforcer.available:
        return {"success": False, "error": "Enforcer not available"}

    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    all_docs = await _knowledge.list_documents(limit=500)
    chunks = []
    for doc in all_docs:
        doc_chunks = await _knowledge.get_document_chunks(doc.get("doc_id", ""))
        for chunk in doc_chunks:
            chunks.append({
                "chunk_id": chunk.get("chunk_id", ""),
                "content": chunk.get("content", ""),
                "source": doc.get("filename", "unknown"),
                "category": doc.get("category", "general")
            })

    report = await _enforcer.validate_index(chunks)

    return {
        "success": True,
        "report": {
            "health_score": report.health_score,
            "total_chunks": report.total_chunks,
            "sampled_chunks": report.sampled_chunks,
            "duplicate_groups": len(report.duplicate_groups),
            "stale_chunks": len(report.stale_chunks),
            "coverage_gaps": report.coverage_gaps,
            "recommendations": report.recommendations
        }
    }


# ==================== Frontend ====================

frontend_dist = BASE_DIR / "frontend" / "dist"
frontend_index = frontend_dist / "index.html"

# Mount static assets BEFORE catch-all routes
if frontend_dist.exists() and (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

# Serve site.webmanifest from dist if present, otherwise fall back to frontend/public for development
@app.get("/site.webmanifest")
async def site_manifest():
    candidates = [
        frontend_dist / "site.webmanifest",
        BASE_DIR / "frontend" / "public" / "site.webmanifest",
    ]
    for p in candidates:
        if p.exists():
            return FileResponse(p)
    return JSONResponse(status_code=404, content={"error": "site.webmanifest not found"})


@app.get("/", response_class=HTMLResponse)
async def root():
    if frontend_index.exists():
        return frontend_index.read_text()
    return (BASE_DIR / "templates/index.html").read_text()


# SPA catch-all route - serves index.html for client-side routing (admin, etc.)
async def _serve_spa():
    if frontend_index.exists():
        return HTMLResponse(frontend_index.read_text())
    return HTMLResponse((BASE_DIR / "templates/index.html").read_text())


@app.get("/admin", response_class=HTMLResponse)
async def spa_admin_root():
    return await _serve_spa()


@app.get("/admin/{path:path}", response_class=HTMLResponse)
async def spa_admin_path(path: str):
    return await _serve_spa()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
