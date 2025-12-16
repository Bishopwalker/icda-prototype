"""
Index Code Files into ICDA Code RAG System
============================================
Run with: python index_code.py [options]

Options:
    --path PATH     Root directory to index (default: current directory)
    --count         Show current indexed file count
    --delete        Delete all code index data
    --test          Run test searches
    --force         Force reindex without prompting
    --extensions    Comma-separated extensions to index (default: py,js,ts,tsx,jsx,java)

Requires OPENSEARCH_HOST environment variable to be set.
"""

import asyncio
import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env BEFORE importing config
load_dotenv()

from icda.config import Config
from icda.embeddings import EmbeddingClient
from icda.indexes.code_index import CodeIndex

# Create fresh config after dotenv is loaded
cfg = Config()

# Default extensions to index
DEFAULT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".cpp", ".c",
    ".cs", ".rb", ".php", ".swift", ".kt",
    ".scala", ".sh", ".sql", ".md", ".yaml",
    ".yml", ".json", ".html", ".css"
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", ".venv", "venv", "__pycache__",
    ".idea", ".vscode", "dist", "build", ".next", "target",
    "vendor", ".cache", ".pytest_cache", ".mypy_cache",
    "coverage", ".nyc_output", "eggs", ".eggs", "*.egg-info"
}

# Files to skip
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "poetry.lock",
    "Pipfile.lock", "composer.lock", "Cargo.lock"
}


def should_skip_dir(dir_name: str) -> bool:
    """Check if directory should be skipped."""
    return dir_name in SKIP_DIRS or dir_name.startswith(".")


def should_skip_file(filename: str) -> bool:
    """Check if file should be skipped."""
    return filename in SKIP_FILES or filename.startswith(".")


def collect_files(
    root_path: Path,
    extensions: set[str],
    max_files: Optional[int] = None
) -> list[Path]:
    """Recursively collect files to index."""
    files = []

    for item in root_path.rglob("*"):
        if max_files and len(files) >= max_files:
            break

        # Skip directories
        if item.is_dir():
            continue

        # Check if any parent is a skip directory
        skip = False
        for parent in item.relative_to(root_path).parents:
            if should_skip_dir(parent.name):
                skip = True
                break
        if skip:
            continue

        # Check file
        if should_skip_file(item.name):
            continue

        # Check extension
        if item.suffix.lower() in extensions:
            files.append(item)

    return files


async def show_count(code_index: CodeIndex) -> int:
    """Show current indexed file count."""
    try:
        stats = await code_index.get_stats()
        count = stats.get("total_documents", 0)
        print(f"Indexed code chunks: {count:,}")

        # Show by language
        if stats.get("languages"):
            print("\nBy language:")
            for lang, lcount in sorted(stats["languages"].items(), key=lambda x: -x[1]):
                print(f"  {lang}: {lcount}")

        return count
    except Exception as e:
        print(f"Error getting stats: {e}")
        return 0


async def delete_index(code_index: CodeIndex) -> bool:
    """Delete the code index."""
    print("Deleting code index...")
    try:
        success = await code_index.delete_index()
        if success:
            print("Code index deleted.")
        else:
            print("Failed to delete index.")
        return success
    except Exception as e:
        print(f"Error: {e}")
        return False


async def index_files(
    code_index: CodeIndex,
    files: list[Path],
    root_path: Path,
    batch_size: int = 10
) -> dict:
    """Index all files with progress reporting."""
    total = len(files)
    start_time = time.time()
    indexed = 0
    errors = 0
    total_chunks = 0

    print(f"Indexing {total:,} files into OpenSearch...")
    print(f"  Index: {code_index.config.name}")
    print()

    for i, filepath in enumerate(files):
        try:
            # Read file content
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"  ✗ Read error: {filepath.name} - {e}")
                errors += 1
                continue

            # Skip empty files
            if not content.strip():
                continue

            # Get relative path for indexing
            rel_path = str(filepath.relative_to(root_path))

            # Index the file
            success_count, error_count = await code_index.index_file(
                filepath=rel_path,
                content=content,
                chunk_size=400,
                chunk_overlap=50
            )

            if success_count > 0:
                indexed += 1
                total_chunks += success_count
            else:
                errors += 1

            # Progress report every 10 files
            if (i + 1) % 10 == 0 or i == total - 1:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (total - i - 1) / rate if rate > 0 else 0
                print(f"  [{i+1}/{total}] {indexed} indexed, {errors} errors - {rate:.1f} files/sec - ETA: {eta:.0f}s")

        except Exception as e:
            print(f"  ✗ Error: {filepath.name} - {e}")
            errors += 1

    elapsed = time.time() - start_time
    print()
    print(f"Indexing complete!")
    print(f"  Files indexed: {indexed:,}")
    print(f"  Total chunks: {total_chunks:,}")
    print(f"  Errors: {errors:,}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Rate: {indexed/elapsed:.1f} files/sec")

    return {"indexed": indexed, "chunks": total_chunks, "errors": errors}


