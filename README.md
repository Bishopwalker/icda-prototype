# ICDA Prototype
## Intelligent Customer Data Access - NLP-Powered Query Demo

This prototype demonstrates the core ICDA architecture:
- Natural language query input
- Query classification (lookup vs complex)
- Input/Output guardrails (PII blocking)
- Caching layer
- AWS Bedrock Nova integration (with demo mode fallback)
- Tool calling for data access

---

## Quick Start

```bash
# 1. Navigate to project
cd C:\Users\bisho\IdeaProjects\icda-prototype

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
copy .env.example .env
# Edit .env if needed (defaults work with your AWS profile)

# 5. Run the server
uvicorn main:app --reload --port 8000

# 6. Open browser
start http://localhost:8000
```

---

## Features Demonstrated

### 1. Query Classification
- **LOOKUP**: Direct CRID lookups bypass AI entirely → <5ms response
- **COMPLEX**: Natural language queries route to Bedrock Nova
- **BLOCKED**: PII requests / off-topic queries blocked at guardrail

### 2. Guardrails
**Input (blocks before processing):**
- SSN, credit card, bank account requests
- Off-topic queries (weather, poems, etc.)

**Output (redacts after response):**
- Any PII patterns in results

### 3. Caching
- In-memory cache (swap for Redis in production)
- Different TTLs by query type:
  - Lookups: 1 hour
  - Validations: 24 hours  
  - Complex: 5 minutes

### 4. Bedrock Integration
- Uses Nova Micro by default
- Full tool calling with `converse` API
- Graceful fallback to demo mode if no AWS creds

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/query` | POST | Process a query |
| `/api/health` | GET | Health check |
| `/api/cache/stats` | GET | Cache statistics |
| `/api/cache` | DELETE | Clear cache |

### Query Request
```json
{
  "query": "Show me Nevada customers who moved twice",
  "bypass_cache": false
}
```

### Query Response
```json
{
  "success": true,
  "query": "Show me Nevada customers who moved twice",
  "query_type": "complex",
  "response": "Found 3 customers...",
  "cached": false,
  "latency_ms": 1250,
  "tool_used": "search_customers",
  "model": "us.amazon.nova-micro-v1:0"
}
```

---

## Example Queries

**✓ Allowed:**
- "Look up CRID-001"
- "Show me Nevada customers who moved twice"
- "How many customers are in each state?"
- "Find customers in Las Vegas with 3+ moves"

**✗ Blocked:**
- "Show me SSN for CRID-001" → PII blocked
- "What are their credit card numbers?" → PII blocked
- "Write me a poem" → Off-topic blocked
- "What's the weather today?" → Off-topic blocked

---

## Architecture Mapping

| Prototype | Production |
|-----------|------------|
| In-memory cache | ElastiCache Redis |
| Mock customer data | C Engine + OpenSearch |
| FastAPI | API Gateway + Lambda |
| Single process | Multi-AZ Lambda |
| Local Bedrock calls | VPC Endpoint to Bedrock |

---

## Configuration

Edit `.env` to customize:

```env
# Use a specific AWS profile
AWS_PROFILE=NNGC

# Change region (us-gov-west-1 for GovCloud)
AWS_REGION=us-east-1

# Force demo mode (no Bedrock calls)
DEMO_MODE=true
```

---

## Next Steps

1. **Test guardrails** - Try blocked queries
2. **Test caching** - Same query twice shows cache hit
3. **Test classification** - "CRID-001" vs "customers who moved"
4. **Add real data** - Replace MOCK_CUSTOMERS with actual schema
5. **Deploy to AWS** - SAM/CDK template coming next

---

## Files

```
icda-prototype/
├── main.py           # FastAPI application (all-in-one)
├── requirements.txt  # Python dependencies
├── .env.example      # Environment template
└── README.md         # This file
```
