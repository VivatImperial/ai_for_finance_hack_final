from __future__ import annotations

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class PromptParams:
    temperature: float
    top_p: float
    max_tokens: int


@dataclass(frozen=True)
class RagPromptSettings:
    orchestrator: PromptParams
    fusion: PromptParams
    chunk_answer: PromptParams
    full_context_answer: PromptParams
    general_answer: PromptParams
    clarification: PromptParams


@dataclass(frozen=True)
class KnowledgeBaseSettings:
    collection_name: str
    user_id: int
    limit: int
    score_threshold: float | None


@dataclass(frozen=True)
class RagAgentSettings:
    messages_limit: int
    max_context_chars: int
    default_top_k: int
    default_score_threshold: float | None
    use_query_expansion: bool
    rrf_k: int
    orchestrator_confidence_threshold: float
    orchestrator_history_tail: int
    clarifications_limit: int
    prompts: RagPromptSettings
    knowledge_base: KnowledgeBaseSettings
    tool_history_tail: int


def load_rag_agent_settings() -> RagAgentSettings:
    prompts = RagPromptSettings(
        orchestrator=PromptParams(
            temperature=float(settings.RAG_ORCHESTRATOR_TEMPERATURE),
            top_p=float(settings.RAG_ORCHESTRATOR_TOP_P),
            max_tokens=int(settings.RAG_ORCHESTRATOR_MAX_TOKENS),
        ),
        fusion=PromptParams(
            temperature=float(settings.RAG_FUSION_TEMPERATURE),
            top_p=float(settings.RAG_FUSION_TOP_P),
            max_tokens=int(settings.RAG_FUSION_MAX_TOKENS),
        ),
        chunk_answer=PromptParams(
            temperature=float(settings.RAG_ANSWER_TEMPERATURE),
            top_p=float(settings.RAG_ANSWER_TOP_P),
            max_tokens=int(settings.RAG_CHUNKS_MAX_TOKENS),
        ),
        full_context_answer=PromptParams(
            temperature=float(settings.RAG_ANSWER_TEMPERATURE),
            top_p=float(settings.RAG_ANSWER_TOP_P),
            max_tokens=int(settings.RAG_FULL_CONTEXT_MAX_TOKENS),
        ),
        general_answer=PromptParams(
            temperature=float(settings.RAG_GENERAL_TEMPERATURE),
            top_p=float(settings.RAG_GENERAL_TOP_P),
            max_tokens=int(settings.RAG_GENERAL_MAX_TOKENS),
        ),
        clarification=PromptParams(
            temperature=float(settings.RAG_CLARIFICATION_TEMPERATURE),
            top_p=float(settings.RAG_CLARIFICATION_TOP_P),
            max_tokens=int(settings.RAG_CLARIFICATION_MAX_TOKENS),
        ),
    )

    knowledge_base = KnowledgeBaseSettings(
        collection_name=settings.RAG_KB_COLLECTION_NAME,
        user_id=int(settings.RAG_KB_USER_ID),
        limit=int(settings.RAG_KB_LIMIT),
        score_threshold=settings.RAG_KB_SCORE_THRESHOLD,
    )

    return RagAgentSettings(
        messages_limit=int(settings.RAG_MESSAGES_LIMIT),
        max_context_chars=int(settings.RAG_MAX_CONTEXT_CHARS),
        default_top_k=int(settings.RAG_DEFAULT_TOP_K),
        default_score_threshold=settings.RAG_DEFAULT_SCORE_THRESHOLD,
        use_query_expansion=bool(settings.RAG_USE_QUERY_EXPANSION),
        rrf_k=int(settings.RAG_RRF_K),
        orchestrator_confidence_threshold=float(
            settings.RAG_ORCHESTRATOR_CONFIDENCE_THRESHOLD
        ),
        orchestrator_history_tail=int(settings.RAG_ORCHESTRATOR_HISTORY_TAIL),
        clarifications_limit=int(settings.RAG_CLARIFICATIONS_LIMIT),
        prompts=prompts,
        knowledge_base=knowledge_base,
        tool_history_tail=int(settings.RAG_TOOL_HISTORY_TAIL),
    )


__all__ = [
    "KnowledgeBaseSettings",
    "PromptParams",
    "RagAgentSettings",
    "RagPromptSettings",
    "load_rag_agent_settings",
]
