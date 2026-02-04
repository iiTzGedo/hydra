"""AI/LLM configuration and provider management service.

Terminology:
- LLMProvider: One of the 4 supported provider types (Anthropic, OpenAI, Ollama, OpenRouter)
- LLMModel: A model available from a provider (fetched dynamically)
- LLMConfig: User's saved configuration (provider + model + API key) for chat sessions
"""

from hydra.api.v1.services.ai.service import AIService, LLMConfigNotFoundError

__all__ = ["AIService", "LLMConfigNotFoundError"]
