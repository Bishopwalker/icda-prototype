# RAG_CONTEXT.md - Universal Code Discovery Patterns

## Intelligent Search Strategies
**Optimized patterns for understanding any codebase quickly**

### Project Discovery Sequence
**Follow this order for maximum context efficiency:**

1. **Project Structure** - `find . -type f -name "*.json" -o -name "*.yaml" -o -name "*.toml" | head -20`
2. **Entry Points** - Look for main.py, index.js, app.py, main.go, etc.
3. **Configuration** - package.json, requirements.txt, go.mod, Cargo.toml, etc.
4. **Documentation** - README.md, docs/, wiki/, etc.

### Code Search Patterns
**Universal patterns that work across languages:**

#### Function/Method Discovery
```bash
# Find function definitions (language-agnostic)
grep -r "def \|function \|func \|fn \|public \|private \|const.*=>" . --include="*.py" --include="*.js" --include="*.ts" --include="*.go" --include="*.rs"

# Find class definitions
grep -r "class \|struct \|interface \|type.*struct\|impl " . --include="*.py" --include="*.js" --include="*.ts" --include="*.go" --include="*.rs"
```

#### Import/Dependency Tracking
```bash
# Find imports/requires
grep -r "import \|require\|from.*import\|use \|#include" . --include="*.py" --include="*.js" --include="*.ts" --include="*.go" --include="*.rs" --include="*.c" --include="*.cpp"
```

#### Configuration & Environment
```bash
# Find environment variables
grep -r "process\.env\|os\.environ\|ENV\[" . --include="*.py" --include="*.js" --include="*.ts"

# Find configuration files
find . -name "*.config.*" -o -name ".env*" -o -name "*rc" -o -name "*.ini"
```

### Architecture Discovery

#### API Endpoints
```bash
# REST endpoints
grep -r "@app\.route\|router\.\|app\.\(get\|post\|put\|delete\)\|@RestController\|@RequestMapping" .

# GraphQL schemas
find . -name "*.graphql" -o -name "*schema*" -o -name "*resolvers*"
```

#### Database Models
```bash
# ORM models
grep -r "class.*Model\|Schema\|@Entity\|CREATE TABLE\|type.*struct.*gorm" .

# Database connections
grep -r "connect\|database\|db\.\|session\|query" . --include="*.py" --include="*.js" --include="*.go"
```

#### Component Structure
```bash
# Frontend components
find . -name "*.component.*" -o -name "*.vue" -o -name "*Component.js*" -o -name "*Component.tsx"

# State management
grep -r "useState\|useEffect\|createStore\|Vuex\|Redux\|Context" . --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx" --include="*.vue"
```

### Testing Discovery
```bash
# Test files
find . -name "*test*" -o -name "*spec*" -o -name "__tests__" -type f

# Test patterns
grep -r "describe\|it\|test\|Test\|assert\|expect\|should" . --include="*test*" --include="*spec*"
```

### Build & Deploy Discovery
```bash
# Build configuration
find . -name "*config*" -name "*.json" -o -name "webpack*" -o -name "vite*" -o -name "rollup*"

# CI/CD pipelines
find . -name ".github" -o -name ".gitlab*" -o -name "Jenkinsfile" -o -name ".circleci" -type d

# Docker/containerization
find . -name "Dockerfile*" -o -name "docker-compose*" -o -name "*.dockerfile"
```

---

## CONTEXT-SPECIFIC SEARCH PATTERNS

### Frontend Codebase Analysis
```bash
# Component hierarchy
grep -r "import.*from\|require.*\.\/" . --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx" | head -50

# Routing
grep -r "Route\|router\|navigate\|Link to" . --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx"

# State management
grep -r "useState\|useReducer\|createStore\|atom\|signal" . --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx"
```

