# ICDA Prototype - Initial Project Specification

## FEATURE:

**ICDA (Intelligent Customer Data Access)** - NLP-powered customer data query system with AWS Bedrock Nova integration, PII guardrails, intelligent caching, and address verification.

### Core Functionality:
- **Natural Language Queries**: Process customer data requests in plain English
- **Query Classification**: Automatic routing (LOOKUP vs COMPLEX vs BLOCKED)
- **PII Guardrails**: Input blocking and output redaction for sensitive data
- **Address Verification**: Multi-stage pipeline with AI-powered completion
- **Caching Layer**: Redis-backed with query-type-specific TTLs

### Architecture:
- **Frontend**: React 18 + TypeScript 5.6 + Material-UI 6.x + Vite
- **Backend**: FastAPI + Python 3.11 + Pydantic
- **Communication**: REST API (JSON)
- **Database**: JSON (prototype) → OpenSearch (production)
- **AI/ML**: AWS Bedrock Nova (us.amazon.nova-micro-v1:0)
- **Caching**: Redis 5.2+
- **Vector Store**: OpenSearch with k-NN plugin

## EXAMPLES:

### 1. Query Classification
- LOOKUP: `"CRID-001"` → Direct database lookup, bypasses AI
- COMPLEX: `"Nevada customers who moved twice"` → Routes to Bedrock Nova
- BLOCKED: `"Show me SSN for CRID-001"` → Guardrail blocks PII request
- **Application**: Optimizes response time by routing simple queries directly

### 2. Tool Calling Pattern
```python
tools = [
    {
        "toolSpec": {
            "name": "search_customers",
            "description": "Search customer database",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "state": {"type": "string"},
                        "move_count": {"type": "integer"}
                    }
                }
            }
        }
    }
]
```
- **Application**: Nova uses structured tools to query data

### 3. Address Verification Pipeline
```
Input: "123 main st las vagas"
→ Normalize: "123 MAIN ST LAS VEGAS"
→ Vector Match: Find similar addresses
→ ZIP Lookup: Validate ZIP codes
→ Nova Complete: AI fills gaps
→ Output: {"street": "123 Main St", "city": "Las Vegas", "state": "NV", "zip": "89101"}
```

### 4. Component Architecture
- `NovaClient`: Bedrock converse API wrapper
- `Router`: Query routing and orchestration
- `Guardrails`: PII detection and blocking
- `RedisCache`: Async caching with TTL
- `VectorIndex`: OpenSearch k-NN operations
- `AddressPipeline`: Multi-stage address processing

## DOCUMENTATION:

### Technical Documentation:
- **FastAPI**: https://fastapi.tiangolo.com/
- **Pydantic**: https://docs.pydantic.dev/
- **Boto3**: https://boto3.amazonaws.com/v1/documentation/api/latest/
- **AWS Bedrock**: https://docs.aws.amazon.com/bedrock/
- **OpenSearch**: https://opensearch.org/docs/

### API References:
- **Bedrock Converse API**: Tool calling with `converse()` method
- **OpenSearch k-NN**: Vector similarity search

### Best Practices:
- Always validate inputs with Pydantic models
- Use async/await for I/O-bound operations
- Implement proper error handling with HTTPException
- Log all queries for audit trail

## ARCHITECTURE & DESIGN PATTERNS

### System Architecture
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   FastAPI   │────▶│   Bedrock   │
│  (React)    │     │  (Router)   │     │   (Nova)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
    ┌───────────┐  ┌───────────┐  ┌───────────┐
    │   Redis   │  │ OpenSearch│  │  Customer │
    │  (Cache)  │  │ (Vectors) │  │    DB     │
    └───────────┘  └───────────┘  └───────────┘
