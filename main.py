"""
ICDA Prototype - Intelligent Customer Data Access
Run with: uvicorn main:app --reload --port 8000
"""

import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import cache
from hashlib import sha256
from os import getenv
from pathlib import Path
from time import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import redis.asyncio as redis
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection, AWSV4SignerAsyncAuth

load_dotenv()

BASE_DIR = Path(__file__).parent


# ============================================================================
# Config
# ============================================================================

@dataclass(slots=True, frozen=True)
class Config:
    aws_region: str = field(default_factory=lambda: getenv("AWS_REGION", "us-east-1"))
    nova_model: str = field(default_factory=lambda: getenv("NOVA_MODEL", "us.amazon.nova-micro-v1:0"))
    cache_ttl: int = 300
    redis_url: str = field(default_factory=lambda: getenv("REDIS_URL", "redis://localhost:6379"))
    opensearch_host: str = field(default_factory=lambda: getenv("OPENSEARCH_HOST", ""))
    opensearch_index: str = field(default_factory=lambda: getenv("OPENSEARCH_INDEX", "customers"))

CFG = Config()


# ============================================================================
# Redis Cache
# ============================================================================

class RedisCache:
    __slots__ = ("client", "ttl", "available", "_fallback")

    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self.client: redis.Redis | None = None
        self.available = False
        self._fallback: dict[str, tuple[str, float]] = {}

    async def connect(self, url: str) -> None:
        try:
            self.client = redis.from_url(url, decode_responses=True)
            await self.client.ping()
            self.available = True
            print(f"Redis connected: {url}")
        except Exception as e:
            print(f"Redis unavailable, using in-memory fallback: {e}")
            self.available = False

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()

    async def get(self, key: str) -> str | None:
        if self.available:
            return await self.client.get(key)
        if (entry := self._fallback.get(key)) and time() < entry[1]:
            return entry[0]
        self._fallback.pop(key, None)
        return None

    async def set(self, key: str, value: str) -> None:
        if self.available:
            await self.client.setex(key, self.ttl, value)
        else:
            self._fallback[key] = (value, time() + self.ttl)

    async def clear(self) -> None:
        if self.available:
            await self.client.flushdb()
        else:
            self._fallback.clear()

    async def stats(self) -> dict[str, int]:
        if self.available:
            info = await self.client.info("keyspace")
            db_info = info.get("db0", {})
            return {"total": db_info.get("keys", 0), "backend": "redis"}
        now = time()
        valid = sum(1 for _, exp in self._fallback.values() if now < exp)
        return {"total": len(self._fallback), "valid": valid, "backend": "memory"}

    @staticmethod
    @cache
    def make_key(query: str) -> str:
        return f"icda:{sha256(query.casefold().strip().encode()).hexdigest()[:16]}"

_cache = RedisCache(CFG.cache_ttl)


# ============================================================================
# OpenSearch Client
# ============================================================================

class OpenSearchClient:
    __slots__ = ("client", "index", "available")

    def __init__(self):
        self.client: AsyncOpenSearch | None = None
        self.index = CFG.opensearch_index
        self.available = False

    async def connect(self, host: str, region: str) -> None:
        if not host:
            print("OpenSearch host not configured")
            return
        try:
            credentials = boto3.Session().get_credentials()
            service = "aoss" if "aoss.amazonaws.com" in host else "es"
            self.client = AsyncOpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=AWSV4SignerAsyncAuth(credentials, region, service),
                use_ssl=True,
                verify_certs=True,
                connection_class=AsyncHttpConnection
            )
            await self.client.info()
            self.available = True
            print(f"OpenSearch connected: {host}")
        except Exception as e:
            print(f"OpenSearch unavailable: {e}")
            self.available = False

    async def close(self) -> None:
        if self.client:
            await self.client.close()

    async def search(self, query: dict, size: int = 10) -> list[dict]:
        if not self.available:
            return []
        resp = await self.client.search(index=self.index, body=query, size=size)
        return [hit["_source"] for hit in resp["hits"]["hits"]]

    async def lookup(self, crid: str) -> dict | None:
        if not self.available:
            return None
        try:
            resp = await self.client.get(index=self.index, id=crid)
            return resp["_source"]
        except Exception:
            return None

    async def index_doc(self, doc_id: str, doc: dict) -> bool:
        if not self.available:
            return False
        await self.client.index(index=self.index, id=doc_id, body=doc)
        return True

_opensearch = OpenSearchClient()


