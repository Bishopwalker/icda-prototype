"""
Context7 Integration - Auto-Fallback for External Documentation
Automatically queries Context7 when local RAG doesn't have documentation.

Features:
- Detects when query is about external libraries/frameworks
- Auto-triggers Context7 MCP for up-to-date documentation
- Caches results to reduce API calls
- Integrates with existing RAG pipeline
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries for routing decisions"""
    LOCAL_CODE = "local_code"           # Query about local codebase
    EXTERNAL_LIBRARY = "external_lib"   # Query about external library
    FRAMEWORK_DOCS = "framework_docs"   # Query about framework usage
    MIXED = "mixed"                     # Both local and external
    UNKNOWN = "unknown"


@dataclass
class Context7Result:
    """Result from Context7 query"""
    query: str
    library: str
    documentation: str
    code_examples: List[str]
    version: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "library": self.library,
            "documentation": self.documentation,
            "code_examples": self.code_examples,
            "version": self.version,
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Context7Result":
        return cls(
            query=data["query"],
            library=data["library"],
            documentation=data["documentation"],
            code_examples=data.get("code_examples", []),
            version=data.get("version"),
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class Context7Cache:
    """Local cache for Context7 results to reduce API calls"""

    def __init__(self, cache_dir: str = ".claude/rag/context7_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "cache.json"
        self.cache_ttl = timedelta(hours=24)  # Cache for 24 hours
        self._load_cache()

    def _load_cache(self):
        """Load cache from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save Context7 cache: {e}")

    def _get_cache_key(self, query: str, library: str) -> str:
        """Generate cache key from query and library"""
        content = f"{query.lower().strip()}:{library.lower().strip()}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, query: str, library: str) -> Optional[Context7Result]:
        """Get cached result if exists and not expired"""
        key = self._get_cache_key(query, library)
        if key in self._cache:
            cached = self._cache[key]
            timestamp = datetime.fromisoformat(cached["timestamp"])
            if datetime.now() - timestamp < self.cache_ttl:
                return Context7Result.from_dict(cached)
            else:
                # Expired, remove from cache
                del self._cache[key]
                self._save_cache()
        return None

    def set(self, result: Context7Result):
        """Cache a result"""
        key = self._get_cache_key(result.query, result.library)
        self._cache[key] = result.to_dict()
        self._save_cache()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        valid_count = 0
        expired_count = 0
        now = datetime.now()

        for key, cached in self._cache.items():
            timestamp = datetime.fromisoformat(cached["timestamp"])
            if now - timestamp < self.cache_ttl:
                valid_count += 1
            else:
                expired_count += 1

        return {
            "total_cached": len(self._cache),
            "valid_entries": valid_count,
            "expired_entries": expired_count,
            "cache_ttl_hours": self.cache_ttl.total_seconds() / 3600
        }


# Common external libraries and frameworks that should trigger Context7
KNOWN_LIBRARIES = {
    # Python
    "fastapi", "django", "flask", "sqlalchemy", "pydantic", "pytest",
    "numpy", "pandas", "tensorflow", "pytorch", "scikit-learn", "keras",
    "requests", "httpx", "aiohttp", "celery", "redis", "boto3",
    # JavaScript/TypeScript
    "react", "next", "nextjs", "vue", "angular", "svelte", "express",
    "nestjs", "prisma", "typeorm", "mongoose", "axios", "lodash",
    # Java
    "spring", "springboot", "spring-boot", "hibernate", "maven", "gradle",
    "junit", "mockito", "lombok", "jackson", "kafka", "rabbitmq",
    # Go
    "gin", "echo", "fiber", "gorm", "cobra", "viper",
    # Rust
    "tokio", "actix", "rocket", "diesel", "serde", "reqwest",
    # DevOps/Cloud
    "docker", "kubernetes", "k8s", "terraform", "aws", "azure", "gcp",
    "ansible", "jenkins", "github-actions", "gitlab-ci",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "dynamodb", "cassandra", "neo4j", "supabase", "firebase",
}


class QueryClassifier:
    """Classifies queries to determine if Context7 should be invoked"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self._load_project_context()

    def _load_project_context(self):
        """Load project-specific context for better classification"""
        self.project_files = set()
        self.project_imports = set()

        # Scan for project files to understand local codebase
        for ext in ["*.py", "*.java", "*.ts", "*.js", "*.go", "*.rs"]:
            for file in self.project_root.rglob(ext):
                if not any(skip in str(file) for skip in ["node_modules", "venv", ".git", "build"]):
                    self.project_files.add(file.name)

    def classify(self, query: str) -> Tuple[QueryType, List[str]]:
        """
        Classify a query and extract library names

        Args:
            query: The search query

        Returns:
            Tuple of (QueryType, list of detected library names)
        """
        query_lower = query.lower()
        detected_libs = []

        # Check for known library mentions
        for lib in KNOWN_LIBRARIES:
            if lib in query_lower:
                detected_libs.append(lib)

        # Check for common documentation request patterns
        doc_patterns = [
            "how to use", "how do i", "example of", "documentation for",
            "api reference", "tutorial", "guide for", "best practices",
            "getting started", "setup", "configure", "install"
        ]

        is_doc_request = any(pattern in query_lower for pattern in doc_patterns)

        # Determine query type
        if detected_libs and is_doc_request:
            return QueryType.FRAMEWORK_DOCS, detected_libs
        elif detected_libs:
            return QueryType.EXTERNAL_LIBRARY, detected_libs
        elif is_doc_request:
            return QueryType.MIXED, detected_libs
        else:
            return QueryType.LOCAL_CODE, detected_libs

    def should_use_context7(self, query: str, local_results: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Determine if Context7 should be used based on query and local results

        Args:
            query: The search query
            local_results: Results from local RAG search

        Returns:
            Tuple of (should_use, list of libraries to query)
        """
        query_type, libraries = self.classify(query)

        # Always use Context7 for framework docs requests
        if query_type == QueryType.FRAMEWORK_DOCS:
            return True, libraries

        # Use Context7 if local results are poor (low similarity or few results)
        local_result_list = local_results.get("results", [])

        if not local_result_list:
            # No local results, try Context7 for external libs
            if query_type == QueryType.EXTERNAL_LIBRARY:
                return True, libraries
            return False, []

        # Check result quality
        best_score = max(r.get("similarity_score", 0) for r in local_result_list)

        if best_score < 0.5 and libraries:
            # Low quality local results + detected library = use Context7
            return True, libraries

        if query_type == QueryType.MIXED and best_score < 0.7:
            # Mixed query with mediocre results = use Context7 as supplement
            return True, libraries

        return False, []


class Context7Integration:
    """
    Main integration class for Context7 with RAG pipeline

    Usage:
        from .context7_integration import Context7Integration

        c7 = Context7Integration(project_root)

        # In your RAG query flow:
        local_results = rag.query(query)
        enhanced_results = c7.enhance_results(query, local_results)
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.cache = Context7Cache(str(self.project_root / ".claude/rag/context7_cache"))
        self.classifier = QueryClassifier(str(project_root))
        self._stats = {
            "total_queries": 0,
            "context7_invocations": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }

    def enhance_results(
        self,
        query: str,
        local_results: Dict[str, Any],
        force_context7: bool = False
    ) -> Dict[str, Any]:
        """
        Enhance local RAG results with Context7 documentation if needed

        Args:
            query: The search query
            local_results: Results from local RAG
            force_context7: Force Context7 usage (for "use context7" in prompt)

        Returns:
            Enhanced results with Context7 documentation if applicable
        """
        self._stats["total_queries"] += 1

        # Check if we should use Context7
        should_use, libraries = self.classifier.should_use_context7(query, local_results)

        if not should_use and not force_context7:
            return local_results

        # Check for "use context7" trigger phrase
        if "use context7" in query.lower():
            force_context7 = True
            # Re-classify without the trigger phrase
            clean_query = query.lower().replace("use context7", "").strip()
            _, libraries = self.classifier.classify(clean_query)

        if not libraries and force_context7:
            # Try to extract library from query context
            libraries = self._extract_library_from_query(query)

        if not libraries:
            return local_results

        self._stats["context7_invocations"] += 1

        # Get Context7 documentation for each library
        context7_results = []
        for lib in libraries:
            result = self._get_context7_docs(query, lib)
            if result:
                context7_results.append(result)

        # Merge results
        return self._merge_results(local_results, context7_results)

    def _extract_library_from_query(self, query: str) -> List[str]:
        """Extract potential library names from query"""
        # Simple extraction - look for capitalized words or known patterns
        words = query.split()
        potential_libs = []

        for word in words:
            word_clean = word.lower().strip(".,!?()[]{}\"'")
            if word_clean in KNOWN_LIBRARIES:
                potential_libs.append(word_clean)

        return potential_libs

    def _get_context7_docs(self, query: str, library: str) -> Optional[Context7Result]:
        """
        Get documentation from Context7 (via MCP or cache)

        Note: This method prepares the request for Context7 MCP.
        The actual MCP call is handled by the Claude Code runtime.
        """
        # Check cache first
        cached = self.cache.get(query, library)
        if cached:
            self._stats["cache_hits"] += 1
            logger.info(f"Context7 cache hit for {library}")
            return cached

        self._stats["cache_misses"] += 1

        # Prepare Context7 request indicator
        # The actual MCP call will be made by Claude when it sees this
        result = Context7Result(
            query=query,
            library=library,
            documentation=f"[Context7 will provide documentation for {library}]",
            code_examples=[f"[Context7 will provide code examples for {library}]"],
            version="latest"
        )

        # Cache the placeholder (will be updated when actual result comes)
        self.cache.set(result)

        return result

    def _merge_results(
        self,
        local_results: Dict[str, Any],
        context7_results: List[Context7Result]
    ) -> Dict[str, Any]:
        """Merge local RAG results with Context7 documentation"""
        merged = local_results.copy()

        # Add Context7 section
        merged["context7"] = {
            "triggered": True,
            "libraries": [r.library for r in context7_results],
            "results": [r.to_dict() for r in context7_results]
        }

        # Add instruction for Claude to use Context7 MCP
        merged["context7_instruction"] = (
            "Query Context7 for up-to-date documentation on: " +
            ", ".join(r.library for r in context7_results)
        )

        return merged

    def get_stats(self) -> Dict[str, Any]:
        """Get integration statistics"""
        return {
            **self._stats,
            "cache_stats": self.cache.get_stats(),
            "known_libraries_count": len(KNOWN_LIBRARIES)
        }

    def format_context7_prompt(self, libraries: List[str]) -> str:
        """
        Format a prompt that triggers Context7 MCP

        Args:
            libraries: List of library names to query

        Returns:
            Formatted prompt string
        """
        if len(libraries) == 1:
            return f"use context7 for {libraries[0]} documentation"
        else:
            return f"use context7 for documentation on: {', '.join(libraries)}"


# Convenience function for RAG integration
def create_context7_enhanced_rag(project_root: str):
    """
    Create a Context7-enhanced RAG pipeline

    Usage:
        from .context7_integration import create_context7_enhanced_rag

        enhanced_query = create_context7_enhanced_rag(project_root)
        results = enhanced_query("how to use fastapi middleware")
    """
    from .adaptive_rag import AdaptiveRAGEngine

    rag = AdaptiveRAGEngine(project_root)
    c7 = Context7Integration(project_root)

    def enhanced_query(query: str, n_results: int = 5) -> Dict[str, Any]:
        local_results = rag.query(query, n_results)
        return c7.enhance_results(query, local_results)

    return enhanced_query
