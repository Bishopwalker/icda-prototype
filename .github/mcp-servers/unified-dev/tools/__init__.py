"""
MCP Tools for EBL Unified Server

Three categories of tools:
- RAG Tools: Code search and analysis
- Memory Tools: Session persistence
- Model Tools: Multi-model interaction
"""

from .rag_tools import search_code, analyze_error, get_code_stats
from .memory_tools import save_memory, search_memory, get_session_memory, enhance_query
from .model_tools import execute_with_model, switch_model, get_model_status

__all__ = [
    # RAG Tools
    'search_code',
    'analyze_error',
    'get_code_stats',
    # Memory Tools
    'save_memory',
    'search_memory',
    'get_session_memory',
    'enhance_query',
    # Model Tools
    'execute_with_model',
    'switch_model',
    'get_model_status',
]
