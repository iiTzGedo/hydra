"""Conversation builder for token-optimized LLM API calls.

This module provides the ConversationBuilder class that transforms a full message
thread into a token-optimized conversation for LLM API calls. It implements:

- Sliding window for recent messages (always included)
- LLM-based summarization for older messages
- Redis caching for summaries (24h TTL)
- Accurate token counting per provider/model
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from hydra.db.redis import RedisClient

logger = structlog.get_logger(__name__)


# =============================================================================
# Token Counter
# =============================================================================


class TokenCounter:
    """Accurate token counting per provider/model.

    Uses tiktoken for OpenAI models (accurate) and character-based estimation
    for other providers.
    """

    # Model to tokenizer encoding mapping for OpenAI
    OPENAI_ENCODINGS = {
        # GPT-4o series uses o200k_base
        "gpt-4o": "o200k_base",
        "gpt-4o-mini": "o200k_base",
        "gpt-4o-2024": "o200k_base",
        # O-series reasoning models use o200k_base
        "o1": "o200k_base",
        "o1-mini": "o200k_base",
        "o1-preview": "o200k_base",
        "o3": "o200k_base",
        "o3-mini": "o200k_base",
        "o4": "o200k_base",
        # GPT-5 series uses o200k_base
        "gpt-5": "o200k_base",
        "gpt-5.1": "o200k_base",
        "gpt-5.2": "o200k_base",
        # GPT-4 series uses cl100k_base
        "gpt-4-turbo": "cl100k_base",
        "gpt-4-1106": "cl100k_base",
        "gpt-4-0125": "cl100k_base",
        "gpt-4-vision": "cl100k_base",
        "gpt-4": "cl100k_base",
        "gpt-4.1": "cl100k_base",
        # GPT-3.5 uses cl100k_base
        "gpt-3.5": "cl100k_base",
    }

    # Character to token ratio estimates for non-OpenAI providers
    CHAR_RATIOS = {
        "anthropic": 4.0,  # Claude models
        "ollama": 4.0,     # Local models
        "openrouter": 4.0, # Mixed, use conservative estimate
    }

    def __init__(self, provider: str, model: str):
        """Initialize token counter for a specific provider/model.

        Args:
            provider: Provider type (anthropic, openai, ollama, openrouter).
            model: Model identifier.
        """
        self.provider = provider.lower() if provider else "unknown"
        self.model = model.lower() if model else "unknown"
        self._encoder = self._get_encoder()

    def _get_encoder(self) -> Any | None:
        """Get tiktoken encoder for OpenAI models."""
        if self.provider not in ("openai", "openrouter"):
            return None

        try:
            import tiktoken
        except ImportError:
            logger.warning("tiktoken_not_available", msg="Install tiktoken for accurate OpenAI token counting")
            return None

        # Check for OpenRouter OpenAI models
        model_to_check = self.model
        if self.provider == "openrouter" and "openai/" in model_to_check:
            model_to_check = model_to_check.replace("openai/", "")

        # Find matching encoding
        for model_prefix, encoding_name in self.OPENAI_ENCODINGS.items():
            if model_to_check.startswith(model_prefix):
                try:
                    return tiktoken.get_encoding(encoding_name)
                except Exception as e:
                    logger.warning("tiktoken_encoding_error", encoding=encoding_name, error=str(e))
                    return None

        # Default to cl100k_base for unknown OpenAI models
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    def count(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for.

        Returns:
            Estimated token count.
        """
        if not text:
            return 0

        if self._encoder:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass

        # Estimate based on character ratio
        ratio = self.CHAR_RATIOS.get(self.provider, 4.0)
        return int(len(text) / ratio) + 1

    def count_message(self, message: dict) -> int:
        """Count tokens in a single message including overhead.

        Args:
            message: Message dict with role, content, and optional tool_calls.

        Returns:
            Estimated token count including message overhead.
        """
        # Base overhead for message structure (~4 tokens per message)
        tokens = 4

        # Content tokens
        content = message.get("content", "")
        if content:
            tokens += self.count(content)

        # Tool calls tokens
        tool_calls = message.get("tool_calls") or message.get("toolCalls") or []
        for tc in tool_calls:
            # Tool name
            name = tc.get("name", "")
            tokens += self.count(name)

            # Tool arguments/input
            args = tc.get("arguments") or tc.get("input") or {}
            if isinstance(args, dict):
                tokens += self.count(json.dumps(args))
            elif isinstance(args, str):
                tokens += self.count(args)

        return tokens

    def count_messages(self, messages: list[dict]) -> int:
        """Count tokens in a list of messages.

        Args:
            messages: List of message dicts.

        Returns:
            Total estimated token count.
        """
        return sum(self.count_message(msg) for msg in messages)


