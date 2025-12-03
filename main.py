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

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Configuration
# ============================================================================

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
NOVA_MODEL = os.getenv("NOVA_MODEL", "us.amazon.nova-micro-v1:0")

try:
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    BEDROCK_AVAILABLE = True
except Exception as e:
    print(f"Bedrock init failed: {e}")
    BEDROCK_AVAILABLE = False

# ============================================================================
# Cache
# ============================================================================

cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 300  # 5 minutes

def get_cache(key: str) -> Optional[str]:
    if key in cache:
        value, expiry = cache[key]
        if time.time() < expiry:
            return value
        del cache[key]
    return None

def set_cache(key: str, value: str):
    cache[key] = (value, time.time() + CACHE_TTL)

def cache_key(query: str) -> str:
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

# ============================================================================
# Customer Data
# ============================================================================

def load_customer_data():
    data_file = os.path.join(os.path.dirname(__file__), "customer_data.json")
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            data = json.load(f)
            print(f"Loaded {len(data)} customers")
            return data
    print("No customer_data.json found")
    return [
        {"crid": "CRID-000001", "name": "John Smith", "state": "NV", "city": "Las Vegas", "zip": "89101", "move_count": 3, "last_move": "2024-06-15", "address": "123 Main St"},
        {"crid": "CRID-000002", "name": "Jane Doe", "state": "NV", "city": "Reno", "zip": "89501", "move_count": 2, "last_move": "2024-03-20", "address": "456 Oak Ave"},
    ]

CUSTOMER_DATA = load_customer_data()
CRID_INDEX = {c["crid"]: c for c in CUSTOMER_DATA}
STATE_INDEX = {}
for c in CUSTOMER_DATA:
    STATE_INDEX.setdefault(c["state"], []).append(c)

# ============================================================================
# Tools
# ============================================================================

def execute_tool(tool_name: str, params: dict) -> dict:
    if tool_name == "lookup_crid":
        crid = params.get("crid", "").upper()
        if crid.startswith("CRID-"):
            num = crid.replace("CRID-", "")
            for fmt in [f"CRID-{num.zfill(6)}", f"CRID-{num.zfill(3)}", crid]:
                if fmt in CRID_INDEX:
                    return {"success": True, "data": CRID_INDEX[fmt]}
        return {"success": False, "error": f"CRID {crid} not found"}

    elif tool_name == "search_customers":
        results = STATE_INDEX.get(params.get("state", "").upper(), []) if params.get("state") else CUSTOMER_DATA
        if min_moves := params.get("min_move_count"):
            results = [c for c in results if c["move_count"] >= int(min_moves)]
        if city := params.get("city"):
            results = [c for c in results if city.lower() in c["city"].lower()]
        limit = min(int(params.get("limit", 10)), 100)
        return {"success": True, "total_matches": len(results), "data": results[:limit]}

    elif tool_name == "get_stats":
        stats = {state: len(customers) for state, customers in STATE_INDEX.items()}
        return {"success": True, "data": stats}

    return {"success": False, "error": f"Unknown tool: {tool_name}"}

# ============================================================================
# Guardrails
# ============================================================================

BLOCKED_PATTERNS = [
    (r'\b(ssn|social\s*security)\b', "SSN not accessible"),
    (r'\b(credit\s*card|bank\s*account)\b', "Financial info not accessible"),
    (r'\b(password|secret|token)\b', "Credentials not accessible"),
    (r'\b(weather|poem|story|joke)\b', "I only help with customer data queries"),
]

def check_guardrail(query: str) -> Optional[str]:
    for pattern, message in BLOCKED_PATTERNS:
        if re.search(pattern, query.lower()):
            return message
    return None

# ============================================================================
# Bedrock
# ============================================================================

SYSTEM_PROMPT = """You are ICDA, an AI assistant for customer data queries.
Use the available tools to look up customers, search, or get statistics.
Be concise. Never provide SSN, financial, or health information.
Use tools immediately - don't explain your reasoning first."""

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

def call_bedrock(query: str) -> dict:
    if not BEDROCK_AVAILABLE:
        return {"success": False, "error": "Bedrock not available"}

    try:
        response = bedrock.converse(
            modelId=NOVA_MODEL,
            messages=[{"role": "user", "content": [{"text": query}]}],
            system=[{"text": SYSTEM_PROMPT}],
            toolConfig={"tools": TOOLS_SPEC, "toolChoice": {"auto": {}}},
            inferenceConfig={"maxTokens": 1024, "temperature": 0.1}
        )

        content = response.get("output", {}).get("message", {}).get("content", [])

        # Find tool use
        tool_use = next((b["toolUse"] for b in content if "toolUse" in b), None)

        if tool_use:
            tool_result = execute_tool(tool_use["name"], tool_use["input"])

            # Get final response
            follow_up = bedrock.converse(
                modelId=NOVA_MODEL,
                messages=[
                    {"role": "user", "content": [{"text": query}]},
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": [{"toolResult": {"toolUseId": tool_use["toolUseId"], "content": [{"json": tool_result}]}}]}
                ],
                system=[{"text": SYSTEM_PROMPT}],
                toolConfig={"tools": TOOLS_SPEC, "toolChoice": {"auto": {}}},
                inferenceConfig={"maxTokens": 1024, "temperature": 0.1}
            )

            final_content = follow_up.get("output", {}).get("message", {}).get("content", [])
            text = next((b["text"] for b in final_content if "text" in b), None)
            if text:
                return {"success": True, "response": text, "tool_used": tool_use["name"]}
            return {"success": True, "response": f"Found {tool_result.get('total_matches', len(tool_result.get('data', [])))} results.", "tool_used": tool_use["name"]}

        # No tool use - return text
        text = next((b["text"] for b in content if "text" in b), None)
        if text:
            return {"success": True, "response": text}

        return {"success": False, "error": "No response generated"}

    except ClientError as e:
        return {"success": False, "error": f"Bedrock error: {e.response.get('Error', {}).get('Message', str(e))}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================================
# FastAPI
# ============================================================================

app = FastAPI(title="ICDA Prototype", version="0.1.0")

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    bypass_cache: bool = False

@app.post("/api/query")
async def process_query(request: QueryRequest):
    start = time.time()
    query = request.query.strip()

    # Check guardrails
    if blocked := check_guardrail(query):
        return {"success": False, "query": query, "response": blocked, "blocked": True, "latency_ms": int((time.time() - start) * 1000)}

    # Check cache
    key = cache_key(query)
    if not request.bypass_cache and (cached := get_cache(key)):
        data = json.loads(cached)
        return {"success": True, "query": query, "response": data["response"], "cached": True, "latency_ms": int((time.time() - start) * 1000)}

    # Call Bedrock
    result = call_bedrock(query)

    if result["success"]:
        set_cache(key, json.dumps({"response": result["response"]}))

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
    return {"status": "healthy", "bedrock": BEDROCK_AVAILABLE, "customers": len(CUSTOMER_DATA)}

@app.get("/api/cache/stats")
async def cache_stats():
    valid = sum(1 for _, (_, exp) in cache.items() if time.time() < exp)
    return {"total": len(cache), "valid": valid}

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
