"""
Model Abstraction Layer for EBL Unified MCP Server
Supports Claude, Codex, and custom model providers
"""

from .base import BaseModel, ModelConfig
from .claude import ClaudeModel
from .codex import CodexModel
from .custom import CustomModel

__all__ = [
    'BaseModel',
    'ModelConfig',
    'ClaudeModel',
    'CodexModel',
    'CustomModel',
    'ModelManager'
]


class ModelManager:
    """
    Manages multiple model instances and handles fallback logic
    """

    def __init__(self, config: dict):
        """
        Initialize model manager with configuration

        Args:
            config: Models configuration from config.json
        """
        self.config = config
        self.models = {}
        self.current_model_name = config.get('primary', 'claude')
        self._initialize_models()

    def _initialize_models(self):
        """Initialize all configured models"""
        # Claude model
        if 'claude' in self.config:
            self.models['claude'] = ClaudeModel(self.config['claude'])

        # Codex/OpenAI model
        if 'codex' in self.config:
            self.models['codex'] = CodexModel(self.config['codex'])

        # Custom model
        if 'custom' in self.config:
            self.models['custom'] = CustomModel(self.config['custom'])

    def get_model(self, model_name: str = None) -> BaseModel:
        """
        Get model instance by name

        Args:
            model_name: Name of model ('claude', 'codex', 'custom') or None for current

        Returns:
            BaseModel instance

        Raises:
            ValueError: If model not found or unavailable
        """
        if model_name is None:
            model_name = self.current_model_name

        if model_name not in self.models:
            raise ValueError(f"Model '{model_name}' not configured")

        model = self.models[model_name]

        if not model.is_available():
            # Try fallback chain
            fallback_chain = self.config.get('fallback', [])
            for fallback_name in fallback_chain:
                if fallback_name in self.models:
                    fallback_model = self.models[fallback_name]
                    if fallback_model.is_available():
                        return fallback_model

            raise ValueError(f"Model '{model_name}' unavailable and no fallback models available")

        return model

    def switch_model(self, model_name: str):
        """
        Switch the current default model

        Args:
            model_name: Name of model to switch to

        Raises:
            ValueError: If model not found or unavailable
        """
        if model_name not in self.models:
            raise ValueError(f"Model '{model_name}' not configured")

        if not self.models[model_name].is_available():
            raise ValueError(f"Model '{model_name}' is not available")

        self.current_model_name = model_name

    def get_status(self) -> dict:
        """
        Get status of all models

        Returns:
            Dictionary with model availability and current model
        """
        status = {
            'current_model': self.current_model_name,
            'models': {}
        }

        for name, model in self.models.items():
            status['models'][name] = {
                'available': model.is_available(),
                'name': model.get_name(),
                'config': model.config.__dict__ if hasattr(model, 'config') else {}
            }

        return status
