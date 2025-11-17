"""Token-aware context management for optimal LLM input."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import structlog

from services.document_processing.vector_manager import VectorSearchResult

logger = structlog.get_logger(__name__)


class TokenAwareContextManager:
    """Manage context with token budget for optimal LLM usage."""

    def __init__(
        self,
        model: str = "anthropic/claude-3.5-sonnet",
        max_tokens: int = 180000,  # Claude 3.5 Sonnet context limit
        reserved_for_output: int = 4000,
        reserved_for_system: int = 2000,
    ):
        """
        Initialize token-aware context manager.

        Note: Using simple heuristic (chars * 0.25) for token estimation
        since tiktoken doesn't support all models. For production, consider
        model-specific tokenizers.
        """
        self._model = model
        self._max_tokens = max_tokens
        self._reserved_output = reserved_for_output
        self._reserved_system = reserved_for_system
        self._available = max_tokens - reserved_for_output - reserved_for_system

        # Simple heuristic: ~4 chars per token for Cyrillic/mixed text
        self._chars_per_token = 4.0

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count using character-based heuristic.

        For production: Replace with actual tokenizer for your model.
        - Claude: anthropic.count_tokens()
        - GPT: tiktoken
        - OpenRouter: model-specific tokenizers
        """
        if not text:
            return 0
        return int(len(text) / self._chars_per_token)

    def estimate_messages_tokens(self, messages: list[dict]) -> int:
        """Estimate tokens in message list."""
        total = 0
        for msg in messages:
            # Account for message formatting overhead
            total += 4  # Role/content structure
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
        return total

    def truncate_to_budget(
        self,
        messages: list[dict],
        budget: int,
        preserve_system: bool = True,
    ) -> list[dict]:
        """
        Truncate messages to fit budget, keeping most recent.

        Args:
            messages: List of message dicts
            budget: Maximum tokens allowed
            preserve_system: If True, always keep system messages
        """
        if not messages:
            return []

        # Separate system and other messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        if preserve_system:
            system_tokens = self.estimate_messages_tokens(system_msgs)
            available = max(0, budget - system_tokens)
        else:
            system_msgs = []
            available = budget

        if available <= 0:
            logger.warning(
                "budget-exhausted-by-system",
                system_tokens=system_tokens if preserve_system else 0,
                budget=budget,
            )
            return system_msgs

        # Add messages from most recent, stay under budget
        result = []
        current_tokens = 0

        for msg in reversed(other_msgs):
            msg_tokens = self.estimate_tokens(msg.get("content", "")) + 4
            if current_tokens + msg_tokens > available:
                break
            result.insert(0, msg)
            current_tokens += msg_tokens

        logger.info(
            "messages-truncated",
            original_count=len(other_msgs),
            kept_count=len(result),
            tokens_used=current_tokens,
            budget=available,
        )

        return system_msgs + result

    def optimize_chunks(
        self,
        chunks: list[VectorSearchResult],
        max_chunk_tokens: int = 500,
    ) -> list[VectorSearchResult]:
        """
        Optimize chunks to fit token budget.
        Truncates chunks that are too long while preserving meaning.
        """
        if not chunks:
            return []

        optimized = []

        for chunk in chunks:
            content = chunk.chunk.chunk_content
            tokens = self.estimate_tokens(content)

            if tokens <= max_chunk_tokens:
                optimized.append(chunk)
            else:
                # Truncate content to fit budget
                target_chars = int(max_chunk_tokens * self._chars_per_token * 0.9)
                truncated = content[:target_chars] + "..."

                # Create new chunk with truncated content
                truncated_chunk = SimpleNamespace(
                    chunk_id=chunk.chunk.chunk_id,
                    chunk_serial=chunk.chunk.chunk_serial,
                    chunk_content=truncated,
                )

                optimized.append(
                    VectorSearchResult(
                        chunk=truncated_chunk,
                        score=chunk.score,
                        payload=chunk.payload,
                    )
                )

                logger.debug(
                    "chunk-truncated",
                    chunk_id=chunk.chunk.chunk_id,
                    original_tokens=tokens,
                    truncated_tokens=self.estimate_tokens(truncated),
                )

        return optimized

    def build_optimal_context(
        self,
        *,
        system_prompt: str,
        guidance: str,
        history: list[dict],
        user_query: str,
        chunks: list[VectorSearchResult] | None = None,
        chunk_weight: float = 0.6,  # 60% of budget for chunks
    ) -> tuple[list[dict], dict[str, Any]]:
        """
        Build context that fits within token budget.

        Returns:
            (messages, stats) where stats contains token usage info
        """
        # Calculate base usage
        system_tokens = self.estimate_tokens(system_prompt)
        guidance_tokens = self.estimate_tokens(guidance)
        query_tokens = self.estimate_tokens(user_query) + 4

        base_tokens = system_tokens + guidance_tokens + query_tokens

        # Budget for chunks and history
        remaining = max(0, self._available - base_tokens)

        # Allocate budget (configurable weights)
        chunk_budget = int(remaining * chunk_weight)
        history_budget = int(remaining * (1.0 - chunk_weight))

        stats = {
            "total_budget": self._available,
            "base_tokens": base_tokens,
            "remaining": remaining,
            "chunk_budget": chunk_budget,
            "history_budget": history_budget,
        }

        # Optimize chunks
        optimized_chunks = []
        chunks_tokens = 0

        if chunks:
            optimized_chunks = self.optimize_chunks(chunks, max_chunk_tokens=500)

            # Calculate total tokens for chunks
            chunks_tokens = sum(
                self.estimate_tokens(c.chunk.chunk_content) + 20  # +20 for formatting
                for c in optimized_chunks
            )

            # If chunks exceed budget, drop lowest scoring
            while chunks_tokens > chunk_budget and len(optimized_chunks) > 3:
                dropped = optimized_chunks.pop()  # Remove last (lowest score)
                chunks_tokens = sum(
                    self.estimate_tokens(c.chunk.chunk_content) + 20
                    for c in optimized_chunks
                )
                logger.debug(
                    "chunk-dropped-budget",
                    chunk_id=dropped.chunk.chunk_id,
                    score=dropped.score,
                )

            stats["chunks_tokens"] = chunks_tokens
            stats["chunks_count"] = len(optimized_chunks)

        # Optimize history
        optimized_history = self.truncate_to_budget(history, history_budget)
        history_tokens = self.estimate_messages_tokens(optimized_history)
        stats["history_tokens"] = history_tokens
        stats["history_count"] = len(optimized_history)

        # Build final messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": guidance},
        ]
        messages.extend(optimized_history)

        # Add user message with optional chunks
        if optimized_chunks:
            chunks_text = self._format_chunks_context(optimized_chunks)
            user_content = f"{chunks_text}\n\n{user_query}"
        else:
            user_content = user_query

        messages.append({"role": "user", "content": user_content})

        # Calculate final usage
        total_tokens = self.estimate_messages_tokens(messages)
        stats["total_tokens"] = total_tokens
        stats["utilization"] = total_tokens / self._available

        logger.info(
            "context-built",
            total_tokens=total_tokens,
            utilization=f"{stats['utilization'] * 100:.1f}%",
            chunks=len(optimized_chunks),
            history_messages=len(optimized_history),
        )

        return messages, stats

    def _format_chunks_context(self, chunks: list[VectorSearchResult]) -> str:
        """Format chunks for context inclusion."""
        if not chunks:
            return ""

        parts = ["=== КОНТЕКСТ ИЗ ДОКУМЕНТОВ ===\n"]

        for i, chunk in enumerate(chunks, 1):
            payload = chunk.payload or {}
            title = payload.get(
                "filename", f"Документ {payload.get('document_id', '?')}"
            )

            parts.append(f"## Фрагмент {i} [{title}]\n{chunk.chunk.chunk_content}\n")

        return "\n".join(parts)


__all__ = ["TokenAwareContextManager"]
