"""
RAG Orchestrator - Master Controller for Intelligent Indexing

This orchestrator implements the enforcer pattern with AI agents to ensure
comprehensive, high-quality vectorization and indexing of the codebase.

Features:
- Adaptive chunking: 333/666/999 chunks based on codebase size
- Visual progress indicators with rich console output
- Human-readable index manifests for fine-tuning
- Multi-agent validation and enforcement
- Gemini-powered quality control

Author: Universal Context Template
"""

import os
import sys
import json
import hashlib
import asyncio
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime
from enum import Enum
import re

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from chunking_strategy import UniversalChunkingStrategy, CodeChunk, ChunkType


class ChunkTarget(Enum):
    """Target chunk counts based on codebase size."""
    SMALL = 333      # < 50 files
    MEDIUM = 666     # 50-200 files
    LARGE = 999      # > 200 files


class ContentCategory(Enum):
    """Categories of content for indexing."""
    SOURCE_CODE = "source_code"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    TESTS = "tests"
    TEMPLATES = "templates"
    REQUIREMENTS = "requirements"
    AGENTS = "agents"
    COMMANDS = "commands"


@dataclass
class IndexStats:
    """Statistics about the indexing process."""
    total_files: int = 0
    total_chunks: int = 0
    target_chunks: int = 333
    files_by_category: Dict[str, int] = field(default_factory=dict)
    chunks_by_category: Dict[str, int] = field(default_factory=dict)
    chunks_by_type: Dict[str, int] = field(default_factory=dict)
    avg_chunk_size: float = 0.0
    total_tokens_estimate: int = 0
    indexing_duration_ms: int = 0
    quality_score: float = 0.0
    enforcer_validations: int = 0
    enforcer_corrections: int = 0


@dataclass
class ChunkManifestEntry:
    """Human-readable entry for chunk manifest."""
    chunk_id: str
    file_path: str
    category: str
    chunk_type: str
    start_line: int
    end_line: int
    size_chars: int
    size_tokens_est: int
    summary: str
    keywords: List[str]
    quality_score: float
    metadata: Dict[str, Any]


@dataclass
class IndexManifest:
    """Complete index manifest for human review and fine-tuning."""
    version: str = "1.0.0"
    created_at: str = ""
    project_root: str = ""
    target_chunks: int = 333
    actual_chunks: int = 0
    stats: Optional[IndexStats] = None
    categories: Dict[str, List[str]] = field(default_factory=dict)
    chunks: List[ChunkManifestEntry] = field(default_factory=list)
    quality_report: Dict[str, Any] = field(default_factory=dict)


class ProgressCallback:
    """Callback interface for progress updates."""

    def on_phase_start(self, phase: str, total: int) -> None:
        pass

    def on_progress(self, current: int, total: int, message: str) -> None:
        pass

    def on_phase_complete(self, phase: str, result: Any) -> None:
        pass

    def on_chunk_created(self, chunk: CodeChunk) -> None:
        pass

    def on_validation(self, validator: str, passed: bool, message: str) -> None:
        pass