async def test_search(code_index: CodeIndex):
    """Run test searches to verify indexing."""
    print("\nTesting code search...")

    test_queries = [
        ("async function", None),
        ("class Config", "python"),
        ("import React", "typescript"),
        ("def __init__", "python"),
        ("router endpoint", None),
    ]

    for query, language in test_queries:
        lang_str = f" (lang: {language})" if language else ""
        print(f"\nQuery: '{query}'{lang_str}")

        results = await code_index.search_code(
            query=query,
            language=language,
            k=3
        )

        if results:
            print(f"  Found {len(results)} results:")
            for r in results[:3]:
                doc = r.document
                print(f"    - {doc.get('filename', 'unknown')} ({doc.get('language', '?')}) "
                      f"[{doc.get('chunk_type', 'mixed')}] score={r.score:.3f}")
                # Show snippet
                text = doc.get("text", "")[:100].replace("\n", " ")
                print(f"      {text}...")
        else:
            print("  No results found")


async def main():
    parser = argparse.ArgumentParser(description="Index code files into ICDA Code RAG")
    parser.add_argument("--path", type=str, default=".", help="Root directory to index")
    parser.add_argument("--count", action="store_true", help="Show current index count")
    parser.add_argument("--delete", action="store_true", help="Delete the code index")
    parser.add_argument("--test", action="store_true", help="Run test searches")
    parser.add_argument("--force", action="store_true", help="Force reindex without prompting")
    parser.add_argument("--extensions", type=str, help="Comma-separated extensions (e.g., py,js,ts)")
    parser.add_argument("--limit", type=int, help="Max files to index (for testing)")
    args = parser.parse_args()

    # Check OpenSearch config
    if not cfg.opensearch_host:
        print("ERROR: OPENSEARCH_HOST environment variable not set.")
        print()
        print("Set it in your .env file or environment:")
        print("  OPENSEARCH_HOST=http://localhost:9200")
        sys.exit(1)

    print(f"OpenSearch host: {cfg.opensearch_host}")
    print(f"AWS region: {cfg.aws_region}")
    print()

    # Initialize components
    embedder = EmbeddingClient(cfg.aws_region, cfg.titan_embed_model, cfg.embed_dimensions)

    # Create OpenSearch client
    from opensearchpy import AsyncOpenSearch

    os_host = cfg.opensearch_host.replace("http://", "").replace("https://", "")
    host, port = os_host.split(":") if ":" in os_host else (os_host, "9200")

    client = AsyncOpenSearch(
        hosts=[{"host": host, "port": int(port)}],
        use_ssl=cfg.opensearch_host.startswith("https"),
        verify_certs=False,
        ssl_show_warn=False,
    )

    # Create code index
    code_index = CodeIndex(client, embedder, cfg.index_code)
    await code_index.ensure_index()

    print(f"Connected to OpenSearch")
    print()

    # Handle commands
    if args.count:
        await show_count(code_index)

    elif args.delete:
        await delete_index(code_index)

    elif args.test:
        count = await show_count(code_index)
        if count == 0:
            print("No code indexed. Run without --test to index first.")
        else:
            await test_search(code_index)

    else:
        # Index code files
        root_path = Path(args.path).resolve()

        if not root_path.exists():
            print(f"ERROR: Path does not exist: {root_path}")
            sys.exit(1)

        print(f"Scanning: {root_path}")

        # Parse extensions
        if args.extensions:
            extensions = {f".{e.strip().lstrip('.')}" for e in args.extensions.split(",")}
        else:
            extensions = DEFAULT_EXTENSIONS

        print(f"Extensions: {', '.join(sorted(extensions))}")

        # Collect files
        files = collect_files(root_path, extensions, args.limit)
        print(f"Found {len(files):,} files to index")

        if not files:
            print("No files to index.")
            await client.close()
            return

        # Check if already indexed
        current_count = await show_count(code_index)

        if current_count > 0 and not args.force:
            try:
                response = input("\nCode index has existing data. Clear and reindex? (y/N): ").strip().lower()
                if response == 'y':
                    await delete_index(code_index)
                    await code_index.ensure_index()
                else:
                    print("Aborted.")
                    await client.close()
                    return
            except EOFError:
                print("Non-interactive mode. Use --force to clear and reindex.")
                await client.close()
                return
        elif current_count > 0 and args.force:
            print("Force flag set - clearing existing index...")
            await delete_index(code_index)
            await code_index.ensure_index()

        # Index files
        await index_files(code_index, files, root_path)

        # Run quick test
        print("\n" + "=" * 60)
        await test_search(code_index)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