# ============================================================================
# CustomerData (with OpenSearch fallback to local)
# ============================================================================

class CustomerData:
    __slots__ = ("customers", "by_crid", "by_state", "os_client")

    def __init__(self, os_client: OpenSearchClient, data_file: str = "customer_data.json"):
        self.os_client = os_client
        self.customers = self._load(data_file)
        self.by_crid = {c["crid"]: c for c in self.customers}
        self.by_state: dict[str, list] = {}
        for c in self.customers:
            self.by_state.setdefault(c["state"], []).append(c)

    def _load(self, data_file: str) -> list[dict]:
        path = BASE_DIR / data_file
        if path.exists():
            data = json.loads(path.read_text())
            print(f"Loaded {len(data)} customers from file")
            return data
        print(f"{data_file} not found")
        return [
            {"crid": "CRID-000001", "name": "John Smith", "state": "NV", "city": "Las Vegas", "zip": "89101", "move_count": 3, "last_move": "2024-06-15", "address": "123 Main St"},
            {"crid": "CRID-000002", "name": "Jane Doe", "state": "NV", "city": "Reno", "zip": "89501", "move_count": 2, "last_move": "2024-03-20", "address": "456 Oak Ave"},
        ]

    async def lookup(self, crid: str) -> dict:
        crid = crid.upper()
        # Try OpenSearch first
        if self.os_client.available:
            if data := await self.os_client.lookup(crid):
                return {"success": True, "data": data, "source": "opensearch"}
        # Fallback to local
        if crid.startswith("CRID-"):
            num = crid.removeprefix("CRID-")
            for fmt in (f"CRID-{num.zfill(6)}", f"CRID-{num.zfill(3)}", crid):
                if data := self.by_crid.get(fmt):
                    return {"success": True, "data": data, "source": "local"}
        return {"success": False, "error": f"CRID {crid} not found"}

    async def search(self, *, state: str | None = None, city: str | None = None, min_moves: int | None = None, limit: int = 10) -> dict:
        limit = min(limit, 100)
        # Try OpenSearch first
        if self.os_client.available:
            must = []
            if state:
                must.append({"term": {"state": state.upper()}})
            if city:
                must.append({"match": {"city": city}})
            if min_moves:
                must.append({"range": {"move_count": {"gte": min_moves}}})
            query = {"query": {"bool": {"must": must}} if must else {"match_all": {}}}
            results = await self.os_client.search(query, size=limit)
            return {"success": True, "total_matches": len(results), "data": results, "source": "opensearch"}
        # Fallback to local
        results = self.by_state.get(state.upper(), []) if state else self.customers
        if min_moves:
            results = [c for c in results if c["move_count"] >= min_moves]
        if city:
            city_lower = city.casefold()
            results = [c for c in results if city_lower in c["city"].casefold()]
        return {"success": True, "total_matches": len(results), "data": results[:limit], "source": "local"}

    def stats(self) -> dict:
        return {"success": True, "data": {s: len(c) for s, c in self.by_state.items()}}


# ============================================================================
# ToolExecutor
# ============================================================================

class ToolExecutor:
    __slots__ = ("data",)
    SPEC = [
        {"toolSpec": {"name": "lookup_crid", "description": "Look up customer by CRID",
            "inputSchema": {"json": {"type": "object", "properties": {"crid": {"type": "string"}}, "required": ["crid"]}}}},
        {"toolSpec": {"name": "search_customers", "description": "Search customers by state, city, or move count",
            "inputSchema": {"json": {"type": "object", "properties": {
                "state": {"type": "string"}, "city": {"type": "string"},
                "min_move_count": {"type": "integer"}, "limit": {"type": "integer"}}}}}},
        {"toolSpec": {"name": "get_stats", "description": "Get customer statistics",
            "inputSchema": {"json": {"type": "object", "properties": {}}}}}
    ]

    def __init__(self, data: CustomerData):
        self.data = data

    async def execute(self, name: str, params: dict) -> dict:
        match name:
            case "lookup_crid":
                return await self.data.lookup(params.get("crid", ""))
            case "search_customers":
                return await self.data.search(
                    state=params.get("state"),
                    city=params.get("city"),
                    min_moves=params.get("min_move_count"),
                    limit=params.get("limit", 10)
                )
            case "get_stats":
                return self.data.stats()
            case _:
                return {"success": False, "error": f"Unknown tool: {name}"}


# ============================================================================
# Guardrails
# ============================================================================

