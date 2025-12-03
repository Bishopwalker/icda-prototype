"""
ICDA Prototype - Intelligent Customer Data Access
Run with: uvicorn main:app --reload --port 8000
"""

import os
import json
import hashlib
import re
import time
from typing import Optional
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# Config
# ============================================================================

@dataclass
class Config:
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    nova_model: str = os.getenv("NOVA_MODEL", "us.amazon.nova-micro-v1:0")
    cache_ttl: int = 300

config = Config()


# ============================================================================
# Cache
# ============================================================================

class Cache:
    def __init__(self, ttl: int = 300):
        self._data: dict[str, tuple[str, float]] = {}
        self.ttl = ttl

    def get(self, key: str) -> Optional[str]:
        if key in self._data:
            value, expiry = self._data[key]
            if time.time() < expiry:
                return value
            del self._data[key]
        return None

    def set(self, key: str, value: str):
        self._data[key] = (value, time.time() + self.ttl)

    def clear(self):
        self._data.clear()

    def stats(self) -> dict:
        valid = sum(1 for _, (_, exp) in self._data.items() if time.time() < exp)
        return {"total": len(self._data), "valid": valid}

    @staticmethod
    def make_key(query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

cache = Cache(config.cache_ttl)


# ============================================================================
# CustomerData
# ============================================================================

class CustomerData:
    def __init__(self, data_file: str = "customer_data.json"):
        self.customers = self._load(data_file)
        self.crid_index = {c["crid"]: c for c in self.customers}
        self.state_index: dict[str, list] = {}
        for c in self.customers:
            self.state_index.setdefault(c["state"], []).append(c)

    def _load(self, data_file: str) -> list:
        path = os.path.join(os.path.dirname(__file__), data_file)
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                print(f"Loaded {len(data)} customers")
                return data
        print("No customer_data.json found")
        return [
            {"crid": "CRID-000001", "name": "John Smith", "state": "NV", "city": "Las Vegas", "zip": "89101", "move_count": 3, "last_move": "2024-06-15", "address": "123 Main St"},
            {"crid": "CRID-000002", "name": "Jane Doe", "state": "NV", "city": "Reno", "zip": "89501", "move_count": 2, "last_move": "2024-03-20", "address": "456 Oak Ave"},
        ]

    def lookup(self, crid: str) -> dict:
        crid = crid.upper()
        if crid.startswith("CRID-"):
            num = crid.replace("CRID-", "")
            for fmt in [f"CRID-{num.zfill(6)}", f"CRID-{num.zfill(3)}", crid]:
                if fmt in self.crid_index:
                    return {"success": True, "data": self.crid_index[fmt]}
        return {"success": False, "error": f"CRID {crid} not found"}

    def search(self, state: str = None, city: str = None, min_moves: int = None, limit: int = 10) -> dict:
        results = self.state_index.get(state.upper(), []) if state else self.customers
        if min_moves:
            results = [c for c in results if c["move_count"] >= min_moves]
        if city:
            results = [c for c in results if city.lower() in c["city"].lower()]
        limit = min(limit, 100)
        return {"success": True, "total_matches": len(results), "data": results[:limit]}

    def stats(self) -> dict:
        return {"success": True, "data": {s: len(c) for s, c in self.state_index.items()}}

customer_data = CustomerData()


# ============================================================================
# ToolExecutor
# ============================================================================

class ToolExecutor:
    TOOLS_SPEC = [
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

    def execute(self, tool_name: str, params: dict) -> dict:
        if tool_name == "lookup_crid":
            return self.data.lookup(params.get("crid", ""))
        elif tool_name == "search_customers":
            return self.data.search(
                state=params.get("state"),
                city=params.get("city"),
                min_moves=params.get("min_move_count"),
                limit=params.get("limit", 10)
            )
        elif tool_name == "get_stats":
            return self.data.stats()
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

tool_executor = ToolExecutor(customer_data)


# ============================================================================
# Guardrails
# ============================================================================

class Guardrails:
    BLOCKED_PATTERNS = [
        (r'\b(ssn|social\s*security)\b', "SSN not accessible"),
        (r'\b(credit\s*card|bank\s*account)\b', "Financial info not accessible"),
        (r'\b(password|secret|token)\b', "Credentials not accessible"),
        (r'\b(weather|poem|story|joke)\b', "I only help with customer data queries"),
    ]

    @classmethod
    def check(cls, query: str) -> Optional[str]:
        for pattern, message in cls.BLOCKED_PATTERNS:
            if re.search(pattern, query.lower()):
                return message
        return None


# ============================================================================
# BedrockClient
# ============================================================================

class BedrockClient:
    SYSTEM_PROMPT = """You are ICDA, an AI assistant for customer data queries.
Use the available tools to look up customers, search, or get statistics.
Be concise. Never provide SSN, financial, or health information.
Use tools immediately - don't explain your reasoning first."""

    def __init__(self, region: str, model: str, executor: ToolExecutor):
        self.model = model
        self.executor = executor
        self.available = False
        try:
            self.client = boto3.client("bedrock-runtime", region_name=region)
            self.available = True
        except Exception as e:
            print(f"Bedrock init failed: {e}")

    def query(self, text: str) -> dict:
        if not self.available:
            return {"success": False, "error": "Bedrock not available"}

        try:
            response = self.client.converse(
                modelId=self.model,
                messages=[{"role": "user", "content": [{"text": text}]}],
                system=[{"text": self.SYSTEM_PROMPT}],
                toolConfig={"tools": self.executor.TOOLS_SPEC, "toolChoice": {"auto": {}}},
                inferenceConfig={"maxTokens": 1024, "temperature": 0.1}
            )

            content = response.get("output", {}).get("message", {}).get("content", [])
            tool_use = next((b["toolUse"] for b in content if "toolUse" in b), None)

            if tool_use:
                tool_result = self.executor.execute(tool_use["name"], tool_use["input"])

                follow_up = self.client.converse(
                    modelId=self.model,
                    messages=[
                        {"role": "user", "content": [{"text": text}]},
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": [{"toolResult": {"toolUseId": tool_use["toolUseId"], "content": [{"json": tool_result}]}}]}
                    ],
                    system=[{"text": self.SYSTEM_PROMPT}],
                    toolConfig={"tools": self.executor.TOOLS_SPEC, "toolChoice": {"auto": {}}},
                    inferenceConfig={"maxTokens": 1024, "temperature": 0.1}
                )

                final_content = follow_up.get("output", {}).get("message", {}).get("content", [])
                text_out = next((b["text"] for b in final_content if "text" in b), None)
                if text_out:
                    return {"success": True, "response": text_out, "tool_used": tool_use["name"]}
                return {"success": True, "response": f"Found {tool_result.get('total_matches', len(tool_result.get('data', [])))} results.", "tool_used": tool_use["name"]}

            text_out = next((b["text"] for b in content if "text" in b), None)
            if text_out:
                return {"success": True, "response": text_out}

            return {"success": False, "error": "No response generated"}

        except ClientError as e:
            return {"success": False, "error": f"Bedrock error: {e.response.get('Error', {}).get('Message', str(e))}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

bedrock = BedrockClient(config.aws_region, config.nova_model, tool_executor)


# ============================================================================
# API
# ============================================================================

app = FastAPI(title="ICDA Prototype", version="0.1.0")

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    bypass_cache: bool = False

@app.post("/api/query")
async def process_query(request: QueryRequest):
    start = time.time()
    query = request.query.strip()

    if blocked := Guardrails.check(query):
        return {"success": False, "query": query, "response": blocked, "blocked": True, "latency_ms": int((time.time() - start) * 1000)}

    key = Cache.make_key(query)
    if not request.bypass_cache and (cached := cache.get(key)):
        data = json.loads(cached)
        return {"success": True, "query": query, "response": data["response"], "cached": True, "latency_ms": int((time.time() - start) * 1000)}

    result = bedrock.query(query)

    if result["success"]:
        cache.set(key, json.dumps({"response": result["response"]}))

    return {
        "success": result["success"],
        "query": query,
        "response": result.get("response") or result.get("error"),
        "tool_used": result.get("tool_used"),
        "cached": False,
        "latency_ms": int((time.time() - start) * 1000)
    }

@app.get("/api/health")
async def health():
    return {"status": "healthy", "bedrock": bedrock.available, "customers": len(customer_data.customers)}

@app.get("/api/cache/stats")
async def cache_stats():
    return cache.stats()

@app.delete("/api/cache")
async def clear_cache():
    cache.clear()
    return {"status": "cleared"}

@app.get("/", response_class=HTMLResponse)
async def root():
    return open(os.path.join(os.path.dirname(__file__), "templates", "index.html")).read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
