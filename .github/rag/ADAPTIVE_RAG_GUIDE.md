# Adaptive RAG System Guide

**Kubernetes-like auto-configuration for any Claude interface**

## Overview

The Adaptive RAG System automatically detects your environment and configures itself:

```
┌─────────────────────────────────────────────────────────────┐
│                    ADAPTIVE RAG ENGINE                       │
├─────────────────────────────────────────────────────────────┤
│  DETECT           │  INDEX            │  SERVE              │
│  ───────          │  ─────            │  ─────              │
│  • Bedrock?       │  • Java/Spring    │  • REST API         │
│  • Copilot?       │  • Python/FastAPI │  • File Inject      │
│  • Docker Agent?  │  • TypeScript     │  • STDIN/STDOUT     │
│  • Claude Code?   │  • Markdown       │  • MCP Protocol     │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: Docker (Recommended)

```bash
# From your project directory
cd /path/to/your/project

# Start RAG service
PROJECT_PATH=$(pwd) docker-compose -f .github/rag/docker-compose.rag.yml up -d

# Query via REST
curl http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"query": "find authentication logic", "n_results": 5}'
```

### Option 2: Python Module

```python
from rag import AdaptiveRAGEngine

# Initialize - auto-detects environment
engine = AdaptiveRAGEngine("/path/to/project")

# Index project
engine.index_project()

# Query
results = engine.query("find database connection")
print(results)

# Get context for LLM prompt
context = engine.get_context_for_prompt("how does auth work?")
print(context)
```

### Option 3: Command Line

```bash
# Index a project
python -m rag.adaptive_rag --project /path/to/project --index

# Query
python -m rag.adaptive_rag --project /path/to/project --query "find auth"

# Start REST server
python -m rag.adaptive_rag --project /path/to/project --serve --port 8080
```

## Interface Adapters

### REST API (Default)

```bash
# Health check
curl http://localhost:8080/health

# Query
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "n_results": 5}'

# Force re-index
curl -X POST http://localhost:8080/index \
  -H "Content-Type: application/json" \
  -d '{"force_reindex": true}'

# Get stats
curl http://localhost:8080/stats
```

### STDIN/STDOUT (Pipes)

```bash
# Single query
echo '{"query": "find auth"}' | python -m rag.adaptive_rag --adapter stdin

# Interactive
python -m rag.adaptive_rag --adapter stdin
> find authentication
> {"query": "database connection", "n_results": 3}
```

### File Injection (GitHub Copilot)

```bash
# Generate context files for Copilot
python -m rag.adaptive_rag --adapter file

# Creates:
#   .github/context/PROJECT_CONTEXT.md
#   .github/context/QUERY_RESULTS.md (after queries)
```

## AWS Bedrock Integration

```python
import boto3
from rag import AdaptiveRAGEngine

# Initialize RAG
engine = AdaptiveRAGEngine("/path/to/project")
engine.index_project()

# Get context for Bedrock prompt
context = engine.get_context_for_prompt("how does auth work?")

# Call Bedrock with context
bedrock = boto3.client('bedrock-runtime')
response = bedrock.invoke_model(
    modelId='anthropic.github-3-sonnet-20240229-v1:0',
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{
            "role": "user",
            "content": f"{context}\n\nQuestion: How does authentication work?"
        }],
        "max_tokens": 4096
    })
)
```

## Environment Detection

The system automatically detects:

| Environment Variable | Detected Interface |
|---------------------|-------------------|
| `AWS_BEDROCK_RUNTIME` | Bedrock |
| `GITHUB_COPILOT` | Copilot |
| `DOCKER_AI_AGENT` | Docker Agent |
| `CLAUDE_CODE` | Claude Code |
| `RAG_REST_API` | REST API |

## Project Type Detection

Automatically detects project structure:

| Files Present | Detected Type |
|--------------|---------------|
| `pom.xml` + spring-boot | Java Spring |
| `build.gradle` | Java Gradle |
| `requirements.txt` + fastapi | Python FastAPI |
| `requirements.txt` + django | Python Django |
| `package.json` + next | Node Next.js |
| `package.json` + react | Node React |
| `go.mod` | Go |
| `Cargo.toml` | Rust |

## FedRAMP / Air-Gapped Mode

```bash
# Enable FedRAMP mode
export FEDRAMP_ENVIRONMENT=true
export AIR_GAPPED=true

# Start service
python -m rag.adaptive_rag --serve
```

In FedRAMP/air-gapped mode:
- No external network calls
- ChromaDB runs locally
- No telemetry
- All processing on-premise

## API Reference

### POST /query

```json
{
  "query": "search term",
  "n_results": 5,
  "filters": {
    "chunk_type": "spring_controller"
  }
}
```

Response:
```json
{
  "query": "search term",
  "results": [
    {
      "id": "file.java::ClassName::method::42",
      "content": "public void authenticate(...",
      "metadata": {
        "file_path": "src/AuthController.java",
        "chunk_type": "spring_controller",
        "start_line": 42,
        "end_line": 67
      },
      "similarity_score": 0.87
    }
  ],
  "context": {
    "project_type": "java_spring",
    "interface": "rest_api"
  }
}
```

### POST /index

```json
{
  "force_reindex": false
}
```

### GET /health

```json
{
  "status": "healthy",
  "context": {
    "interface": "rest_api",
    "project_type": "java_spring",
    "has_docker": true,
    "is_fedramp": true
  }
}
```

### GET /stats

```json
{
  "total_documents": 1547,
  "provider": "ChromaDB (Local)",
  "project_root": "/project",
  "project_type": "java_spring"
}
```

## Troubleshooting

### "No chunks found"
- Check that your project has supported file types (.java, .py, .ts, .js, .md)
- Verify project root is correct
- Check `.gitignore` patterns aren't excluding code

### "ChromaDB connection failed"
- Ensure write permissions on `.github/rag/chroma_db`
- Check disk space
- Try `--force-reindex`

### "REST API not responding"
- Check port 8080 is available
- Verify Docker container is running
- Check logs: `docker logs adaptive-rag`

## Architecture

```
adaptive_rag.py
├── EnvironmentDetector      # Detects interface & project type
├── AdaptiveRAGEngine        # Main orchestrator
│   ├── ChromaVectorDatabase # Local vector storage
│   └── UniversalChunker     # Multi-language chunking
└── Adapters
    ├── RESTAdapter          # FastAPI REST server
    ├── STDINAdapter         # Command line / pipes
    └── FileInjectAdapter    # Copilot integration
```

---

**Version**: 2.0.0 | **FedRAMP**: Compliant | **Dependencies**: Self-contained