# =============================================================================
# Conversation Data Class
# =============================================================================


@dataclass
class Conversation:
    """Token-optimized conversation for LLM API calls.

    This represents a conversation that has been optimized to fit within
    a model's context window, with older messages summarized.

    Attributes:
        system_prompt: The system prompt for the conversation.
        summary: Optional summary of older messages.
        messages: Recent messages included in full.
        token_count: Total token count of the conversation.
        context_window: The model's context window size.
        truncated_count: Number of messages that were summarized/dropped.
    """

    system_prompt: str
    summary: str | None
    messages: list[dict]
    token_count: int
    context_window: int
    truncated_count: int = 0

    def to_messages(self, provider: str) -> list[dict]:
        """Format conversation for a specific provider's API.

        Args:
            provider: Provider type (anthropic, openai, ollama).

        Returns:
            List of formatted messages for the provider's API.
        """
        result = []

        # Add summary as context if present
        if self.summary:
            if provider == "anthropic":
                # For Anthropic, we'll prepend to system prompt (handled externally)
                pass
            else:
                # For OpenAI/Ollama, add as system message
                result.append({
                    "role": "system",
                    "content": f"[Previous conversation summary]\n{self.summary}",
                })

        # Add recent messages
        result.extend(self.messages)

        return result

    def get_system_prompt_with_summary(self) -> str:
        """Get system prompt with summary prepended (for Anthropic).

        Returns:
            System prompt with summary context.
        """
        if self.summary:
            return f"[Previous conversation summary]\n{self.summary}\n\n{self.system_prompt}"
        return self.system_prompt


# =============================================================================
# Context Window Sizes
# =============================================================================


# Context window sizes for common models
MODEL_CONTEXT_WINDOWS = {
    # Anthropic Claude models
    "claude-3-5-sonnet": 200000,
    "claude-3-5-haiku": 200000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-2": 100000,
    # OpenAI models
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4-1106": 128000,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4.1": 1000000,  # 1M context
    "gpt-5": 256000,
    "gpt-5.1": 256000,
    "gpt-5.2": 256000,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
    # O-series reasoning models
    "o1": 128000,
    "o1-mini": 128000,
    "o1-preview": 128000,
    "o3": 128000,
    "o3-mini": 128000,
    "o4": 128000,
    # Ollama models
    "llama3.1": 128000,
    "llama3.2": 128000,
    "llama3.3": 128000,
    "llama3": 8192,
    "mistral": 32768,
    "mixtral": 32768,
    "qwen2": 32768,
    "qwen2.5": 32768,
    "deepseek": 64000,
}


def get_context_window(provider: str, model: str) -> int:
    """Get context window size for a model.

    Args:
        provider: Provider type.
        model: Model identifier.

    Returns:
        Context window size in tokens.
    """
    model_lower = model.lower()

    # Check for exact or prefix match
    for model_prefix, context_size in MODEL_CONTEXT_WINDOWS.items():
        if model_lower.startswith(model_prefix):
            return context_size

    # Default context windows by provider
    defaults = {
        "anthropic": 200000,
        "openai": 128000,
        "ollama": 8192,
        "openrouter": 128000,
    }

    return defaults.get(provider.lower(), 8192)


# =============================================================================
# Conversation Builder
# =============================================================================


