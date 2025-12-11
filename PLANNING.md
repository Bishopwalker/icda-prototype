# PLANNING.md
# ICDA Prototype - Project Architecture & Planning

## Project Overview

**ICDA (Intelligent Customer Data Access)** - NLP-powered customer data query system with AWS Bedrock Nova integration, guardrails, caching, and address verification.

## Project Architecture

### Frontend Stack
- **Framework**: React 18 + TypeScript 5.6+
- **UI Library**: Material-UI (MUI) 6.x
- **Build Tool**: Vite 5.4+
- **State Management**: React hooks (useState, useEffect)
- **Key Libraries**:
  - `@mui/x-data-grid` - Data tables
  - `axios` - HTTP client
  - `uuid` - Session management

### Backend Stack
- **Framework**: FastAPI (Python 3.11+)
- **Language**: Python 3.11+
- **Key Libraries**:
  - `boto3` - AWS SDK (Bedrock, OpenSearch)
  - `redis[hiredis]` - Caching layer
  - `opensearch-py[async]` - Vector search
  - `pydantic` - Data validation
- **Database**: JSON file (prototype) → OpenSearch (production)
- **AI/ML**: AWS Bedrock Nova (converse API with tool calling)

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Cloud Provider**: AWS (Bedrock, OpenSearch, ElastiCache)
- **Caching**: Redis (local) / ElastiCache (production)
- **Vector Store**: OpenSearch with k-NN plugin

## Core Components

### 1. Query Processing Pipeline
```
User Query → Classifier → Guardrails → Router → Cache/Nova → Response
```

- **Classifier**: LOOKUP (direct CRID) vs COMPLEX (NLP) vs BLOCKED
- **Guardrails**: Input (PII blocking) + Output (redaction)
- **Router**: Routes to cache, vector search, or Bedrock Nova

### 2. Address Verification Pipeline
```
Address Input → Normalizer → Vector Index → ZIP Database → Nova Completer → Verified Address
```

- **AddressIndex**: Builds searchable index from customer addresses
- **AddressVectorIndex**: Semantic address matching
- **ZipDatabase**: ZIP code validation and lookup
- **NovaAddressCompleter**: AI-powered address completion

### 3. Backend Modules (`/icda`)
| Module | Purpose |
|--------|---------|
| `config.py` | Environment configuration |
| `cache.py` | Redis caching layer |
| `classifier.py` | Query type classification |
| `guardrails.py` | PII input/output filtering |
| `router.py` | Request routing logic |
| `nova.py` | Bedrock Nova client with tool calling |
| `database.py` | Customer data access |
| `embeddings.py` | Titan embedding client |
| `vector_index.py` | OpenSearch vector operations |
| `session.py` | User session management |
| `address_*.py` | Address verification pipeline |
| `agents/` | AI agent orchestration |
| `indexes/` | Address and ZIP indexes |

## Development Workflow

### 1. Pre-Development Setup
1. Read `.claude/CLAUDE.md` for development standards
2. Check `TASK.md` for current sprint work
3. Reference `.claude/INITIAL.md` for technical specifications
4. Ensure AWS credentials configured (`AWS_PROFILE=NNGC`)

### 2. Feature Development Process
```bash
# 1. Start development environment
npm run dev  # Starts both backend (port 8000) and frontend (port 5173)

# OR separately:
npm run dev:backend   # uvicorn main:app --reload --port 8000
npm run dev:frontend  # vite dev

# 2. Create feature branch
git checkout -b feature/your-feature-name

# 3. Run linting
npm run lint --prefix frontend

# 4. Build for production
npm run build
```

### 3. Testing Strategy
- **Unit Tests**: pytest (backend), Jest (frontend - to be added)
- **Integration Tests**: `/tests` directory
- **Manual Testing**: Web UI at http://localhost:8000
- **Coverage Requirements**: 80%+ for critical paths

## Naming Conventions

### Files & Directories
- **Python Modules**: `snake_case.py`
- **React Components**: `PascalCase.tsx`
- **Utilities**: `camelCase.ts`
- **Constants**: `UPPER_SNAKE_CASE`
- **Test Files**: `test_*.py` (Python), `*.test.tsx` (React)

### Code Structure
```
icda-prototype/
├── icda/                    # Backend Python package
│   ├── agents/              # AI agent orchestration
│   ├── indexes/             # Address/ZIP indexes
│   ├── config.py            # Configuration
│   ├── nova.py              # Bedrock client
│   └── ...                  # Other modules
├── frontend/                # React frontend
│   ├── src/                 # Source code
│   ├── public/              # Static assets
│   └── ...
├── tests/                   # Test suite
├── templates/               # HTML templates
├── main.py                  # FastAPI entrypoint
└── docker-compose.yml       # Container orchestration
```

## Key Architectural Decisions

### 1. Query Classification
- **Decision**: Three-tier classification (LOOKUP, COMPLEX, BLOCKED)
- **Rationale**: LOOKUP bypasses AI for <5ms response, COMPLEX uses Nova
- **Implementation**: Pattern matching in `classifier.py`

### 2. Guardrails Strategy
- **Decision**: Dual-layer (input blocking + output redaction)
- **Rationale**: Defense in depth for PII protection
- **Implementation**: `guardrails.py` with regex patterns

### 3. Caching Strategy
- **Decision**: Redis with query-type-specific TTLs
- **Rationale**: Balance freshness vs performance
- **Implementation**:
  - Lookups: 1 hour TTL
  - Validations: 24 hours TTL
  - Complex: 5 minutes TTL

### 4. Tool Calling Architecture
- **Decision**: Bedrock Nova `converse` API with structured tools
- **Rationale**: Native tool calling vs prompt engineering
- **Implementation**: Tool definitions in `nova.py`

### 5. Address Verification
- **Decision**: Multi-stage pipeline with AI fallback
- **Rationale**: Fast deterministic matching + AI for ambiguity
- **Implementation**: `address_pipeline.py` orchestrates stages

## Performance Requirements

### API Response Times
- **LOOKUP queries**: <50ms (cache hit) / <200ms (miss)
- **COMPLEX queries**: <3000ms (includes Bedrock latency)
- **Address verification**: <1000ms

### System Performance
- **Concurrent users**: 100+ (prototype)
- **Cache hit rate**: >70% target
- **Memory usage**: <512MB (backend)

## Security & Compliance

### Data Protection
- **PII Blocking**: SSN, credit cards, bank accounts blocked at input
- **PII Redaction**: Output scrubbing for leaked patterns
- **Audit Logging**: All queries logged with session ID

### AWS Security
- **Authentication**: AWS IAM profiles
- **Region**: `us-east-1` (commercial) / `us-gov-west-1` (GovCloud)
- **Bedrock Access**: VPC endpoint recommended for production

## Deployment Strategy

### Environments
- **Development**: Local Docker Compose
- **Production**: AWS (API Gateway + Lambda + ElastiCache + OpenSearch)

### Architecture Mapping
| Prototype | Production |
|-----------|------------|
| In-memory cache | ElastiCache Redis |
| Mock customer data | C Engine + OpenSearch |
| FastAPI | API Gateway + Lambda |
| Single process | Multi-AZ Lambda |
| Local Bedrock calls | VPC Endpoint to Bedrock |

---

**Reference Files:**
- Technical Specifications: `.claude/INITIAL.md`
- Development Standards: `.claude/CLAUDE.md`
- Infrastructure Setup: `.claude/INFRASTRUCTURE.md`
- Current Tasks: `TASK.md`