"""
RAG Tools - Code Search and Analysis
Integrates with Agent 3's RAG system from .claude/rag/
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path for imports
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from ..utils.error_handler import handle_tool_error, RAGNotInitializedError
from ..utils.validation import SearchCodeInput, AnalyzeErrorInput

# Global RAG pipeline instance
_rag_pipeline = None
_rag_config = None


def initialize_rag(project_root_path: str):
    """
    Initialize RAG system from Agent 3's work

    Args:
        project_root_path: Path to project root
    """
    global _rag_pipeline, _rag_config

    try:
        # Import from RAG system - add .claude directory to path
        claude_path = Path(project_root_path) / '.claude'
        sys.path.insert(0, str(claude_path))
        from rag import load_config, CloudRAGPipeline

        _rag_config = load_config()
        _rag_pipeline = CloudRAGPipeline(
            project_root=project_root_path,
            provider=_rag_config.vector_provider,
            **_rag_config.get_vector_config()
        )

        # Index project if not already indexed
        _rag_pipeline.index_project(force_reindex=False)

    except Exception as e:
        raise RAGNotInitializedError(f"Failed to initialize RAG: {str(e)}")


@handle_tool_error
async def search_code(query: str, n_results: int = 5) -> Dict[str, Any]:
    """
    Search the codebase using hybrid semantic + keyword search

    Args:
        query: Search query (e.g., "audio buffer management")
        n_results: Number of results to return (1-20)

    Returns:
        {
            "query": str,
            "results": [
                {
                    "file_path": str,
                    "content": str,
                    "scores": {...},
                    "metadata": {...}
                }
            ]
        }
    """
    # Validate input
    validated = SearchCodeInput(query=query, n_results=n_results)

    if _rag_pipeline is None:
        raise RAGNotInitializedError("RAG system not initialized. Call initialize_rag() first.")

    # Perform hybrid search
    results = _rag_pipeline.query(validated.query, validated.n_results)

    return {
        "query": validated.query,
        "n_results": len(results.get('results', [])),
        "results": results.get('results', [])
    }


@handle_tool_error
async def analyze_error(stack_trace: str, context_query: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze stack trace and find relevant code context

    Uses RAG to match stack frames to code chunks and provide context.
    Optionally enhances with semantic search if context_query provided.

    Args:
        stack_trace: Stack trace text to analyze
        context_query: Optional additional search context

    Returns:
        {
            "frames": [list of stack frames],
            "matches": [code chunks matching frames],
            "suggestions": [helpful suggestions]
        }
    """
    # Validate input
    validated = AnalyzeErrorInput(stack_trace=stack_trace, context_query=context_query)

    if _rag_pipeline is None:
        raise RAGNotInitializedError("RAG system not initialized.")

    # Parse stack trace to extract file paths and line numbers
    frames = _parse_stack_trace(validated.stack_trace)

    # Find code chunks matching error locations
    matches = []
    for frame in frames:
        file_path = frame.get('file_path')
        if file_path:
            # Search for code in this file
            query = f"file:{file_path}"
            if context_query:
                query += f" {context_query}"

            results = _rag_pipeline.query(query, n_results=2)
            if results.get('results'):
                matches.extend(results['results'])

    return {
        "frames": frames,
        "matches": matches[:5],  # Top 5 matches
        "suggestions": [
            "Check import statements and module paths",
            "Verify file exists at expected location",
            "Review recent changes to affected files",
            "Check for circular dependencies"
        ]
    }


@handle_tool_error
async def get_code_stats() -> Dict[str, Any]:
    """
    Get statistics about the indexed codebase

    Returns:
        {
            "total_chunks": int,
            "vector_provider": str,
            "indexed": bool,
            ...
        }
    """
    if _rag_pipeline is None:
        raise RAGNotInitializedError("RAG system not initialized.")

    stats = _rag_pipeline.vector_db.get_stats()

    return {
        "total_chunks": stats.get('total_documents', 0),
        "vector_provider": stats.get('provider', 'unknown'),
        "indexed": stats.get('total_documents', 0) > 0,
        "config": {
            "vector_provider": str(_rag_config.vector_provider) if _rag_config else "unknown",
            "project_root": _rag_config.project_root if _rag_config else "unknown"
        }
    }


def _parse_stack_trace(stack_trace: str) -> List[Dict[str, Any]]:
    """
    Parse stack trace to extract frames

    Args:
        stack_trace: Stack trace text

    Returns:
        List of frames with file_path, line, function, etc.
    """
    frames = []
    lines = stack_trace.split('\n')

    for line in lines:
        # Simple parsing - look for common patterns
        # Python: File "path/to/file.py", line 123, in function_name
        # TypeScript: at function_name (path/to/file.ts:123:45)

        if 'File "' in line and 'line ' in line:
            # Python stack frame
            try:
                parts = line.split('"')
                file_path = parts[1] if len(parts) > 1 else ""
                line_num_part = line.split('line ')[1].split(',')[0] if 'line ' in line else "0"
                line_num = int(line_num_part)
                func_name = line.split('in ')[1].strip() if 'in ' in line else "unknown"

                frames.append({
                    "file_path": file_path,
                    "line": line_num,
                    "function": func_name,
                    "language": "python"
                })
            except:
                pass

        elif ' at ' in line and '(' in line and ')' in line:
            # TypeScript/JavaScript stack frame
            try:
                func_name = line.split(' at ')[1].split('(')[0].strip() if ' at ' in line else "unknown"
                location = line.split('(')[1].split(')')[0] if '(' in line else ""
                if ':' in location:
                    parts = location.rsplit(':', 2)
                    file_path = parts[0]
                    line_num = int(parts[1]) if len(parts) > 1 else 0

                    frames.append({
                        "file_path": file_path,
                        "line": line_num,
                        "function": func_name,
                        "language": "typescript"
                    })
            except:
                pass

    return frames
