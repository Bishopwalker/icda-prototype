"""
Input Validation with Pydantic
Type-safe validation for all MCP tool inputs (Python equivalent of Zod)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List


class SearchCodeInput(BaseModel):
    """Input validation for search_code tool"""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    n_results: int = Field(5, ge=1, le=20, description="Number of results (1-20)")

    @validator('query')
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace')
        return v.strip()


class AnalyzeErrorInput(BaseModel):
    """Input validation for analyze_error tool"""
    stack_trace: str = Field(..., min_length=10, description="Stack trace to analyze")
    context_query: Optional[str] = Field(None, max_length=200, description="Optional context query")


class SaveMemoryInput(BaseModel):
    """Input validation for save_memory tool"""
    session_id: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=10000)
    memory_type: str = Field("session", description="Memory type")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    @validator('memory_type')
    def valid_memory_type(cls, v):
        valid_types = ['session', 'code_context', 'decision', 'learning', 'bug_report']
        if v not in valid_types:
            raise ValueError(f'Memory type must be one of: {", ".join(valid_types)}')
        return v


class SearchMemoryInput(BaseModel):
    """Input validation for search_memory tool"""
    query: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = Field(None, max_length=100)
    memory_type: Optional[str] = Field(None, max_length=50)
    n_results: int = Field(5, ge=1, le=20)


class GetSessionMemoryInput(BaseModel):
    """Input validation for get_session_memory tool"""
    session_id: str = Field(..., min_length=1, max_length=100)


class EnhanceQueryInput(BaseModel):
    """Input validation for enhance_query tool"""
    query: str = Field(..., min_length=1, max_length=500)
    session_id: str = Field(..., min_length=1, max_length=100)


class ExecuteWithModelInput(BaseModel):
    """Input validation for execute_with_model tool"""
    task: str = Field(..., min_length=1, max_length=5000, description="Task to execute")
    model_name: Optional[str] = Field(None, description="Model to use (claude, codex, custom)")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

    @validator('model_name')
    def valid_model_name(cls, v):
        if v is not None:
            valid_models = ['claude', 'codex', 'custom']
            if v not in valid_models:
                raise ValueError(f'Model must be one of: {", ".join(valid_models)}')
        return v


class SwitchModelInput(BaseModel):
    """Input validation for switch_model tool"""
    model_name: str = Field(..., description="Model to switch to")

    @validator('model_name')
    def valid_model_name(cls, v):
        valid_models = ['claude', 'codex', 'custom']
        if v not in valid_models:
            raise ValueError(f'Model must be one of: {", ".join(valid_models)}')
        return v


def validate_input(input_class: type[BaseModel], data: Dict[str, Any]):
    """
    Validate input data against Pydantic model

    Args:
        input_class: Pydantic model class for validation
        data: Input data to validate

    Returns:
        Validated input instance

    Raises:
        ValueError: If validation fails with detailed error message
    """
    try:
        return input_class(**data)
    except Exception as e:
        raise ValueError(f"Input validation failed: {str(e)}")
