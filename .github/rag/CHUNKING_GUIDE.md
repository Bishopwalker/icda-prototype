# 📦 Universal Code Chunking Guide

**Intelligent, language-aware code chunking for RAG systems**

## 🎯 Overview

This chunking strategy intelligently splits your codebase into semantically meaningful chunks that preserve context and structure. **Special focus on Java Spring Boot projects!**

## ✅ Supported Languages

### 🔥 Java & Spring Boot (Full Support)

**Why Spring Boot needs special handling:**
- Spring uses annotations (`@RestController`, `@Service`, etc.)
- Endpoints defined via `@GetMapping`, `@PostMapping`, etc.
- Dependency injection via `@Autowired`
- JPA entities with `@Entity`, `@Table`

**What we extract:**

#### 1. Spring Controllers

```java
@RestController
@RequestMapping("/api/products")
public class ProductController {

    @Autowired
    private ProductService productService;

    @GetMapping("/{id}")
    public ResponseEntity<Product> getProduct(@PathVariable Long id) {
        return ResponseEntity.ok(productService.findById(id));
    }

    @PostMapping
    public ResponseEntity<Product> createProduct(@RequestBody ProductDTO dto) {
        Product product = productService.create(dto);
        return ResponseEntity.status(201).body(product);
    }
}
```

**Chunking Result:**

**Chunk 1 (Class-level):**
- Type: `SPRING_CONTROLLER`
- Content: Full class with all methods
- Metadata:
  ```json
  {
    "class_name": "ProductController",
    "annotations": ["@RestController", "@RequestMapping(\"/api/products\")"],
    "base_path": "/api/products",
    "dependencies": ["ProductService"],
    "framework": "spring-boot",
    "language": "java"
  }
  ```

**Chunk 2 (Method: getProduct):**
- Type: `JAVA_METHOD`
- Content: Just the `getProduct` method
- Metadata:
  ```json
  {
    "class_name": "ProductController",
    "method_name": "getProduct",
    "annotations": ["@GetMapping(\"/{id}\")"],
    "is_endpoint": true,
    "http_methods": ["GET"],
    "endpoint_path": "/{id}",
    "framework": "spring-boot"
  }
  ```

**Chunk 3 (Method: createProduct):**
- Type: `JAVA_METHOD`
- Content: Just the `createProduct` method
- Metadata:
  ```json
  {
    "class_name": "ProductController",
    "method_name": "createProduct",
    "annotations": ["@PostMapping"],
    "is_endpoint": true,
    "http_methods": ["POST"],
    "framework": "spring-boot"
  }
  ```

#### 2. Spring Services

```java
@Service
public class ProductService {

    @Autowired
    private ProductRepository productRepository;

    public Product findById(Long id) {
        return productRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("Product not found"));
    }

    @Transactional
    public Product create(ProductDTO dto) {
        Product product = new Product();
        product.setName(dto.getName());
        product.setPrice(dto.getPrice());
        return productRepository.save(product);
    }
}
```

**Chunks Created:**
1. **Class chunk**: Full service with `@Service` annotation
2. **Method chunks**: Each method separately
   - Metadata includes: `@Transactional`, dependencies

#### 3. JPA Repositories

```java
@Repository
public interface ProductRepository extends JpaRepository<Product, Long> {

    List<Product> findByCategory(String category);

    @Query("SELECT p FROM Product p WHERE p.price < :maxPrice")
    List<Product> findAffordableProducts(@Param("maxPrice") BigDecimal maxPrice);
}
```

**Chunk Type:** `SPRING_REPOSITORY`
- Captures interface definition
- Tracks custom query methods
- Metadata includes JPA entity type

#### 4. JPA Entities

```java
@Entity
@Table(name = "products")
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private BigDecimal price;

    // Getters, setters, etc.
}
```

**Chunk Type:** `SPRING_ENTITY`
- Metadata:
  ```json
  {
    "class_name": "Product",
    "table_name": "products",
    "framework": "spring-boot",
    "annotations": ["@Entity", "@Table(name = \"products\")"]
  }
  ```

#### 5. Configuration Classes

```java
@Configuration
public class AppConfig {

    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }

    @Bean
    public ModelMapper modelMapper() {
        return new ModelMapper();
    }
}
```

**Chunk Type:** `SPRING_CONFIG`
- Tracks `@Bean` definitions
- Useful for dependency discovery

### 🐍 Python & FastAPI

**What we extract:**

#### Classes
```python
class UserService:
    def __init__(self, db: Database):
        self.db = db

    def get_user(self, user_id: int) -> User:
        return self.db.query(User).filter(User.id == user_id).first()
```

