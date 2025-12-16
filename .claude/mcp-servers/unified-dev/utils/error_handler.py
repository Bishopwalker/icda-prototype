"""
Robust Error Handling
Learned from codex server patterns - structured error responses
"""

import logging
import traceback
from typing import Dict, Any, Optional
from functools import wraps
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Structured error response"""
    success: bool = False
    error: str
    error_type: str
    details: Optional[Dict[str, Any]] = None
    traceback: Optional[str] = None


def handle_tool_error(func):
    """
    Decorator for robust tool error handling

    Wraps tool functions to catch exceptions and return structured error responses
    Prevents server crashes from individual tool failures

    Usage:
        @handle_tool_error
        async def my_tool(arg1, arg2):
            # tool implementation
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return {
                'success': True,
                'data': result
            }
        except ValueError as e:
            logger.error(f"Validation error in {func.__name__}: {str(e)}")
            return ErrorResponse(
                error=str(e),
                error_type='ValidationError',
                details={'function': func.__name__}
            ).dict()
        except FileNotFoundError as e:
            logger.error(f"File not found in {func.__name__}: {str(e)}")
            return ErrorResponse(
                error=str(e),
                error_type='FileNotFoundError',
                details={'function': func.__name__}
            ).dict()
        except ImportError as e:
            logger.error(f"Import error in {func.__name__}: {str(e)}")
            return ErrorResponse(
                error=f"Missing dependency: {str(e)}",
                error_type='ImportError',
                details={
                    'function': func.__name__,
                    'hint': 'Run: pip install -r requirements.txt'
                }
            ).dict()
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            return ErrorResponse(
                error=str(e),
                error_type=type(e).__name__,
                details={'function': func.__name__},
                traceback=traceback.format_exc()
            ).dict()

    return wrapper


def format_error_response(error: Exception, context: str = "") -> Dict:
    """
    Format exception as structured error response

    Args:
        error: Exception that occurred
        context: Additional context about where/when error occurred

    Returns:
        Structured error dictionary
    """
    return ErrorResponse(
        error=str(error),
        error_type=type(error).__name__,
        details={'context': context} if context else None,
        traceback=traceback.format_exc()
    ).dict()


class ToolExecutionError(Exception):
    """Custom exception for tool execution failures"""
    pass


class ModelUnavailableError(Exception):
    """Exception when requested model is unavailable"""
    pass


class RAGNotInitializedError(Exception):
    """Exception when RAG system not properly initialized"""
    pass


class MemoryServiceError(Exception):
    """Exception for memory service operations"""
    pass
