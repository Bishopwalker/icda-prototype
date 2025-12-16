"""
Memory Tools - Session Persistence with Mem0
Integrates with Agent 3's MemoryService from .github/rag/
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from ..utils.error_handler import handle_tool_error, MemoryServiceError
from ..utils.validation import (
    SaveMemoryInput,
    SearchMemoryInput,
    GetSessionMemoryInput,
    EnhanceQueryInput
)

# Global memory service instance
_memory_service = None
_memory_config = None


def initialize_memory(project_root_path: str):
    """
    Initialize Memory service from Agent 3's work

    Args:
        project_root_path: Path to project root
    """
    global _memory_service, _memory_config

    try:
        # Import from RAG system - add .github directory to path
        claude_path = Path(project_root_path) / '.github'
        sys.path.insert(0, str(claude_path))
        from rag import load_config, MemoryService

        _memory_config = load_config()
        _memory_service = MemoryService(_memory_config.get_mem0_config())

    except Exception as e:
        raise MemoryServiceError(f"Failed to initialize Memory service: {str(e)}")


@handle_tool_error
async def save_memory(
    session_id: str,
    content: str,
    memory_type: str = "session",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Save persistent memory for later retrieval

    Args:
        session_id: Session identifier
        content: Content to save
        memory_type: Type of memory (session, code_context, decision, learning, bug_report)
        metadata: Optional metadata

    Returns:
        {
            "memory_id": str,
            "saved": bool,
            "session_id": str,
            "memory_type": str
        }
    """
    # Validate input
    validated = SaveMemoryInput(
        session_id=session_id,
        content=content,
        memory_type=memory_type,
        metadata=metadata
    )

    if _memory_service is None:
        raise MemoryServiceError("Memory service not initialized. Call initialize_memory() first.")

    # Save memory based on type
    if validated.memory_type == "session":
        memory_id = _memory_service.save_session_memory(
            session_id=validated.session_id,
            content=validated.content,
            metadata=validated.metadata or {}
        )
    elif validated.memory_type == "code_context":
        # Extract file_path from metadata if present
        file_path = (validated.metadata or {}).get('file_path', 'unknown')
        memory_id = _memory_service.save_code_context(
            file_path=file_path,
            context=validated.content
        )
    elif validated.memory_type == "decision":
        memory_id = _memory_service.save_decision(
            decision=validated.content,
            rationale=(validated.metadata or {}).get('rationale', ''),
            outcome=(validated.metadata or {}).get('outcome')
        )
    else:
        # Generic save for other types
        memory_id = _memory_service.save_session_memory(
            session_id=validated.session_id,
            content=validated.content,
            metadata={**(validated.metadata or {}), 'type': validated.memory_type}
        )

    return {
        "memory_id": memory_id,
        "saved": True,
        "session_id": validated.session_id,
        "memory_type": validated.memory_type
    }


@handle_tool_error
async def search_memory(
    query: str,
    session_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    n_results: int = 5
) -> List[Dict[str, Any]]:
    """
    Search across all saved memories

    Args:
        query: Search query
        session_id: Optional filter by session
        memory_type: Optional filter by type
        n_results: Number of results

    Returns:
        List of matching memories
    """
    # Validate input
    validated = SearchMemoryInput(
        query=query,
        session_id=session_id,
        memory_type=memory_type,
        n_results=n_results
    )

    if _memory_service is None:
        raise MemoryServiceError("Memory service not initialized.")

    # Search with optional filters
    filters = {}
    if validated.session_id:
        filters['session_id'] = validated.session_id
    if validated.memory_type:
        filters['type'] = validated.memory_type

    results = _memory_service.search_memory(
        query=validated.query,
        filters=filters if filters else None
    )

    # Limit results
    return results[:validated.n_results]


@handle_tool_error
async def get_session_memory(session_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all memories for a specific session

    Args:
        session_id: Session identifier

    Returns:
        Chronological list of all memories in session
    """
    # Validate input
    validated = GetSessionMemoryInput(session_id=session_id)

    if _memory_service is None:
        raise MemoryServiceError("Memory service not initialized.")

    memories = _memory_service.get_session_memory(validated.session_id)

    return memories


@handle_tool_error
async def enhance_query(query: str, session_id: str) -> str:
    """
    Enhance a RAG query with session context

    Uses memory to add relevant context to improve search results.

    Example:
        Input: "connection pool"
        Session Context: "Working on database connection timeout issues"
        Output: "database connection timeout connection pool management"

    Args:
        query: Original query
        session_id: Session identifier for context

    Returns:
        Enhanced query string
    """
    # Validate input
    validated = EnhanceQueryInput(query=query, session_id=session_id)

    if _memory_service is None:
        raise MemoryServiceError("Memory service not initialized.")

    enhanced = _memory_service.enhance_rag_query(
        query=validated.query,
        session_id=validated.session_id
    )

    return enhanced