class Guardrails:
    __slots__ = ()
    _PATTERNS = tuple(
        (re.compile(p, re.I), msg) for p, msg in [
            (r"\b(ssn|social\s*security)\b", "SSN not accessible"),
            (r"\b(credit\s*card|bank\s*account)\b", "Financial info not accessible"),
            (r"\b(password|secret|token)\b", "Credentials not accessible"),
            (r"\b(weather|poem|story|joke)\b", "I only help with customer data queries"),
        ]
    )

    @classmethod
    def check(cls, query: str) -> str | None:
        for pattern, msg in cls._PATTERNS:
            if pattern.search(query):
                return msg
        return None


# ============================================================================
# BedrockClient
# ============================================================================

class BedrockClient:
    __slots__ = ("model", "executor", "client", "available")
    _PROMPT = "You are ICDA, an AI assistant for customer data queries. Use tools to look up customers, search, or get statistics. Be concise. Never provide SSN, financial, or health info. Use tools immediately."

    def __init__(self, region: str, model: str, executor: ToolExecutor):
        self.model = model
        self.executor = executor
        try:
            self.client = boto3.client("bedrock-runtime", region_name=region)
            self.available = True
        except Exception as e:
            print(f"Bedrock init failed: {e}")
            self.client = None
            self.available = False

    def _converse(self, messages: list) -> dict:
        return self.client.converse(
            modelId=self.model,
            messages=messages,
            system=[{"text": self._PROMPT}],
            toolConfig={"tools": self.executor.SPEC, "toolChoice": {"auto": {}}},
            inferenceConfig={"maxTokens": 1024, "temperature": 0.1}
        )

    def _extract_text(self, content: list) -> str | None:
        return next((b["text"] for b in content if "text" in b), None)

    async def query(self, text: str) -> dict:
        if not self.available:
            return {"success": False, "error": "Bedrock not available"}

        try:
            resp = self._converse([{"role": "user", "content": [{"text": text}]}])
            content = resp["output"]["message"]["content"]

            if tool := next((b["toolUse"] for b in content if "toolUse" in b), None):
                result = await self.executor.execute(tool["name"], tool["input"])
                follow = self._converse([
                    {"role": "user", "content": [{"text": text}]},
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": [{"toolResult": {"toolUseId": tool["toolUseId"], "content": [{"json": result}]}}]}
                ])
                if out := self._extract_text(follow["output"]["message"]["content"]):
                    return {"success": True, "response": out, "tool_used": tool["name"]}
                return {"success": True, "response": f"Found {result.get('total_matches', len(result.get('data', [])))} results.", "tool_used": tool["name"]}

            if out := self._extract_text(content):
                return {"success": True, "response": out}

            return {"success": False, "error": "No response"}

        except ClientError as e:
            return {"success": False, "error": f"Bedrock: {e.response['Error']['Message']}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================================
# App Lifecycle & API
# ============================================================================

_data: CustomerData = None
_tools: ToolExecutor = None
_bedrock: BedrockClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _data, _tools, _bedrock
    # Startup
    await _cache.connect(CFG.redis_url)
    await _opensearch.connect(CFG.opensearch_host, CFG.aws_region)
    _data = CustomerData(_opensearch)
    _tools = ToolExecutor(_data)
    _bedrock = BedrockClient(CFG.aws_region, CFG.nova_model, _tools)
    yield
    # Shutdown
    await _cache.close()
    await _opensearch.close()

app = FastAPI(title="ICDA", version="0.3.0", lifespan=lifespan)

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    bypass_cache: bool = False

@app.post("/api/query")
async def query(req: QueryRequest):
    start = time()
    q = req.query.strip()

    if blocked := Guardrails.check(q):
        return {"success": False, "query": q, "response": blocked, "blocked": True, "latency_ms": int((time() - start) * 1000)}

    key = RedisCache.make_key(q)
    if not req.bypass_cache and (hit := await _cache.get(key)):
        return {"success": True, "query": q, "response": json.loads(hit)["response"], "cached": True, "latency_ms": int((time() - start) * 1000)}

    result = await _bedrock.query(q)
    if result["success"]:
        await _cache.set(key, json.dumps({"response": result["response"]}))

    return {"success": result["success"], "query": q, "response": result.get("response") or result.get("error"),
            "tool_used": result.get("tool_used"), "cached": False, "latency_ms": int((time() - start) * 1000)}

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "bedrock": _bedrock.available if _bedrock else False,
        "redis": _cache.available,
        "opensearch": _opensearch.available,
        "customers": len(_data.customers) if _data else 0
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
