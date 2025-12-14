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

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
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

# Knowledge document registry - auto-indexed on startup
KNOWLEDGE_DOCUMENTS = [
    {
        "file": "puerto-rico-urbanization-addressing.md",
        "category": "address-standards",
        "tags": ["puerto-rico", "urbanization", "usps", "addressing", "zip-codes", "postal"]
    },
    # Add more documents here as needed
]

# Globals
_cache: RedisCache = None
_embedder: EmbeddingClient = None
_vector_index: VectorIndex = None
_db: CustomerDB = None
_nova: NovaClient = None
_sessions: SessionManager = None
_router: Router = None
_knowledge: KnowledgeManager = None

# Address verification globals
_address_index: AddressIndex = None
_address_completer: NovaAddressCompleter = None
_address_pipeline: AddressPipeline = None
_zip_database: ZipDatabase = None
_address_vector_index: AddressVectorIndex = None
_orchestrator: AddressAgentOrchestrator = None


async def auto_index_knowledge_documents(knowledge_manager: KnowledgeManager) -> dict:
    """Auto-index knowledge documents from /knowledge directory on startup."""
    if not knowledge_manager or not knowledge_manager.available:
        return {"indexed": 0, "skipped": 0, "failed": 0}

    if not KNOWLEDGE_DIR.exists():
        return {"indexed": 0, "skipped": 0, "failed": 0}

    existing_docs = await knowledge_manager.list_documents(limit=1000)
    existing_filenames = {doc["filename"] for doc in existing_docs}

    indexed = 0
    skipped = 0
    failed = 0

    for doc_config in KNOWLEDGE_DOCUMENTS:
        filepath = KNOWLEDGE_DIR / doc_config["file"]

        if not filepath.exists():
            print(f"  ⚠ Knowledge file not found: {doc_config['file']}")
            failed += 1
            continue

        if doc_config["file"] in existing_filenames:
            skipped += 1
            continue

        try:
            result = await knowledge_manager.index_document(
                content=filepath,
                filename=doc_config["file"],
                tags=doc_config.get("tags", []),
                category=doc_config.get("category", "general")
            )

            if result.get("success"):
                print(f"  ✓ Indexed: {doc_config['file']} ({result.get('chunks_indexed', 0)} chunks)")
                indexed += 1
            else:
                print(f"  ✗ Failed: {doc_config['file']} - {result.get('error')}")
                failed += 1
        except Exception as e:
            print(f"  ✗ Error: {doc_config['file']} - {e}")
            failed += 1

    return {"indexed": indexed, "skipped": skipped, "failed": failed}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache, _embedder, _vector_index, _db, _nova, _sessions, _router, _knowledge
    global _address_index, _address_completer, _address_pipeline
    global _zip_database, _address_vector_index, _orchestrator

    print("\n" + "="*50)
    print("  ICDA Startup")
    print("="*50 + "\n")

    # Startup
    _cache = RedisCache(cfg.cache_ttl)
    await _cache.connect(cfg.redis_url)

    _embedder = EmbeddingClient(cfg.aws_region, cfg.titan_embed_model, cfg.embed_dimensions)

    _vector_index = VectorIndex(_embedder, cfg.opensearch_index)
    await _vector_index.connect(cfg.opensearch_host, cfg.aws_region)

    _db = CustomerDB(BASE_DIR / "customer_data.json")
    print(f"Customer database: {len(_db.customers)} customers loaded")

    _nova = NovaClient(cfg.aws_region, cfg.nova_model, _db)

    _sessions = SessionManager(_cache)

    _router = Router(_cache, _vector_index, _db, _nova, _sessions)

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

    # Initialize knowledge base
    print("\nInitializing knowledge base...")
    opensearch_client = _vector_index.client if _vector_index.available else None
    _knowledge = KnowledgeManager(_embedder, opensearch_client)
    await _knowledge.ensure_index()

    # Auto-index knowledge documents
    if KNOWLEDGE_DIR.exists() and KNOWLEDGE_DOCUMENTS:
        print("Auto-indexing knowledge documents...")
        result = await auto_index_knowledge_documents(_knowledge)
        if result["indexed"]:
            print(f"  New: {result['indexed']}")
        if result["skipped"]:
            print(f"  Skipped (existing): {result['skipped']}")

    stats = await _knowledge.get_stats()
    print(f"  Knowledge base: {stats.get('unique_documents', 0)} docs, {stats.get('total_chunks', 0)} chunks ({stats.get('backend', 'unknown')})")

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
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
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


@app.post("/api/query")
async def query(req: QueryRequest):
    guards = req.guardrails.model_dump() if req.guardrails else None
    return await _router.route(req.query, req.bypass_cache, guards)


@app.get("/api/health")
async def health():
    """Health check with mode status"""
    nova_ok = _nova.available if _nova else False
    embedder_ok = _embedder.available if _embedder else False
    mode = "FULL" if nova_ok and embedder_ok else "LITE"

    return {
        "status": "healthy",
        "mode": mode,
        "services": {
            "redis": _cache.available if _cache else False,
            "opensearch": _vector_index.available if _vector_index else False,
            "embeddings": embedder_ok,
            "nova_ai": nova_ok,
            "knowledge": _knowledge.available if _knowledge else False,
        },
        "data": {
            "customers": len(_db.customers) if _db else 0,
            "knowledge_backend": _knowledge._memory_store is not None and not _knowledge.use_opensearch 
                                 if _knowledge else "unavailable"
        }
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
    category: str = Form("general")
):
    """Upload a document to the knowledge base."""
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    suffix = Path(file.filename).suffix

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = await _knowledge.index_document(
            content=tmp_path,
            filename=file.filename,
            tags=tag_list,
            category=category
        )
        return result
    finally:
        tmp_path.unlink(missing_ok=True)


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


@app.get("/api/knowledge/search")
async def search_knowledge(
    q: str,
    limit: int = 5,
    tags: Optional[str] = None,
    category: Optional[str] = None
):
    """Search the knowledge base."""
    if not _knowledge or not _knowledge.available:
        return {"success": False, "hits": [], "error": "Not available"}

    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()] if tags else None
    return await _knowledge.search(query=q, limit=limit, tags=tag_list, category=category)


@app.delete("/api/knowledge/document/{doc_id}")
async def delete_knowledge_document(doc_id: str):
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Not available"}
    result = await _knowledge.delete_document(doc_id)
    return {"success": result.get("deleted", 0) > 0, "doc_id": doc_id, **result}


@app.post("/api/knowledge/reindex")
async def reindex_knowledge_documents(force: bool = False):
    """Manually trigger re-indexing of knowledge documents."""
    if not _knowledge or not _knowledge.available:
        return {"success": False, "error": "Knowledge base not available"}

    if force:
        docs = await _knowledge.list_documents(limit=1000)
        for doc in docs:
            await _knowledge.delete_document(doc["doc_id"])

    result = await auto_index_knowledge_documents(_knowledge)
    return {"success": True, **result}


# ==================== Frontend ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    frontend_index = BASE_DIR / "frontend" / "dist" / "index.html"
    if frontend_index.exists():
        return frontend_index.read_text()
    return (BASE_DIR / "templates/index.html").read_text()


frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