```

### Key Design Decisions:
- **Classifier First**: Route queries before any processing
- **Cache Before AI**: Check cache before expensive Bedrock calls
- **Guardrails at Boundaries**: Block PII at input AND output
- **Async Everything**: Non-blocking I/O throughout

## OTHER CONSIDERATIONS:

### Critical Implementation Details:

1. **AWS Credentials**: Must have `AWS_PROFILE=NNGC` or equivalent configured
2. **Redis Connection**: Required for caching, falls back to in-memory if unavailable
3. **OpenSearch**: Vector index requires k-NN plugin enabled
4. **Bedrock Access**: Ensure model access granted in AWS console
5. **CORS**: Frontend on different port requires CORS middleware

### Environment Variables:
```env
AWS_PROFILE=NNGC
AWS_REGION=us-east-1
REDIS_URL=redis://localhost:6379
OPENSEARCH_HOST=localhost
OPENSEARCH_INDEX=customer-vectors
DEMO_MODE=false
```

### Performance Optimizations:

1. **Query Classification**: Pattern matching < 1ms
2. **Cache Hits**: Redis lookup < 5ms
3. **Vector Search**: OpenSearch k-NN < 50ms
4. **Bedrock Calls**: Nova Micro < 2000ms

### Common AI Assistant Mistakes to Avoid:

1. **Don't hardcode AWS credentials**: Always use profiles or environment
2. **Don't skip guardrails**: PII protection is mandatory
3. **Don't ignore cache**: Always check cache before AI calls
4. **Don't block the event loop**: Use async for all I/O
5. **Don't expose internal errors**: Wrap in HTTPException
6. **Don't forget session management**: Track user context
7. **NEVER WRITE** **Completed by:** Claude or Anthropic or anything that isn't the actual author
8. **NEVER FORGET**: Check project for any mentions of authored by Claude or Anthropic AI

### Development Gotchas:

1. **Port Conflicts**: Kill existing processes on 8000/5173 before starting
2. **Redis Not Running**: Start Redis or use `DEMO_MODE=true`
3. **OpenSearch Connection**: Ensure OpenSearch is running locally
4. **Model Access**: Request Bedrock model access in AWS console
5. **Frontend Proxy**: Vite proxies `/api` to backend automatically

## IMPLEMENTATION PATTERNS

### Query Processing Pattern
```python
async def process_query(query: str, session_id: str) -> QueryResponse:
    # 1. Classify
    query_type = classifier.classify(query)

    # 2. Check guardrails
    if guardrails.is_blocked(query):
        raise HTTPException(400, "Query blocked by guardrails")

    # 3. Check cache
    cached = await cache.get(query)
    if cached:
        return cached

    # 4. Process based on type
    if query_type == "LOOKUP":
        result = db.lookup(query)
    else:
        result = await nova.converse(query, session_id)

    # 5. Apply output guardrails
    result = guardrails.redact_output(result)

    # 6. Cache and return
    await cache.set(query, result, ttl=get_ttl(query_type))
    return result
```

### Address Verification Pattern
```python
async def verify_address(address: AddressInput) -> VerifiedAddress:
    # Stage 1: Normalize
    normalized = normalizer.normalize(address)

    # Stage 2: Exact match
    exact = address_index.exact_match(normalized)
    if exact:
        return exact

    # Stage 3: Vector search
    candidates = await vector_index.search(normalized, k=5)

    # Stage 4: ZIP validation
    validated = zip_db.validate(candidates)

    # Stage 5: AI completion (if needed)
    if not validated.complete:
        validated = await nova_completer.complete(validated)

    return validated
```

### Error Handling Pattern
```python
from fastapi import HTTPException

async def safe_operation():
    try:
        result = await risky_operation()
        return result
    except NovaTimeoutError:
        raise HTTPException(504, "AI service timeout")
    except PIIDetectedError as e:
        raise HTTPException(400, f"PII blocked: {e.type}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(500, "Internal server error")
```

### Browser Support and Compatibility
- **React**: Modern browsers (ES2020+)
- **Material-UI**: Chrome, Firefox, Safari, Edge (latest 2 versions)
- **Vite**: HMR requires WebSocket support
