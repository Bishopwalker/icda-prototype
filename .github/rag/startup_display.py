#!/usr/bin/env python3
"""
RAG Startup Display - Shows index stats and Context7 status on app start

Displays:
- Total indexed documents (code chunks)
- Project type detected
- Context7 integration status
- Cache statistics
- Last index timestamp
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def get_rag_stats(project_root: str) -> Dict[str, Any]:
    """Get RAG system statistics"""
    root = Path(project_root)
    stats = {
        "initialized": False,
        "total_documents": 0,
        "project_type": "unknown",
        "last_indexed": None,
        "vector_provider": "ChromaDB (Local)",
        "conventions_analyzed": False
    }

    # Check bootstrap status
    status_file = root / ".github" / "BOOTSTRAP_STATUS.json"
    if status_file.exists():
        try:
            with open(status_file, 'r') as f:
                bootstrap_status = json.load(f)
            stats["initialized"] = bootstrap_status.get("initialized", False)
            stats["project_type"] = bootstrap_status.get("project_type", "unknown")
            stats["conventions_analyzed"] = bootstrap_status.get("conventions_analyzed", False)
            stats["last_indexed"] = bootstrap_status.get("timestamp")
        except Exception:
            pass

    # Get actual document count from ChromaDB
    chroma_dir = root / ".github" / "rag" / "chroma_db"
    if chroma_dir.exists():
        try:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=str(chroma_dir),
                settings=Settings(anonymized_telemetry=False)
            )

            # Try to get the collection
            try:
                collection = client.get_collection("code_chunks")
                stats["total_documents"] = collection.count()
            except Exception:
                # Collection might not exist yet
                pass
        except ImportError:
            # ChromaDB not installed
            pass

    return stats


def get_context7_stats(project_root: str) -> Dict[str, Any]:
    """Get Context7 integration statistics"""
    root = Path(project_root)
    stats = {
        "enabled": False,
        "cache_entries": 0,
        "mcp_configured": False
    }

    # Check if MCP is configured
    mcp_file = root / ".mcp.json"
    if mcp_file.exists():
        try:
            with open(mcp_file, 'r') as f:
                mcp_config = json.load(f)
            if "context7" in mcp_config.get("mcpServers", {}):
                stats["enabled"] = True
                stats["mcp_configured"] = True
        except Exception:
            pass

    # Check cache
    cache_file = root / ".github" / "rag" / "context7_cache" / "cache.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cache = json.load(f)
            stats["cache_entries"] = len(cache)
        except Exception:
            pass

    return stats


def get_file_counts(project_root: str) -> Dict[str, int]:
    """Count source files by type"""
    root = Path(project_root)
    counts = {
        "python": 0,
        "java": 0,
        "javascript": 0,
        "typescript": 0,
        "go": 0,
        "rust": 0,
        "other": 0
    }

    extensions = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust"
    }

    skip_dirs = {"node_modules", "venv", ".venv", ".git", "build", "dist", "__pycache__", "target"}

    for file in root.rglob("*"):
        if file.is_file():
            # Skip ignored directories
            if any(skip in file.parts for skip in skip_dirs):
                continue

            ext = file.suffix.lower()
            if ext in extensions:
                counts[extensions[ext]] += 1
            elif ext in [".md", ".json", ".yaml", ".yml", ".toml"]:
                counts["other"] += 1

    return counts


def display_startup_banner(project_root: str, use_colors: bool = True):
    """Display the startup banner with RAG statistics"""
    c = Colors if use_colors else type('NoColors', (), {attr: '' for attr in dir(Colors) if not attr.startswith('_')})()

    rag_stats = get_rag_stats(project_root)
    c7_stats = get_context7_stats(project_root)
    file_counts = get_file_counts(project_root)

    # Calculate totals
    total_source_files = sum(v for k, v in file_counts.items() if k != "other")
    total_all_files = sum(file_counts.values())

    # Build the display
    print()
    print(f"{c.BOLD}{c.CYAN}+{'=' * 62}+{c.ENDC}")
    print(f"{c.BOLD}{c.CYAN}|     UNIVERSAL CONTEXT TEMPLATE - RAG System Status           |{c.ENDC}")
    print(f"{c.BOLD}{c.CYAN}+{'=' * 62}+{c.ENDC}")
    print()

    # RAG Status Section
    status_icon = "[OK]" if rag_stats["initialized"] else "[!]"
    status_text = "Initialized" if rag_stats["initialized"] else "Not Initialized"

    print(f"{c.BOLD}[*] RAG Index Status:{c.ENDC}")
    print(f"   {status_icon} Status: {c.GREEN if rag_stats['initialized'] else c.YELLOW}{status_text}{c.ENDC}")
    print(f"   [#] Indexed Chunks: {c.BOLD}{rag_stats['total_documents']:,}{c.ENDC}")
    print(f"   [>] Project Type: {c.CYAN}{rag_stats['project_type']}{c.ENDC}")
    print(f"   [>] Vector DB: {rag_stats['vector_provider']}")

    if rag_stats["last_indexed"]:
        print(f"   [>] Last Indexed: {rag_stats['last_indexed']}")
    print()

    # File Counts Section
    print(f"{c.BOLD}[*] Source Files Detected:{c.ENDC}")
    file_display = []
    if file_counts["python"] > 0:
        file_display.append(f"Python: {file_counts['python']}")
    if file_counts["java"] > 0:
        file_display.append(f"Java: {file_counts['java']}")
    if file_counts["javascript"] > 0:
        file_display.append(f"JS: {file_counts['javascript']}")
    if file_counts["typescript"] > 0:
        file_display.append(f"TS: {file_counts['typescript']}")
    if file_counts["go"] > 0:
        file_display.append(f"Go: {file_counts['go']}")
    if file_counts["rust"] > 0:
        file_display.append(f"Rust: {file_counts['rust']}")

    if file_display:
        print(f"   {' | '.join(file_display)}")
    else:
        print(f"   {c.DIM}No source files detected{c.ENDC}")

    print(f"   {c.DIM}Total: {total_source_files} source files, {total_all_files} total files{c.ENDC}")
    print()

    # Context7 Section
    print(f"{c.BOLD}[*] Context7 Integration:{c.ENDC}")
    c7_icon = "[OK]" if c7_stats["enabled"] else "[X]"
    c7_status = "Enabled" if c7_stats["enabled"] else "Disabled"
    print(f"   {c7_icon} Status: {c.GREEN if c7_stats['enabled'] else c.RED}{c7_status}{c.ENDC}")

    if c7_stats["enabled"]:
        print(f"   [>] Cached Docs: {c7_stats['cache_entries']} entries")
        print(f"   {c.DIM}Tip: Add 'use context7' to queries for live documentation{c.ENDC}")
    else:
        print(f"   {c.YELLOW}Run: Add context7 to .mcp.json for auto-documentation{c.ENDC}")
    print()

    # Quick Actions
    print(f"{c.BOLD}[*] Quick Actions:{c.ENDC}")
    if not rag_stats["initialized"]:
        print(f"   {c.YELLOW}> Run /context-init to initialize RAG system{c.ENDC}")
    else:
        print(f"   > /context-init - Refresh context")
        print(f"   > python .github/rag/bootstrap.py --force - Re-index codebase")
        print(f"   > python .github/rag/adaptive_rag.py --conventions - Analyze conventions")
    print()

    print(f"{c.DIM}{'-' * 64}{c.ENDC}")
    print()


def get_startup_json(project_root: str) -> Dict[str, Any]:
    """Get startup information as JSON (for programmatic use)"""
    return {
        "rag": get_rag_stats(project_root),
        "context7": get_context7_stats(project_root),
        "files": get_file_counts(project_root),
        "timestamp": datetime.now().isoformat()
    }


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG Startup Display")
    parser.add_argument(
        "--project-root", "-p",
        default=os.getcwd(),
        help="Project root directory"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    args = parser.parse_args()

    if args.json:
        print(json.dumps(get_startup_json(args.project_root), indent=2))
    else:
        display_startup_banner(args.project_root, use_colors=not args.no_color)


if __name__ == "__main__":
    main()