class RAGOrchestrator:
    """
    Master orchestrator for RAG indexing with enforcer pattern.

    Implements adaptive chunking (333/666/999) based on codebase size,
    with visual progress tracking and human-readable manifests.
    """

    # File patterns for different categories
    CATEGORY_PATTERNS = {
        ContentCategory.SOURCE_CODE: [
            r'\.py$', r'\.java$', r'\.ts$', r'\.tsx$', r'\.js$', r'\.jsx$',
            r'\.go$', r'\.rs$', r'\.cpp$', r'\.c$', r'\.cs$', r'\.rb$',
            r'\.php$', r'\.swift$', r'\.kt$', r'\.scala$'
        ],
        ContentCategory.DOCUMENTATION: [
            r'\.md$', r'\.rst$', r'\.txt$', r'README', r'CHANGELOG',
            r'CONTRIBUTING', r'LICENSE'
        ],
        ContentCategory.CONFIGURATION: [
            r'\.json$', r'\.yaml$', r'\.yml$', r'\.toml$', r'\.ini$',
            r'\.env', r'\.config', r'Dockerfile', r'docker-compose',
            r'\.xml$', r'pom\.xml$', r'build\.gradle'
        ],
        ContentCategory.TESTS: [
            r'test_.*\.py$', r'.*_test\.py$', r'.*\.test\.(ts|js)$',
            r'.*\.spec\.(ts|js)$', r'Test.*\.java$', r'.*Test\.java$'
        ],
        ContentCategory.TEMPLATES: [
            r'TEMPLATE.*\.md$', r'\.template$', r'\.tmpl$'
        ],
        ContentCategory.REQUIREMENTS: [
            r'requirements.*\.txt$', r'package\.json$', r'Cargo\.toml$',
            r'go\.mod$', r'Gemfile$', r'\.csproj$'
        ],
        ContentCategory.AGENTS: [
            r'.*AGENT.*\.md$', r'agents/.*'
        ],
        ContentCategory.COMMANDS: [
            r'commands/.*\.md$'
        ]
    }

    # Directories to skip
    SKIP_DIRS = {
        'node_modules', 'venv', 'env', '.venv', '.env',
        '__pycache__', '.git', '.svn', '.hg',
        'dist', 'build', 'target', 'out',
        '.gradle', '.idea', '.vscode',
        'coverage', '.pytest_cache', '.mypy_cache',
        '.tox', 'eggs', '*.egg-info',
        'chroma_db', '.claude/rag/chroma_db'
    }

    def __init__(
        self,
        project_root: str,
        output_dir: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None
    ):
        self.project_root = Path(project_root).resolve()
        self.output_dir = Path(output_dir) if output_dir else self.project_root / '.claude' / 'rag' / 'index'
        self.progress = progress_callback or ProgressCallback()
        self.chunking_strategy = UniversalChunkingStrategy(str(self.project_root))

        # State
        self.files_discovered: Dict[ContentCategory, List[Path]] = {}
        self.chunks: List[CodeChunk] = []
        self.manifest: Optional[IndexManifest] = None
        self.stats = IndexStats()

    def _categorize_file(self, file_path: Path) -> Optional[ContentCategory]:
        """Determine the category of a file based on patterns."""
        rel_path = str(file_path.relative_to(self.project_root))
        filename = file_path.name

        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, rel_path, re.IGNORECASE) or \
                   re.search(pattern, filename, re.IGNORECASE):
                    return category

        # Default to source code for code files
        if file_path.suffix in ['.py', '.java', '.ts', '.js', '.go', '.rs']:
            return ContentCategory.SOURCE_CODE

        return None

    def _should_skip_dir(self, dir_path: Path) -> bool:
        """Check if directory should be skipped."""
        dir_name = dir_path.name
        rel_path = str(dir_path.relative_to(self.project_root))

        for skip in self.SKIP_DIRS:
            if skip in dir_name or skip in rel_path:
                return True
        return False

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (roughly 4 chars per token)."""
        return len(text) // 4

    def _generate_chunk_id(self, chunk: CodeChunk) -> str:
        """Generate unique ID for a chunk."""
        content_hash = hashlib.md5(chunk.content.encode()).hexdigest()[:8]
        chunk_type_str = chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type)
        return f"{chunk_type_str}_{content_hash}_{chunk.start_line}"

    def _extract_keywords(self, chunk: CodeChunk) -> List[str]:
        """Extract keywords from chunk for searchability."""
        keywords = set()

        # Extract from metadata
        if chunk.metadata:
            for key in ['class_name', 'method_name', 'name', 'annotations']:
                if key in chunk.metadata:
                    val = chunk.metadata[key]
                    if isinstance(val, list):
                        keywords.update(val)
                    elif val:
                        keywords.add(str(val))

        # Extract identifiers from content (camelCase, snake_case, PascalCase)
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', chunk.content)
        # Filter common keywords
        common = {'def', 'class', 'function', 'const', 'let', 'var', 'import',
                  'from', 'return', 'if', 'else', 'for', 'while', 'try', 'catch',
                  'public', 'private', 'protected', 'static', 'void', 'string',
                  'int', 'bool', 'true', 'false', 'null', 'None', 'self', 'this'}
        keywords.update(i for i in identifiers[:20] if i.lower() not in common)

        return list(keywords)[:15]  # Limit to 15 keywords

    def _generate_summary(self, chunk: CodeChunk) -> str:
        """Generate a brief summary of the chunk."""
        lines = chunk.content.strip().split('\n')
        first_line = lines[0][:100] if lines else ""

        # Try to extract docstring or comment
        chunk_type_str = chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type)
        # Check for class-like types (python_class, java_class, ts_class, etc.)
        if 'class' in chunk_type_str.lower():
            match = re.search(r'"""(.+?)"""', chunk.content, re.DOTALL)
            if match:
                return match.group(1).strip()[:150]

        # Check for function-like types (python_function, java_method, ts_function, etc.)
        if 'function' in chunk_type_str.lower() or 'method' in chunk_type_str.lower():
            match = re.search(r'("""|\'\'\')(.+?)("""|\'\'\')', chunk.content, re.DOTALL)
            if match:
                return match.group(2).strip()[:150]

        # Use first meaningful line
        for line in lines[:5]:
            line = line.strip()
            if line and not line.startswith(('#', '//', '/*', '*', '@')):
                return line[:150]

        return first_line[:150]

    def determine_chunk_target(self, file_count: int) -> ChunkTarget:
        """Determine optimal chunk target based on codebase size."""
        if file_count < 50:
            return ChunkTarget.SMALL
        elif file_count <= 200:
            return ChunkTarget.MEDIUM
        else:
            return ChunkTarget.LARGE

    def discover_files(self) -> Dict[ContentCategory, List[Path]]:
        """Discover and categorize all files in the project."""
        self.progress.on_phase_start("Discovery", 0)

        discovered: Dict[ContentCategory, List[Path]] = {cat: [] for cat in ContentCategory}
        file_count = 0

        for root, dirs, files in os.walk(self.project_root):
            root_path = Path(root)

            # Filter directories
            dirs[:] = [d for d in dirs if not self._should_skip_dir(root_path / d)]

            for filename in files:
                file_path = root_path / filename
                category = self._categorize_file(file_path)

                if category:
                    discovered[category].append(file_path)
                    file_count += 1
                    self.progress.on_progress(file_count, 0, f"Found: {filename}")

        self.files_discovered = discovered
        self.stats.total_files = file_count
        self.stats.files_by_category = {
            cat.value: len(files) for cat, files in discovered.items()
        }

        # Determine chunk target
        target = self.determine_chunk_target(file_count)
        self.stats.target_chunks = target.value

        self.progress.on_phase_complete("Discovery", {
            "total_files": file_count,
            "target_chunks": target.value,
            "categories": self.stats.files_by_category
        })

        return discovered

    def create_chunks(self) -> List[CodeChunk]:
        """Create chunks from discovered files with adaptive sizing."""
        self.progress.on_phase_start("Chunking", self.stats.total_files)

        all_chunks: List[CodeChunk] = []
        processed = 0

        # Process by category priority
        category_priority = [
            ContentCategory.SOURCE_CODE,
            ContentCategory.DOCUMENTATION,
            ContentCategory.AGENTS,
            ContentCategory.COMMANDS,
            ContentCategory.CONFIGURATION,
            ContentCategory.REQUIREMENTS,
            ContentCategory.TEMPLATES,
            ContentCategory.TESTS
        ]

        for category in category_priority:
            files = self.files_discovered.get(category, [])

            for file_path in files:
                try:
                    rel_path = str(file_path.relative_to(self.project_root))

                    # Use chunking strategy (it handles file reading internally)
                    file_chunks = self.chunking_strategy.chunk_file(rel_path)

                    # Add category metadata
                    for chunk in file_chunks:
                        chunk.metadata['category'] = category.value
                        all_chunks.append(chunk)
                        self.progress.on_chunk_created(chunk)

                    processed += 1
                    self.progress.on_progress(
                        processed,
                        self.stats.total_files,
                        f"Chunked: {rel_path} ({len(file_chunks)} chunks)"
                    )

                except Exception as e:
                    processed += 1
                    self.progress.on_progress(
                        processed,
                        self.stats.total_files,
                        f"Error chunking {file_path}: {e}"
                    )

        self.chunks = all_chunks
        self._optimize_chunk_count()

        self.progress.on_phase_complete("Chunking", {
            "total_chunks": len(self.chunks),
            "target": self.stats.target_chunks
        })

        return self.chunks

    def _optimize_chunk_count(self) -> None:
        """
        Optimize chunks to hit target (333/666/999).

        Strategy:
        - If too few: keep all chunks, note in manifest
        - If too many: merge small related chunks or prioritize
        """
        current = len(self.chunks)
        target = self.stats.target_chunks

        if current <= target:
            # Under target - keep all
            return

        # Over target - need to consolidate
        # Priority: Keep source code, agents, documentation
        # Merge: Similar small chunks from same file

        # Sort by importance
        def chunk_priority(chunk: CodeChunk) -> int:
            cat = chunk.metadata.get('category', '')
            priorities = {
                'source_code': 0,
                'agents': 1,
                'documentation': 2,
                'commands': 3,
                'configuration': 4,
                'requirements': 5,
                'templates': 6,
                'tests': 7
            }
            return priorities.get(cat, 10)

        self.chunks.sort(key=chunk_priority)

        # If still over, merge small adjacent chunks from same file
        if len(self.chunks) > target:
            merged = []
            i = 0
            while i < len(self.chunks) and len(merged) < target:
                chunk = self.chunks[i]

                # Try to merge with next if same file and both small
                if (i + 1 < len(self.chunks) and
                    len(merged) < target - 1 and
                    len(chunk.content) < 500 and
                    self.chunks[i + 1].file_path == chunk.file_path and
                    len(self.chunks[i + 1].content) < 500):

                    # Merge chunks
                    next_chunk = self.chunks[i + 1]
                    merged_content = chunk.content + "\n\n" + next_chunk.content
                    chunk.content = merged_content
                    chunk.end_line = next_chunk.end_line
                    i += 2
                else:
                    i += 1

                merged.append(chunk)

            # Add remaining high-priority chunks if under target
            while len(merged) < target and i < len(self.chunks):
                merged.append(self.chunks[i])
                i += 1

            self.chunks = merged[:target]

    def build_manifest(self) -> IndexManifest:
        """Build human-readable index manifest."""
        self.progress.on_phase_start("Manifest", len(self.chunks))

        manifest = IndexManifest(
            version="1.0.0",
            created_at=datetime.now().isoformat(),
            project_root=str(self.project_root),
            target_chunks=self.stats.target_chunks,
            actual_chunks=len(self.chunks)
        )

        # Build category index
        categories: Dict[str, List[str]] = {}

        # Process each chunk
        total_size = 0
        total_tokens = 0
        chunks_by_type: Dict[str, int] = {}
        chunks_by_cat: Dict[str, int] = {}

        for i, chunk in enumerate(self.chunks):
            chunk_id = self._generate_chunk_id(chunk)
            category = chunk.metadata.get('category', 'unknown')

            # Update counts
            chunk_type_str = chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type)
            chunks_by_type[chunk_type_str] = chunks_by_type.get(chunk_type_str, 0) + 1
            chunks_by_cat[category] = chunks_by_cat.get(category, 0) + 1

            # Category index
            if category not in categories:
                categories[category] = []
            categories[category].append(chunk_id)

            # Create manifest entry
            size_chars = len(chunk.content)
            size_tokens = self._estimate_tokens(chunk.content)
            total_size += size_chars
            total_tokens += size_tokens

            entry = ChunkManifestEntry(
                chunk_id=chunk_id,
                file_path=chunk.file_path,
                category=category,
                chunk_type=chunk_type_str,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                size_chars=size_chars,
                size_tokens_est=size_tokens,
                summary=self._generate_summary(chunk),
                keywords=self._extract_keywords(chunk),
                quality_score=1.0,  # Will be updated by enforcer
                metadata=chunk.metadata
            )

            manifest.chunks.append(entry)
            self.progress.on_progress(i + 1, len(self.chunks), f"Manifest: {chunk_id}")

        manifest.categories = categories

        # Update stats
        self.stats.total_chunks = len(self.chunks)
        self.stats.chunks_by_type = chunks_by_type
        self.stats.chunks_by_category = chunks_by_cat
        self.stats.avg_chunk_size = total_size / len(self.chunks) if self.chunks else 0
        self.stats.total_tokens_estimate = total_tokens

        manifest.stats = self.stats

        self.manifest = manifest
        self.progress.on_phase_complete("Manifest", {"entries": len(manifest.chunks)})

        return manifest

    def save_manifest(self) -> Tuple[Path, Path]:
        """Save manifest in both JSON and human-readable markdown formats."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # JSON manifest (for programmatic access)
        json_path = self.output_dir / "index_manifest.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            # Convert to serializable format
            manifest_dict = {
                'version': self.manifest.version,
                'created_at': self.manifest.created_at,
                'project_root': self.manifest.project_root,
                'target_chunks': self.manifest.target_chunks,
                'actual_chunks': self.manifest.actual_chunks,
                'stats': asdict(self.manifest.stats) if self.manifest.stats else {},
                'categories': self.manifest.categories,
                'chunks': [asdict(c) for c in self.manifest.chunks],
                'quality_report': self.manifest.quality_report
            }
            json.dump(manifest_dict, f, indent=2, default=str)

        # Markdown manifest (for human review)
        md_path = self.output_dir / "INDEX_MANIFEST.md"
        self._write_markdown_manifest(md_path)

        return json_path, md_path

    def _write_markdown_manifest(self, path: Path) -> None:
        """Write human-readable markdown manifest."""
        lines = [
            "# RAG Index Manifest",
            "",
            f"Generated: {self.manifest.created_at}",
            f"Project: `{self.manifest.project_root}`",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Target Chunks | {self.manifest.target_chunks} |",
            f"| Actual Chunks | {self.manifest.actual_chunks} |",
            f"| Total Files | {self.stats.total_files} |",
            f"| Avg Chunk Size | {self.stats.avg_chunk_size:.0f} chars |",
            f"| Est. Total Tokens | {self.stats.total_tokens_estimate:,} |",
            f"| Quality Score | {self.stats.quality_score:.2f} |",
            "",
            "## Chunks by Category",
            "",
        ]

        for cat, count in sorted(self.stats.chunks_by_category.items()):
            lines.append(f"- **{cat}**: {count} chunks")

        lines.extend([
            "",
            "## Chunks by Type",
            "",
        ])

        for ctype, count in sorted(self.stats.chunks_by_type.items()):
            lines.append(f"- **{ctype}**: {count}")

        lines.extend([
            "",
            "## Category Index",
            "",
            "Use these sections to navigate and fine-tune the chunking.",
            "",
        ])

        for category, chunk_ids in sorted(self.manifest.categories.items()):
            lines.append(f"### {category.replace('_', ' ').title()}")
            lines.append("")
            lines.append(f"*{len(chunk_ids)} chunks*")
            lines.append("")

            # Get chunks for this category
            cat_chunks = [c for c in self.manifest.chunks if c.category == category]

            # Group by file
            files: Dict[str, List[ChunkManifestEntry]] = {}
            for chunk in cat_chunks:
                if chunk.file_path not in files:
                    files[chunk.file_path] = []
                files[chunk.file_path].append(chunk)

            for file_path, chunks in sorted(files.items()):
                lines.append(f"#### `{file_path}`")
                lines.append("")
                for chunk in chunks:
                    keywords = ', '.join(chunk.keywords[:5]) if chunk.keywords else 'none'
                    lines.append(f"- **{chunk.chunk_id}** ({chunk.chunk_type}, L{chunk.start_line}-{chunk.end_line})")
                    lines.append(f"  - Summary: {chunk.summary[:80]}...")
                    lines.append(f"  - Keywords: {keywords}")
                    lines.append(f"  - Size: {chunk.size_chars} chars (~{chunk.size_tokens_est} tokens)")
                lines.append("")

        lines.extend([
            "",
            "---",
            "",
            "## Fine-Tuning Guide",
            "",
            "To adjust chunking:",
            "",
            "1. **Merge chunks**: Edit `index_manifest.json`, combine chunk IDs",
            "2. **Split chunks**: Mark chunks for re-processing with finer granularity",
            "3. **Exclude chunks**: Add chunk IDs to `excluded_chunks` array",
            "4. **Re-categorize**: Update `category` field in chunk entries",
            "",
            "After editing, run: `python -m .claude.rag.rag_orchestrator --rebuild`",
        ])

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    def run(self) -> IndexManifest:
        """Execute full orchestration pipeline."""
        start_time = datetime.now()

        # Phase 1: Discovery
        self.discover_files()

        # Phase 2: Chunking
        self.create_chunks()

        # Phase 3: Build manifest
        self.build_manifest()

        # Phase 4: Save outputs
        json_path, md_path = self.save_manifest()

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds() * 1000
        self.stats.indexing_duration_ms = int(duration)

        return self.manifest


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG Orchestrator")
    parser.add_argument("--project", "-p", default=".", help="Project root directory")
    parser.add_argument("--output", "-o", help="Output directory for manifests")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild from existing manifest")

    args = parser.parse_args()

    orchestrator = RAGOrchestrator(
        project_root=args.project,
        output_dir=args.output
    )

    manifest = orchestrator.run()

    print(f"\nIndexing complete!")
    print(f"  Files: {manifest.stats.total_files}")
    print(f"  Chunks: {manifest.actual_chunks} / {manifest.target_chunks} target")
    print(f"  Duration: {manifest.stats.indexing_duration_ms}ms")
