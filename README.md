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

1. Add `.md` files to `knowledge/` folder
2. Register in `main.py`:
```python
KNOWLEDGE_DOCUMENTS = [
    {"file": "your-doc.md", "category": "category", "tags": ["tag1"]}
]
```
3. Restart - auto-indexed on startup

## License

MIT
