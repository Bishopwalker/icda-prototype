"""
ICDA Prototype - Intelligent Customer Data Access
Run with: uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Must be before importing config

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from icda.config import Config
from icda.cache import RedisCache
from icda.embeddings import EmbeddingClient
from icda.vector_index import VectorIndex
from icda.database import CustomerDB
from icda.nova import NovaClient
from icda.router import Router
from icda.session import SessionManager

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

# Globals
_cache: RedisCache = None
_embedder: EmbeddingClient = None
_vector_index: VectorIndex = None
_db: CustomerDB = None
_nova: NovaClient = None
_sessions: SessionManager = None
_router: Router = None

# Address verification globals
_address_index: AddressIndex = None
_address_completer: NovaAddressCompleter = None
_address_pipeline: AddressPipeline = None
_zip_database: ZipDatabase = None
_address_vector_index: AddressVectorIndex = None
_orchestrator: AddressAgentOrchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache, _embedder, _vector_index, _db, _nova, _sessions, _router
    global _address_index, _address_completer, _address_pipeline
    global _zip_database, _address_vector_index, _orchestrator

    # Startup
    _cache = RedisCache(cfg.cache_ttl)
    await _cache.connect(cfg.redis_url)

    _embedder = EmbeddingClient(cfg.aws_region, cfg.titan_embed_model, cfg.embed_dimensions)

    _vector_index = VectorIndex(_embedder, cfg.opensearch_index)
    await _vector_index.connect(cfg.opensearch_host, cfg.aws_region)

    _db = CustomerDB(BASE_DIR / "customer_data.json")

    _nova = NovaClient(cfg.aws_region, cfg.nova_model, _db)

    _sessions = SessionManager(_cache)

    _router = Router(_cache, _vector_index, _db, _nova, _sessions)

    # Initialize address verification components
    print("Initializing address verification pipeline...")

    # Build address index from customer data
    _address_index = AddressIndex()
    _address_index.build_from_customers(_db.customers)
    print(f"  Address index: {_address_index.total_addresses} addresses")

    # Build ZIP database
    _zip_database = ZipDatabase()
    _zip_database.build_from_customers(_db.customers)
    print(f"  ZIP database: {_zip_database.total_zips} ZIPs")

    # Initialize Nova address completer
    _address_completer = NovaAddressCompleter(
        cfg.aws_region,
        cfg.nova_model,
        _address_index,
    )

    # Create pipeline (legacy 6-stage)
    _address_pipeline = AddressPipeline(
        _address_index,
        _address_completer,
    )

    # Initialize address vector index for semantic search (optional)
    _address_vector_index = None
    if cfg.opensearch_host and _embedder.available:
        _address_vector_index = AddressVectorIndex(_embedder)
        connected = await _address_vector_index.connect(
            cfg.opensearch_host,
            cfg.aws_region,
        )
        if connected:
            print("  Address vector index: connected")
        else:
            print("  Address vector index: not available (semantic search disabled)")
            _address_vector_index = None

    # Initialize 5-agent orchestrator
    _orchestrator = AddressAgentOrchestrator(
        address_index=_address_index,
        zip_database=_zip_database,
        vector_index=_address_vector_index,
    )
    print("  5-agent orchestrator: initialized")

    # Configure address router with both legacy pipeline and new orchestrator
    configure_router(_address_pipeline, _orchestrator)
    print("Address verification ready!")

    yield

    # Shutdown
    await _cache.close()
    await _vector_index.close()
    if _address_vector_index:
        await _address_vector_index.close()


app = FastAPI(title="ICDA", version="0.6.0", lifespan=lifespan)

# Include address verification router
app.include_router(address_router)

# CORS - allow all origins for development
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
    return {
        "status": "healthy",
        "redis": _cache.available if _cache else False,
        "opensearch": _vector_index.available if _vector_index else False,
        "embedder": _embedder.available if _embedder else False,
        "nova": _nova.available if _nova else False,
        "customers": len(_db.customers) if _db else 0
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
    """
    Autocomplete endpoint for address, name, or city fields.

    Examples:
      /api/autocomplete/address?q=123 Main
      /api/autocomplete/name?q=John
      /api/autocomplete/city?q=Las
      /api/autocomplete/address?q=main&fuzzy=true  (slower, handles typos)
    """
    if fuzzy:
        return _db.autocomplete_fuzzy(field, q, limit)
    return _db.autocomplete(field, q, limit)


@app.get("/api/search/semantic")
async def semantic_search(q: str, limit: int = 10, state: str = None, city: str = None,
                          min_moves: int = None, status: str = None, customer_type: str = None):
    """
    Semantic search for customers using vector similarity (requires OpenSearch).

    Examples:
      /api/search/semantic?q=customers in Las Vegas
      /api/search/semantic?q=high movers&state=CA&min_moves=3
      /api/search/semantic?q=business customers&customer_type=BUSINESS

    Filters: state, city, min_moves, status, customer_type
    """
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
    """
    Hybrid search combining full-text and semantic search.
    Better for address autocomplete with typo tolerance.

    Examples:
      /api/search/hybrid?q=123 mian street  (handles typos)
      /api/search/hybrid?q=john smth las vegas
    """
    filters = {}
    if state:
        filters["state"] = state
    if min_moves:
        filters["min_moves"] = min_moves

    return await _vector_index.search_customers_hybrid(q, limit, filters if filters else None)


@app.get("/api/index/status")
async def index_status():
    """Get status of OpenSearch customer index"""
    return {
        "opensearch_available": _vector_index.available if _vector_index else False,
        "customer_index": _vector_index.customer_index if _vector_index else None,
        "indexed_customers": await _vector_index.customer_count() if _vector_index else 0
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    return (BASE_DIR / "templates/index.html").read_text()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
