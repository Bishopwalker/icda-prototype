"""
ICDA Prototype - Intelligent Customer Data Access
Run with: uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from icda.config import cfg
from icda.cache import RedisCache
from icda.embeddings import EmbeddingClient
from icda.vector_index import VectorIndex
from icda.database import CustomerDB
from icda.nova import NovaClient
from icda.router import Router

load_dotenv()

BASE_DIR = Path(__file__).parent

# Globals
_cache: RedisCache = None
_embedder: EmbeddingClient = None
_vector_index: VectorIndex = None
_db: CustomerDB = None
_nova: NovaClient = None
_router: Router = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache, _embedder, _vector_index, _db, _nova, _router

    # Startup
    _cache = RedisCache(cfg.cache_ttl)
    await _cache.connect(cfg.redis_url)

    _embedder = EmbeddingClient(cfg.aws_region, cfg.titan_embed_model, cfg.embed_dimensions)

    _vector_index = VectorIndex(_embedder, cfg.opensearch_index)
    await _vector_index.connect(cfg.opensearch_host, cfg.aws_region)

    _db = CustomerDB(BASE_DIR / "customer_data.json")

    _nova = NovaClient(cfg.aws_region, cfg.nova_model, _db)

    _router = Router(_cache, _vector_index, _db, _nova)

    yield

    # Shutdown
    await _cache.close()
    await _vector_index.close()


app = FastAPI(title="ICDA", version="0.5.0", lifespan=lifespan)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    bypass_cache: bool = False


@app.post("/api/query")
async def query(req: QueryRequest):
    return await _router.route(req.query, req.bypass_cache)


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


@app.get("/", response_class=HTMLResponse)
async def root():
    return (BASE_DIR / "templates/index.html").read_text()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