**Chunk Type:** `PYTHON_CLASS`
- Full class definition
- Methods included as part of class

#### Functions
```python
def calculate_total(items: List[Item]) -> float:
    return sum(item.price * item.quantity for item in items)
```

**Chunk Type:** `PYTHON_FUNCTION`
- Standalone function
- Includes docstring if present

#### FastAPI Routes
```python
@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Database = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

**Chunk Type:** `FASTAPI_ROUTE`
- Metadata:
  ```json
  {
    "is_fastapi_route": true,
    "http_method": "GET",
    "name": "get_user"
  }
  ```

### 📘 TypeScript/JavaScript & React

**What we extract:**

#### Classes
```typescript
class UserManager {
    private users: Map<string, User>;

    constructor() {
        this.users = new Map();
    }

    addUser(user: User): void {
        this.users.set(user.id, user);
    }
}
```

**Chunk Type:** `TS_CLASS`

#### Functions
```typescript
export function calculateDiscount(price: number, percentage: number): number {
    return price * (1 - percentage / 100);
}
```

**Chunk Type:** `TS_FUNCTION`

#### React Components
```typescript
export const UserProfile: React.FC<UserProfileProps> = ({ userId }) => {
    const [user, setUser] = useState<User | null>(null);

    useEffect(() => {
        fetchUser(userId).then(setUser);
    }, [userId]);

    return <div>{user?.name}</div>;
};
```

**Chunk Type:** `REACT_COMPONENT`

### 📝 Markdown Documentation

```markdown
# Getting Started

This guide explains how to set up the project.

## Prerequisites

You need the following installed:
- Node.js 18+
- Java 17+

## Installation

Run the following commands:
```

**Chunking:**
- Each header section becomes a separate chunk
- Type: `MARKDOWN_SECTION`
- Preserves header hierarchy

## 🔧 Chunking Strategy Details

### Class-Level Chunking

**Benefits:**
- Preserves full context (class annotations, fields, all methods)
- Useful for understanding overall structure
- Captures dependencies and configuration

**Use Cases:**
- "What controllers exist in the system?"
- "Show me the UserService class"
- "What are all the JPA entities?"

### Method-Level Chunking

**Benefits:**
- Fine-grained code search
- Direct access to specific functionality
- Better for targeted questions

**Use Cases:**
- "How do we handle GET /api/users/{id}?"
- "Show me the createProduct implementation"
- "What validation is done in saveOrder?"

### Metadata Enrichment

**Spring Boot Metadata:**
```json
{
  "class_name": "OrderController",
  "chunk_type": "spring_controller",
  "annotations": ["@RestController", "@RequestMapping(\"/api/orders\")"],
  "base_path": "/api/orders",
  "dependencies": ["OrderService", "PaymentService"],
  "framework": "spring-boot",
  "language": "java",
  "is_endpoint": true,
  "http_methods": ["POST"],
  "endpoint_path": "/",
  "file_path": "src/main/java/com/example/controller/OrderController.java",
  "start_line": 15,
  "end_line": 45
}
```

**Benefits:**
- Enables filtered search ("show me all POST endpoints")
- Track dependencies between components
- Understand HTTP API surface area
- Map routes to implementations

## 📊 Chunking Statistics

For a typical Spring Boot project:

```
Total Chunks: ~500-2000 (depending on size)

Breakdown:
- SPRING_CONTROLLER:     15-30 classes  +  50-150 methods
- SPRING_SERVICE:        20-40 classes  +  80-200 methods
- SPRING_REPOSITORY:     10-20 interfaces
- SPRING_ENTITY:         15-30 classes
- SPRING_CONFIG:         5-10 classes
- JAVA_CLASS:            30-100 classes +  100-400 methods
- MARKDOWN_SECTION:      50-200 sections
```

## 🎯 Search Examples

### Finding Spring Endpoints

```python
from .github.rag import CloudRAGPipeline, VectorProvider

rag = CloudRAGPipeline(
    project_root="/path/to/spring-boot-project",
    provider=VectorProvider.CHROMA
)

# Find all GET endpoints
results = rag.query("GET endpoint user")

# Results will include methods with metadata:
# { "is_endpoint": true, "http_methods": ["GET"], ... }
```

### Finding Services

```python
# Find user-related services
results = rag.query("UserService business logic")

# Returns chunks with chunk_type="spring_service"
```

### Finding JPA Entities

```python
# Find entity definitions
results = rag.query("Product entity JPA")