### Backend API Analysis
```bash
# Endpoint definitions
grep -r "@.*route\|@.*mapping\|router\.\|app\.\(get\|post\|put\|delete\)" .

# Middleware
grep -r "middleware\|@.*Before\|@.*After\|use\(" . --include="*.py" --include="*.js" --include="*.go"

# Authentication
grep -r "auth\|jwt\|token\|login\|authenticate\|authorize" . --include="*.py" --include="*.js" --include="*.go"
```

### Database Layer Analysis
```bash
# Models/Schemas
grep -r "class.*Model\|Schema\|@Entity\|@Table\|CREATE TABLE" .

# Queries
grep -r "SELECT\|INSERT\|UPDATE\|DELETE\|query\|find\|save" . --include="*.py" --include="*.js" --include="*.sql"

# Migrations
find . -name "*migration*" -o -name "*migrate*" -o -name "versions" -type d
```

---

## INTELLIGENT CONTEXT EXTRACTION

### Understanding Data Flow
1. **Entry point** - Find main function/app initialization
2. **Request handling** - Trace from routes to business logic
3. **Data layer** - Follow from business logic to database/storage
4. **Response formatting** - Track from data back to API response

### Dependency Mapping
```bash
# Direct dependencies
grep -A 5 -B 5 "import.*from.*\|require.*\|use .*::" [target_file]

# Find all files that import a specific module
grep -r "import.*[module_name]\|from.*[module_name]" . --include="*.py" --include="*.js" --include="*.ts"
```

### Error Handling Patterns
```bash
# Exception handling
grep -r "try\|catch\|except\|Error\|panic\|Result<" . --include="*.py" --include="*.js" --include="*.ts" --include="*.go" --include="*.rs"

# Logging
grep -r "log\|console\|print\|debug\|error\|warn" . --include="*.py" --include="*.js" --include="*.ts" --include="*.go"
```

---

## PROJECT TYPE PATTERNS

### React/TypeScript Projects
- **Components**: `find . -name "*.tsx" -o -name "*.jsx" | head -20`
- **Hooks**: `grep -r "use[A-Z]" . --include="*.ts" --include="*.tsx"`
- **Context**: `grep -r "createContext\|useContext" . --include="*.ts" --include="*.tsx"`

### Python/FastAPI Projects
- **Models**: `grep -r "class.*BaseModel\|class.*Model" . --include="*.py"`
- **Endpoints**: `grep -r "@app\.\|@router\." . --include="*.py"`
- **Schemas**: `find . -name "*schema*" -o -name "*model*" --include="*.py"`

### Go Projects
- **Packages**: `find . -name "*.go" -exec grep -l "package " {} \;`
- **Handlers**: `grep -r "func.*Handler\|func.*\(w http\.ResponseWriter" . --include="*.go"`
- **Structs**: `grep -r "type.*struct" . --include="*.go"`

### Rust Projects
- **Modules**: `find . -name "mod.rs" -o -name "lib.rs" -o -name "main.rs"`
- **Traits**: `grep -r "trait \|impl.*for" . --include="*.rs"`
- **Macros**: `grep -r "macro_rules!\|#\[.*\]" . --include="*.rs"`

---

## OPTIMIZATION STRATEGIES

### Large Codebase Handling
- **Limit search scope**: Use `--max-depth=3` with find
- **Focus on recent changes**: `git log --oneline -10` for context
- **Key directories first**: src/, lib/, app/, cmd/ before others

### Memory Efficient Searches
- **Stream results**: Use `head -50` to limit output
- **Targeted file types**: Always use `--include="*.ext"`
- **Exclude unnecessary**: `--exclude-dir=node_modules --exclude-dir=.git`

### Context Building Priority
1. **Configuration** (understand stack & setup)
2. **Entry points** (understand application flow)
3. **Core business logic** (understand what the app does)
4. **Integration points** (understand external dependencies)
5. **Testing strategy** (understand quality approach)

---

**Use these patterns to quickly understand any codebase structure and build effective context for development tasks.**
