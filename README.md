# ICDA - Intelligent Customer Data Access

AI-powered customer data assistant with semantic search, address verification, and RAG knowledge base.

## Quick Start (No Docker Required!)

```bash
# Clone and run
git clone <repo>
cd icda-prototype

# Windows
run.bat

# Mac/Linux
./run.sh
```

That's it! The app runs at http://localhost:8000

## Two Modes

### LITE MODE (Default - No AWS Required)
- ✅ Customer database search & autocomplete
- ✅ Address verification pipeline
- ✅ Knowledge base (keyword search)
- ✅ Full API functionality
- ❌ AI-powered queries (needs AWS)
- ❌ Semantic vector search (needs AWS)

### FULL MODE (With AWS Credentials)
- ✅ Everything in LITE MODE
- ✅ Bedrock Nova AI assistant
- ✅ Titan semantic embeddings
- ✅ Vector similarity search

To enable FULL MODE, add AWS credentials to `.env`:
```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
```

<<<<<<< HEAD
## Optional: Redis & OpenSearch

For production deployments, you can add:
- **Redis**: Faster caching (app uses in-memory cache by default)
- **OpenSearch**: Vector search (app uses keyword search by default)

```bash
# Start with Docker services
docker-compose up -d redis opensearch
```

Then update `.env`:
```env
=======
## Docker Deployment

### Option 1: Core Services Only (Redis + OpenSearch)
```bash
docker-compose up -d redis opensearch
```
Then run the app locally with `run.bat` or `run.sh`.

### Option 2: Full Stack (Everything in Docker)
```bash
docker-compose up -d
```
This starts: ICDA app + Redis + OpenSearch

### Option 3: With MCP Servers (for Claude Code integration)
```bash
docker-compose --profile mcp up -d
```
This adds: MCP server + MCP Knowledge server (RAG for internal docs)

### Environment Variables
Create `.env` file:
```env
# AWS (required for AI features)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# Services (auto-configured in Docker)
>>>>>>> 04ca1a3554d0e96a498278e69485ff09f1595add
REDIS_URL=redis://localhost:6379
OPENSEARCH_HOST=http://localhost:9200
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check + mode status |
| `POST /api/query` | AI query (FULL MODE) |
| `GET /api/autocomplete/{field}?q=` | Autocomplete search |
| `GET /api/search/semantic?q=` | Semantic search |
| `GET /api/knowledge/search?q=` | Knowledge base search |
| `POST /api/knowledge/upload` | Upload knowledge docs |
| `POST /api/address/verify` | Address verification |

## Project Structure

```
icda-prototype/
├── main.py              # FastAPI app
├── run.bat              # Windows quick start
├── run.sh               # Mac/Linux quick start
├── icda/                # Core modules
│   ├── cache.py         # Redis + memory fallback
│   ├── embeddings.py    # Titan embeddings
│   ├── knowledge.py     # RAG knowledge base
│   ├── nova.py          # Bedrock Nova AI
│   └── vector_index.py  # OpenSearch + fallback
├── knowledge/           # Knowledge documents (auto-indexed)
└── customer_data.json   # Sample customer data
```

## Adding Knowledge Documents

<<<<<<< HEAD
1. Add `.md` files to `knowledge/` folder
2. Register in `main.py`:
```python
KNOWLEDGE_DOCUMENTS = [
    {"file": "your-doc.md", "category": "category", "tags": ["tag1"]}
]
```
3. Restart - auto-indexed on startup
=======
Just drop files into the `knowledge/` folder - they auto-index on startup!

```
knowledge/
├── address-standards/     # Category = "address-standards"
│   └── your-doc.md
├── examples/              # Category = "examples"
│   └── test-cases.md
└── any-file.md            # Category = "general"
```

**Supported formats:** `.md`, `.txt`, `.json`

**Auto-tagging:** Add YAML frontmatter for custom tags:
```yaml
---
tags: [puerto-rico, validation, testing]
---
# Your Document Title
```

**Or just name files descriptively** - tags auto-inferred from filename:
- `pr-address-examples.md` → tags: `puerto-rico`, `addressing`, `examples`

**Re-index manually:** `POST /api/knowledge/reindex`
>>>>>>> 04ca1a3554d0e96a498278e69485ff09f1595add

## License

MIT
