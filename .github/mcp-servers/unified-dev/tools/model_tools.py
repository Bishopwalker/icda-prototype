"""
Model Tools - Multi-Model Execution
Allows seamless switching between Claude, Codex, and custom models
"""

from typing import Dict, Any, Optional
from ..utils.error_handler import handle_tool_error, ModelUnavailableError
from ..utils.validation import ExecuteWithModelInput, SwitchModelInput

# Global model manager instance
_model_manager = None


def initialize_models(config: dict):
    """
    Initialize model manager with configuration

    Args:
        config: Models configuration from config.json
    """
    global _model_manager

    from ..models import ModelManager
    _model_manager = ModelManager(config)


@handle_tool_error
async def execute_with_model(
    task: str,
    model_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a task using specified model (or default)

    Args:
        task: Task description or prompt
        model_name: "claude", "codex", "custom", or None (use default)
        context: Optional context (RAG results, memory, etc.)

    Returns:
        {
            "model_used": str,
            "result": str,
            "usage": {...}
        }
    """
    # Validate input
    validated = ExecuteWithModelInput(
        task=task,
        model_name=model_name,
        context=context
    )

    if _model_manager is None:
        raise ModelUnavailableError("Model manager not initialized. Call initialize_models() first.")

    # Get model (uses default if model_name is None)
    try:
        model = _model_manager.get_model(validated.model_name)
    except ValueError as e:
        raise ModelUnavailableError(str(e))

    # Prepare prompt with context if provided
    prompt = validated.task
    if validated.context:
        # Add context to prompt
        context_str = "\n\n".join([
            f"**{key}**: {value}"
            for key, value in validated.context.items()
        ])
        prompt = f"{context_str}\n\n{validated.task}"

    # Execute with model
    result = await model.generate(prompt)

    return {
        "model_used": model.get_name(),
        "result": result,
        "usage": {
            "model": model.config.model,
            "max_tokens": model.config.max_tokens,
            "temperature": model.config.temperature
        }
    }


@handle_tool_error
async def switch_model(model_name: str) -> Dict[str, Any]:
    """
    Switch the default model for subsequent operations

    Args:
        model_name: Model to switch to ("claude", "codex", "custom")

    Returns:
        {
            "previous_model": str,
            "new_model": str,
            "switched": bool
        }
    """
    # Validate input
    validated = SwitchModelInput(model_name=model_name)

    if _model_manager is None:
        raise ModelUnavailableError("Model manager not initialized.")

    previous = _model_manager.current_model_name

    try:
        _model_manager.switch_model(validated.model_name)
        return {
            "previous_model": previous,
            "new_model": validated.model_name,
            "switched": True
        }
    except ValueError as e:
        raise ModelUnavailableError(str(e))


@handle_tool_error
async def get_model_status() -> Dict[str, Any]:
    """
    Get status of all configured models

    Returns:
        {
            "current_model": str,
            "models": {
                "claude": {"available": bool, "name": str, ...},
                "codex": {"available": bool, "name": str, ...},
                "custom": {"available": bool, "name": str, ...}
            }
        }
    """
    if _model_manager is None:
        raise ModelUnavailableError("Model manager not initialized.")

    status = _model_manager.get_status()

    return status