# Returns chunks with chunk_type="spring_entity"
# Metadata includes table_name
```

## 🔍 Advanced Features

### 1. Annotation Detection

Automatically recognizes:
- `@RestController` → SPRING_CONTROLLER
- `@Service` → SPRING_SERVICE
- `@Repository` → SPRING_REPOSITORY
- `@Entity` → SPRING_ENTITY
- `@Configuration` → SPRING_CONFIG
- `@Component` → JAVA_CLASS

### 2. Dependency Tracking

Extracts `@Autowired` dependencies:

```java
@Service
public class OrderService {
    @Autowired
    private PaymentService paymentService;  // ← Tracked

    @Autowired
    private InventoryService inventoryService;  // ← Tracked
}
```

Metadata includes: `{"dependencies": ["PaymentService", "InventoryService"]}`

### 3. Endpoint Path Extraction

Combines `@RequestMapping` + method mappings:

```java
@RestController
@RequestMapping("/api/v1/orders")  // ← Base path
public class OrderController {

    @GetMapping("/{id}")  // ← Method path
    public Order getOrder(@PathVariable Long id) { ... }
    // Full path: /api/v1/orders/{id}
}
```

Metadata: `{"base_path": "/api/v1/orders", "endpoint_path": "/{id}"}`

### 4. JPA Table Name Tracking

```java
@Entity
@Table(name = "customer_orders")  // ← Table name extracted
public class Order { ... }
```

Metadata: `{"table_name": "customer_orders"}`

## 🚀 Usage in RAG System

### Indexing

```python
from .github.rag import CloudRAGPipeline, VectorProvider

# Initialize
rag = CloudRAGPipeline(
    project_root="/path/to/your/spring-boot-project",
    provider=VectorProvider.CHROMA
)

# Index entire project
# This runs the chunking strategy automatically
rag.index_project()

# Chunking happens transparently:
# 1. Scans all .java files
# 2. Detects Spring annotations
# 3. Creates class and method chunks
# 4. Extracts metadata
# 5. Embeds and stores in vector DB
```

### Searching

```python
# Find authentication code
results = rag.query("user authentication security")

# Results include relevant chunks:
for result in results['results']:
    print(f"File: {result['metadata']['file_path']}")
    print(f"Type: {result['metadata']['chunk_type']}")
    print(f"Lines: {result['metadata']['start_line']}-{result['metadata']['end_line']}")
    print(f"Score: {result['similarity_score']:.3f}")
    print(result['content'][:200])
    print()
```

## 🛠️ Customization

### Adding New Language Support

```python
# In chunking_strategy.py

class KotlinChunker:
    """Chunker for Kotlin files"""

    @staticmethod
    def extract_chunks(file_path: str, content: str) -> List[CodeChunk]:
        # Implement Kotlin-specific chunking
        pass

# Register in UniversalChunkingStrategy
class UniversalChunkingStrategy:
    KOTLIN_EXTENSIONS = {'.kt'}

    def chunk_file(self, relative_file_path: str):
        ext = Path(relative_file_path).suffix.lower()

        if ext in self.KOTLIN_EXTENSIONS:
            return KotlinChunker.extract_chunks(...)
        # ... rest of logic
```

### Customizing Spring Detection

```python
# Add custom Spring stereotypes
JavaSpringBootChunker.SPRING_ANNOTATIONS.update({
    '@CustomController': ChunkType.SPRING_CONTROLLER,
    '@CustomService': ChunkType.SPRING_SERVICE,
})
```

## 📈 Performance

**Typical Chunking Speed:**
- Small project (100 files): ~2-5 seconds
- Medium project (500 files): ~10-20 seconds
- Large project (2000 files): ~40-60 seconds

**Memory Usage:**
- Chunks stored as CodeChunk objects
- ~1-2 KB per chunk
- 1000 chunks ≈ 1-2 MB memory

## 🔒 Best Practices

### 1. Re-index After Major Changes

```python
# After adding new classes or major refactoring
rag.index_project(force_reindex=True)
```

### 2. Use Specific Queries

```python
# Good: Specific
results = rag.query("OrderController createOrder method")

# Less effective: Too vague
results = rag.query("orders")
```

### 3. Filter by Metadata

```python
# Search only in controllers
from .github.rag.vector_database import CloudRAGPipeline

results = rag.vector_db.search(
    query="user validation",
    filter_dict={"chunk_type": "spring_controller"}
)
```

## 📚 Next Steps

- See `SETUP.md` for RAG system setup
- See `config.py` for configuration options
- See `vector_database.py` for vector storage
- See `memory_service.py` for memory integration

---

**Status:** ✅ Production Ready
**Languages Supported:** Java, Python, TypeScript, Markdown
**Frameworks:** Spring Boot, FastAPI, React
**Last Updated:** 2025-11-13