@dataclass
class ConversationBuilder:
    """Builds token-optimized conversations from message threads.

    This class transforms a full message thread into a conversation that fits
    within a model's context window. It uses:

    1. Sliding window for recent messages (always included)
    2. LLM-based summarization for older messages
    3. Redis caching for summaries (24h TTL)

    Attributes:
        provider: Provider type (anthropic, openai, ollama, openrouter).
        model: Model identifier.
        context_window: Model's context window size.
        reserved_output: Tokens reserved for model output.
        redis: Optional Redis client for caching.
        llm_bridge: Optional LLM bridge for summarization.
    """

    provider: str
    model: str
    context_window: int = field(default=0)
    reserved_output: int = field(default=4096)
    redis: "RedisClient | None" = field(default=None)
    llm_bridge: Any = field(default=None)  # Circular import prevention

    # Token budget allocation ratios
    SYSTEM_BUDGET_RATIO: float = field(default=0.05, init=False)   # 5% for system prompt
    SUMMARY_BUDGET_RATIO: float = field(default=0.15, init=False)  # 15% for summary
    RECENT_BUDGET_RATIO: float = field(default=0.80, init=False)   # 80% for recent messages

    # Cache settings
    SUMMARY_CACHE_TTL: int = field(default=86400, init=False)  # 24 hours
    CONVERSATION_CACHE_TTL: int = field(default=3600, init=False)  # 1 hour

    def __post_init__(self):
        """Initialize computed fields after dataclass init."""
        if self.context_window == 0:
            self.context_window = get_context_window(self.provider, self.model)

        self._token_counter = TokenCounter(self.provider, self.model)

        # Calculate available tokens and budgets
        self.available_tokens = self.context_window - self.reserved_output
        self.system_budget = int(self.available_tokens * self.SYSTEM_BUDGET_RATIO)
        self.summary_budget = int(self.available_tokens * self.SUMMARY_BUDGET_RATIO)
        self.recent_budget = int(self.available_tokens * self.RECENT_BUDGET_RATIO)

    async def build(
        self,
        thread: list[dict],
        system_prompt: str,
        session_id: str,
    ) -> Conversation:
        """Build a token-optimized conversation from a message thread.

        Args:
            thread: Full message thread (all messages in session).
            system_prompt: System prompt for the conversation.
            session_id: Session ID for cache key generation.

        Returns:
            Conversation object optimized for the model's context window.
        """
        if not thread:
            return Conversation(
                system_prompt=system_prompt,
                summary=None,
                messages=[],
                token_count=self._token_counter.count(system_prompt),
                context_window=self.context_window,
                truncated_count=0,
            )

        # Count system prompt tokens
        system_tokens = self._token_counter.count(system_prompt)

        # Calculate effective budget for recent messages
        effective_recent_budget = self.available_tokens - system_tokens - self.summary_budget

        # Phase 1: Fill recent messages from end of thread (sliding window)
        recent_messages = []
        recent_tokens = 0
        cutoff_index = len(thread)

        for i in range(len(thread) - 1, -1, -1):
            msg = thread[i]
            msg_tokens = self._token_counter.count_message(msg)

            if recent_tokens + msg_tokens > effective_recent_budget:
                cutoff_index = i + 1
                break

            recent_messages.insert(0, msg)
            recent_tokens += msg_tokens
            cutoff_index = i

        # Phase 2: Summarize older messages if any exist
        older_messages = thread[:cutoff_index]
        summary = None
        summary_tokens = 0
        truncated_count = len(older_messages)

        if older_messages:
            summary = await self._get_or_create_summary(
                session_id=session_id,
                messages=older_messages,
                token_budget=self.summary_budget,
            )
            if summary:
                summary_tokens = self._token_counter.count(summary)

        total_tokens = system_tokens + summary_tokens + recent_tokens

        logger.debug(
            "conversation_built",
            session_id=session_id,
            thread_length=len(thread),
            recent_count=len(recent_messages),
            truncated_count=truncated_count,
            total_tokens=total_tokens,
            context_window=self.context_window,
            has_summary=summary is not None,
        )

        return Conversation(
            system_prompt=system_prompt,
            summary=summary,
            messages=recent_messages,
            token_count=total_tokens,
            context_window=self.context_window,
            truncated_count=truncated_count,
        )

    async def _get_or_create_summary(
        self,
        session_id: str,
        messages: list[dict],
        token_budget: int,
    ) -> str | None:
        """Get cached summary or create new one via LLM.

        Args:
            session_id: Session ID for cache key.
            messages: Messages to summarize.
            token_budget: Maximum tokens for the summary.

        Returns:
            Summary text or None if summarization fails.
        """
        if not messages:
            return None

        # Create deterministic cache key
        cache_key = self._create_summary_cache_key(session_id, messages)

        # Check Redis cache first
        if self.redis:
            try:
                cached = await self.redis.cache_get(f"conversation:summary:{cache_key}")
                if cached:
                    logger.debug("summary_cache_hit", cache_key=cache_key)
                    return cached
            except Exception as e:
                logger.warning("summary_cache_get_error", error=str(e))

        # Generate new summary via LLM
        summary = await self._generate_summary(messages, token_budget)

        # Cache the summary
        if self.redis and summary:
            try:
                await self.redis.cache_set(
                    f"conversation:summary:{cache_key}",
                    summary,
                    self.SUMMARY_CACHE_TTL,
                )
                logger.debug("summary_cached", cache_key=cache_key)
            except Exception as e:
                logger.warning("summary_cache_set_error", error=str(e))

        return summary

    def _create_summary_cache_key(self, session_id: str, messages: list[dict]) -> str:
        """Create deterministic cache key for a message range.

        Args:
            session_id: Session ID.
            messages: Messages being summarized.

        Returns:
            16-character hex hash.
        """
        # Use first and last message IDs + count for key
        first_id = messages[0].get("message_id", messages[0].get("messageId", ""))
        last_id = messages[-1].get("message_id", messages[-1].get("messageId", ""))
        count = len(messages)

        key_str = f"{session_id}:{first_id}:{last_id}:{count}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    async def _generate_summary(
        self,
        messages: list[dict],
        token_budget: int,
    ) -> str | None:
        """Generate summary of messages using LLM.

        Args:
            messages: Messages to summarize.
            token_budget: Maximum tokens for the summary.

        Returns:
            Summary text or None.
        """
        if not self.llm_bridge:
            # Fallback to simple summary without LLM
            return self._create_simple_summary(messages, token_budget)

        # Build summarization prompt
        message_lines = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            # Truncate long messages for summarization input
            if len(content) > 500:
                content = content[:500] + "..."
            message_lines.append(f"{role}: {content}")

        message_text = "\n".join(message_lines)
        max_words = token_budget // 4  # Rough estimate: 4 chars per token, 5 chars per word

        summarization_prompt = f"""Summarize the following conversation history concisely.
Focus on: key topics discussed, decisions made, important context for continuing the conversation.
Keep your summary under {max_words} words.

CONVERSATION:
{message_text}

SUMMARY:"""

        try:
            summary = ""
            summarization_config = self._get_summarization_config()

            async for event in self.llm_bridge.stream_completion(
                provider_config=summarization_config,
                messages=[{"role": "user", "content": summarization_prompt}],
                max_tokens=token_budget,
                temperature=0.3,  # Low temperature for factual summary
            ):
                if event.get("type") == "text_delta":
                    summary += event.get("text", "")
                elif event.get("type") == "done":
                    break
                elif event.get("type") == "error":
                    logger.warning("summarization_llm_error", error=event.get("error"))
                    return self._create_simple_summary(messages, token_budget)

            return summary.strip() if summary else self._create_simple_summary(messages, token_budget)

        except Exception as e:
            logger.warning("summarization_error", error=str(e))
            return self._create_simple_summary(messages, token_budget)

    def _get_summarization_config(self) -> dict:
        """Get config for summarization model (fast/cheap model).

        Returns:
            Provider config dict for a fast summarization model.
        """
        # Use a fast model based on provider type
        if self.provider == "anthropic":
            return {
                "type": "anthropic",
                "model": "claude-3-haiku-20240307",
                "api_key": None,  # Will use same key as main provider
            }
        elif self.provider == "openai":
            return {
                "type": "openai",
                "model": "gpt-4o-mini",
                "api_key": None,
            }
        else:
            # Use main model for other providers
            return {
                "type": self.provider,
                "model": self.model,
            }

    def _create_simple_summary(self, messages: list[dict], token_budget: int) -> str:
        """Create simple summary without LLM (fallback).

        Args:
            messages: Messages to summarize.
            token_budget: Maximum tokens for the summary.

        Returns:
            Simple bullet-point summary.
        """
        points = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "user")
            if content:
                # Take first 100 chars of each message
                truncated = content[:100] + "..." if len(content) > 100 else content
                points.append(f"- {role}: {truncated}")

        # Take last N points that fit in budget
        summary_lines = ["Previous conversation:"]
        max_chars = token_budget * 4  # ~4 chars per token

        for point in reversed(points):
            if len("\n".join(summary_lines + [point])) > max_chars:
                break
            summary_lines.insert(1, point)

        return "\n".join(summary_lines)
