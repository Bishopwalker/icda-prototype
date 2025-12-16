"""
Code Index - Development Context Index.

Stores code chunks, API references, and development documentation
for internal tooling and code completion assistance.

Features:
- Language-aware chunking metadata
- Symbol extraction (functions, classes)
- Import/dependency tracking
- Code-specific search optimizations
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import logging
import re

from .base_index import BaseIndex, IndexConfig, SearchResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CodeChunk:
    """A code chunk to be indexed."""
    doc_id: str
    chunk_id: str
    filename: str
    filepath: str
    language: str
    chunk_type: str  # "function", "class", "module", "comment", "mixed"
    chunk_index: int
    text: str
    code_context: str = ""  # Surrounding context
    symbols: list[str] = field(default_factory=list)  # Function/class names
    imports: list[str] = field(default_factory=list)  # Dependencies
    tags: list[str] = field(default_factory=list)
    category: str = "code"


class CodeIndex(BaseIndex):
    """
    Code index for development context and code search.

    Optimized for:
    - Code snippet retrieval
    - Function/class lookup
    - API documentation search
    - Development context for AI assistants

    Schema:
        - doc_id: Parent document ID
        - chunk_id: Unique chunk identifier
        - filename: Source file name
        - filepath: Full file path
        - language: Programming language
        - chunk_type: Type of code (function, class, etc.)
        - chunk_index: Position in document
        - text: Chunk content
        - code_context: Surrounding context
        - symbols: Extracted symbols
        - imports: Dependencies
        - embedding: Vector representation
    """

    # Language file extensions
    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sh": "bash",
        ".bat": "batch",
        ".ps1": "powershell",
        ".sql": "sql",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".xml": "xml",
        ".html": "html",
        ".css": "css",
    }

    def __init__(
        self,
        opensearch_client: Any,
        embedder: Any,
        index_name: str = "icda-code",
    ):
        config = IndexConfig(
            name=index_name,
            shards=2,
            replicas=0,
        )
        super().__init__(opensearch_client, embedder, config)

    @property
    def mapping(self) -> dict[str, Any]:
        """OpenSearch mapping for the code index."""
        return {
            "properties": {
                "doc_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "filename": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "filepath": {"type": "keyword"},
                "language": {"type": "keyword"},
                "chunk_type": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                "text": {
                    "type": "text",
                    "analyzer": "standard",
                },
                "code_context": {"type": "text"},
                "symbols": {"type": "keyword"},
                "imports": {"type": "keyword"},
                "tags": {"type": "keyword"},
                "category": {"type": "keyword"},
                "content_hash": {"type": "keyword"},
                "indexed_at": {"type": "date"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": self.EMBEDDING_DIMENSION,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 48,
                        },
                    },
                },
            }
        }

    async def index_code_chunk(
        self,
        chunk: CodeChunk,
        generate_embedding: bool = True,
    ) -> bool:
        """
        Index a code chunk.

        Args:
            chunk: CodeChunk to index
            generate_embedding: Whether to generate embedding

        Returns:
            bool: True if indexed successfully
        """
        document = {
            "doc_id": chunk.doc_id,
            "chunk_id": chunk.chunk_id,
            "filename": chunk.filename,
            "filepath": chunk.filepath,
            "language": chunk.language,
            "chunk_type": chunk.chunk_type,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "code_context": chunk.code_context,
            "symbols": chunk.symbols,
            "imports": chunk.imports,
            "tags": chunk.tags,
            "category": chunk.category,
            "content_hash": self.generate_content_hash(chunk.text),
            "indexed_at": datetime.utcnow().isoformat(),
        }

        # Generate embedding
        if generate_embedding:
            # For code, include filename and symbols in embedding context
            embed_text = f"{chunk.filename}\n{' '.join(chunk.symbols)}\n{chunk.text}"
            embedding = await self.generate_embedding(embed_text[:8000])
            if embedding:
                document["embedding"] = embedding

        return await self.index_document(chunk.chunk_id, document, refresh=True)

    async def index_file(
        self,
        filepath: str,
        content: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> tuple[int, int]:
        """
        Index an entire code file.

        Args:
            filepath: Path to the file
            content: File content
            chunk_size: Words per chunk
            chunk_overlap: Words overlap between chunks

        Returns:
            tuple: (success_count, error_count)
        """
        # Detect language
        ext = "." + filepath.split(".")[-1].lower() if "." in filepath else ""
        language = self.LANGUAGE_MAP.get(ext, "unknown")

        # Extract filename
        filename = filepath.split("/")[-1].split("\\")[-1]

        # Generate doc_id from filepath
        doc_id = self.generate_content_hash(filepath)

        # Delete existing chunks for this file
        await self.delete_by_query({"term": {"doc_id": doc_id}})

        # Chunk the content
        chunks = self._chunk_code(content, chunk_size, chunk_overlap)

        # Extract symbols from the file
        all_symbols = self._extract_symbols(content, language)
        all_imports = self._extract_imports(content, language)

        success = 0
        errors = 0

        for i, chunk_text in enumerate(chunks):
            chunk = CodeChunk(
                doc_id=doc_id,
                chunk_id=f"{doc_id}_chunk_{i}",
                filename=filename,
                filepath=filepath,
                language=language,
                chunk_type=self._detect_chunk_type(chunk_text, language),
                chunk_index=i,
                text=chunk_text,
                code_context=self._get_context(chunks, i),
                symbols=self._extract_symbols(chunk_text, language),
                imports=all_imports if i == 0 else [],  # Imports only on first chunk
                tags=[language, filename.split(".")[0]],
                category="code",
            )

            if await self.index_code_chunk(chunk):
                success += 1
            else:
                errors += 1

        return success, errors

    def _chunk_code(
        self,
        content: str,
        chunk_size: int,
        overlap: int,
    ) -> list[str]:
        """Chunk code content respecting logical boundaries."""
        lines = content.split("\n")
        chunks = []
        current_chunk: list[str] = []
        current_words = 0

        for line in lines:
            line_words = len(line.split())
            current_chunk.append(line)
            current_words += line_words

            # Check if we should start a new chunk
            if current_words >= chunk_size:
                # Try to break at a logical boundary
                chunk_text = "\n".join(current_chunk)
                chunks.append(chunk_text)

                # Keep overlap
                overlap_lines = []
                overlap_words = 0
                for l in reversed(current_chunk):
                    lw = len(l.split())
                    if overlap_words + lw > overlap:
                        break
                    overlap_lines.insert(0, l)
                    overlap_words += lw

                current_chunk = overlap_lines
                current_words = overlap_words

        # Add remaining content
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _detect_chunk_type(self, text: str, language: str) -> str:
        """Detect the type of code in a chunk."""
        text_lower = text.lower()

        if language == "python":
            if re.search(r"^\s*class\s+\w+", text, re.MULTILINE):
                return "class"
            if re.search(r"^\s*def\s+\w+", text, re.MULTILINE):
                return "function"
            if re.search(r"^\s*#", text, re.MULTILINE) and len(text) < 200:
                return "comment"

        elif language in ("javascript", "typescript"):
            if re.search(r"^\s*class\s+\w+", text, re.MULTILINE):
                return "class"
            if re.search(r"(function\s+\w+|const\s+\w+\s*=\s*(\(|async))", text, re.MULTILINE):
                return "function"
            if re.search(r"^\s*(//|/\*)", text, re.MULTILINE) and len(text) < 200:
                return "comment"

        elif language == "java":
            if re.search(r"^\s*(public|private|protected)?\s*class\s+\w+", text, re.MULTILINE):
                return "class"
            if re.search(r"^\s*(public|private|protected)?\s+\w+\s+\w+\s*\(", text, re.MULTILINE):
                return "function"

        return "mixed"

    def _extract_symbols(self, text: str, language: str) -> list[str]:
        """Extract function/class names from code."""
        symbols = []

        if language == "python":
            # Classes
            symbols.extend(re.findall(r"class\s+(\w+)", text))
            # Functions
            symbols.extend(re.findall(r"def\s+(\w+)", text))

        elif language in ("javascript", "typescript"):
            # Classes
            symbols.extend(re.findall(r"class\s+(\w+)", text))
            # Functions
            symbols.extend(re.findall(r"function\s+(\w+)", text))
            # Arrow functions
            symbols.extend(re.findall(r"const\s+(\w+)\s*=\s*(?:async\s*)?\(", text))

        elif language == "java":
            # Classes
            symbols.extend(re.findall(r"class\s+(\w+)", text))
            # Methods
            symbols.extend(re.findall(r"(?:public|private|protected)?\s+\w+\s+(\w+)\s*\(", text))

        return list(set(symbols))

    def _extract_imports(self, text: str, language: str) -> list[str]:
        """Extract import statements from code."""
        imports = []

        if language == "python":
            imports.extend(re.findall(r"^import\s+(\S+)", text, re.MULTILINE))
            imports.extend(re.findall(r"^from\s+(\S+)\s+import", text, re.MULTILINE))

        elif language in ("javascript", "typescript"):
            imports.extend(re.findall(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]", text))
            imports.extend(re.findall(r"require\(['\"]([^'\"]+)['\"]\)", text))

        elif language == "java":
            imports.extend(re.findall(r"^import\s+([\w.]+);", text, re.MULTILINE))

        return list(set(imports))

    def _get_context(self, chunks: list[str], index: int) -> str:
        """Get surrounding context for a chunk."""
        context_parts = []

        # Previous chunk summary
        if index > 0:
            prev = chunks[index - 1]
            context_parts.append(f"[PREV]: {prev[:100]}...")

        # Next chunk summary
        if index < len(chunks) - 1:
            next_ = chunks[index + 1]
            context_parts.append(f"[NEXT]: {next_[:100]}...")

        return " ".join(context_parts)

    async def search_code(
        self,
        query: str,
        language: Optional[str] = None,
        symbols: Optional[list[str]] = None,
        k: int = 10,
    ) -> list[SearchResult]:
        """
        Search for code chunks.

        Args:
            query: Search query
            language: Filter by language
            symbols: Filter by symbol names
            k: Number of results

        Returns:
            List of search results
        """
        # Build filters
        filters: list[dict[str, Any]] = []

        if language:
            filters.append({"term": {"language": language}})

        if symbols:
            filters.append({"terms": {"symbols": symbols}})

        filter_query = {"bool": {"must": filters}} if filters else None

        # Generate query embedding
        embedding = await self.generate_embedding(query)

        if embedding:
            return await self.knn_search(
                embedding=embedding,
                k=k,
                filters=filter_query,
            )
        else:
            # Fallback to text search
            text_query: dict[str, Any] = {
                "bool": {
                    "should": [
                        {"match": {"text": {"query": query, "boost": 2.0}}},
                        {"match": {"symbols": {"query": query, "boost": 3.0}}},
                        {"match": {"filename": {"query": query, "boost": 1.5}}},
                    ],
                    "minimum_should_match": 1,
                }
            }

            if filter_query:
                text_query["bool"]["filter"] = filter_query["bool"]["must"]

            return await self.search(text_query, size=k)

    async def find_symbol(
        self,
        symbol_name: str,
        language: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Find code chunks containing a specific symbol.

        Args:
            symbol_name: Function/class name to find
            language: Optional language filter

        Returns:
            List of matching chunks
        """
        query: dict[str, Any] = {
            "bool": {
                "must": [
                    {"term": {"symbols": symbol_name}},
                ],
            }
        }

        if language:
            query["bool"]["filter"] = [{"term": {"language": language}}]

        return await self.search(query, size=20)
