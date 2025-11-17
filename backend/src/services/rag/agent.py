from __future__ import annotations

import json
import math
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Sequence
from urllib.parse import urlparse

import structlog
from qdrant_client.http.models import FieldCondition, MatchValue
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import ParsedDocument, User
from db.repositories.document_repo import ParsedDocumentRepository
from db.repositories.message_repo import MessageRepository
from services.document_processing.vector_manager import (
    DocumentVectorManager,
    VectorSearchResult,
)
from services.embeddings.openrouter import OpenRouterEmbeddingClient
from services.qdrant.vector_store import QdrantVectorStore
from services.rag.configuration import (
    PromptParams,
    RagAgentSettings,
    load_rag_agent_settings,
)
from services.rag.external_clients import CentralBankClient, TavilyClient
from services.rag.fusion_planner import FusionPlanner, FusionPlan
from services.rag.openrouter_chat import OpenRouterChatClient
from services.rag.tool_registry import (
    ToolContext,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    ToolInvocation,
)
from services.rag.tool_executor import ParallelToolExecutor
from services.rag.context_manager import TokenAwareContextManager


logger = structlog.get_logger(__name__)


@dataclass
class AgentResult:
    answer: str
    used_chunks: list[VectorSearchResult]
    scenario: int
    debug: dict[str, Any]


@dataclass
class ScenarioDecision:
    scenario: int
    confidence: float
    reason: str
    follow_up: bool
    clarifications: list[str]
    use_query_expansion: bool | None
    rule_guess: int
    raw_response: dict[str, Any] | None = None
    intent: str | None = None


class VectorSearchError(Exception):
    """Raised when vector search cannot be completed."""


class RagAgent:
    _RUSSIAN_NEWS_DOMAINS = (
        "cbr.ru",
        "tass.ru",
        "ria.ru",
        "rbc.ru",
        "vedomosti.ru",
        "kommersant.ru",
        "interfax.ru",
        "banki.ru",
        "finmarket.ru",
        "iz.ru",
        "1prime.ru",
        "forbes.ru",
        "rg.ru",
        "vestifinance.ru",
    )

    def __init__(
        self,
        *,
        chat_client: OpenRouterChatClient | None = None,
        vector_manager: DocumentVectorManager | None = None,
        config: RagAgentSettings | None = None,
    ) -> None:
        self._chat = chat_client or OpenRouterChatClient.from_settings()
        self._vectors = vector_manager or DocumentVectorManager()
        self._config = config or load_rag_agent_settings()
        self._messages_limit = self._config.messages_limit
        self._max_context_chars = self._config.max_context_chars
        self._top_k = self._config.default_top_k
        self._score_threshold = self._config.default_score_threshold
        self._rrf_k = self._config.rrf_k
        self._default_use_query_expansion = bool(self._config.use_query_expansion)
        self._kb_settings = self._config.knowledge_base
        self._kb_embeddings = OpenRouterEmbeddingClient.from_settings()
        self._kb_store = QdrantVectorStore(
            url=getattr(settings, "QDRANT_URL", None),
            collection_name=self._kb_settings.collection_name,
            batch_size=int(getattr(settings, "QDRANT_BATCH_SIZE", 64)),
        )
        self._fusion_planner = FusionPlanner(
            chat_client=self._chat,
            prompt_params=self._config.prompts.fusion,
            history_tail=self._config.orchestrator_history_tail,
        )
        self._tool_registry = self._build_tool_registry()
        self._cbr_client = CentralBankClient(
            base_url=settings.CBR_API_BASE_URL,
            cache_ttl_seconds=int(settings.CBR_CACHE_TTL_SECONDS),
        )
        self._tavily_client = TavilyClient(
            api_key=settings.TAVILY_API_KEY,
            base_url=settings.TAVILY_BASE_URL,
            timeout_seconds=float(settings.TAVILY_TIMEOUT_SECONDS),
            cache_ttl_seconds=int(settings.TAVILY_CACHE_TTL_SECONDS),
        )

        # Initialize parallel executor with retry logic
        max_retries = int(getattr(settings, "RAG_MAX_TOOL_RETRIES", 2))
        self._parallel_executor = ParallelToolExecutor(
            registry=self._tool_registry,
            max_retries=max_retries,
        )

        # Initialize token-aware context manager
        self._context_manager = TokenAwareContextManager(
            model="anthropic/claude-3.5-sonnet",
            max_tokens=int(getattr(settings, "RAG_TOKEN_BUDGET", 180000)),
            reserved_for_output=int(
                getattr(settings, "RAG_RESERVED_OUTPUT_TOKENS", 4000)
            ),
            reserved_for_system=int(
                getattr(settings, "RAG_RESERVED_SYSTEM_TOKENS", 2000)
            ),
        )
        self._preferred_news_domains = set(self._RUSSIAN_NEWS_DOMAINS)

    async def run(
        self,
        *,
        db: AsyncSession,
        user: User,
        query: str,
        chat_id: int | None = None,
        selected_document_ids: Sequence[int] | None = None,
        answer_instructions: str | None = None,
    ) -> AgentResult:
        current_dt = datetime.now(timezone.utc)
        current_dt_iso = current_dt.isoformat()
        history = await self._load_chat_history(db, chat_id) if chat_id else []
        decision = await self._choose_scenario(
            query=query,
            history=history,
            selected_ids=selected_document_ids,
            current_datetime=current_dt_iso,
        )
        scenario = decision.scenario

        used_chunks: list[VectorSearchResult] = []
        debug: dict[str, Any] = {
            "history_len": len(history),
            "scenario": scenario,
            "current_datetime": current_dt_iso,
            "scenario_decision": {
                "confidence": decision.confidence,
                "reason": decision.reason,
                "follow_up": decision.follow_up,
                "clarifications": decision.clarifications,
                "rule_guess": decision.rule_guess,
                "raw_response": decision.raw_response,
                "intent": decision.intent,
            },
        }

        if decision.follow_up:
            scenario = 5
            answer = await self._ask_clarification(
                query=query, history=history, clarifications=decision.clarifications
            )
            return AgentResult(
                answer=answer, used_chunks=used_chunks, scenario=scenario, debug=debug
            )

        instructions = self._resolve_instructions(answer_instructions)

        scenario, precomputed_debug = await self._adjust_scenario_for_documents(
            db=db,
            selected_ids=selected_document_ids,
            scenario=scenario,
        )
        debug.update(precomputed_debug)

        allowed_tools = self._tools_for_scenario(scenario, decision.intent)

        # Handle predefined responses for specific intents
        if decision.intent in {"small_talk", "off_topic"}:
            answer = self._get_predefined_response(decision.intent, query)
            return AgentResult(
                answer=answer, used_chunks=used_chunks, scenario=scenario, debug=debug
            )

        if scenario == 5 or (
            not allowed_tools
            and decision.intent != "small_talk"
            and decision.intent != "off_topic"
        ):
            answer = await self._ask_clarification(
                query=query, history=history, clarifications=decision.clarifications
            )
        else:
            try:
                answer, used_chunks, tool_usage = await self._run_tool_conversation(
                    scenario=scenario,
                    query=query,
                    history=history,
                    instructions=instructions,
                    allowed_tools=allowed_tools,
                    db=db,
                    user=user,
                    selected_ids=selected_document_ids,
                    intent=decision.intent,
                    current_datetime=current_dt_iso,
                    use_query_expansion=decision.use_query_expansion,
                )
                debug["tool_calls"] = tool_usage
            except VectorSearchError as exc:
                logger.warning("vector-search-unavailable", reason=str(exc))
                debug["vector_search_error"] = str(exc)
                answer = self._vector_search_unavailable_message()

        return AgentResult(
            answer=answer, used_chunks=used_chunks, scenario=scenario, debug=debug
        )

    async def _load_chat_history(
        self, db: AsyncSession, chat_id: int
    ) -> list[dict[str, str]]:
        msgs = await MessageRepository(db).get_last_for_chat(
            chat_id=chat_id, limit=self._messages_limit
        )
        history: list[dict[str, str]] = []
        for m in msgs:
            role = "assistant" if m.message_type.name == "MODEL" else "user"
            history.append({"role": role, "content": m.content})
        return history

    async def _choose_scenario(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        selected_ids: Sequence[int] | None,
        current_datetime: str,
    ) -> ScenarioDecision:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")
        orchestrator_prompt = (base / "orchestrator_ru.txt").read_text(encoding="utf-8")

        rule_guess = self._rule_guess_scenario(
            query=query, history=history, selected_ids=selected_ids
        )
        sys_msg = {"role": "system", "content": system_prompt}
        orch_msg = {"role": "system", "content": orchestrator_prompt}
        user_msg = {
            "role": "user",
            "content": json.dumps(
                {
                    "query": query,
                    "selected_document_ids": list(selected_ids or []),
                    "has_history": bool(history),
                    "rule_guess": rule_guess,
                    "history_messages": len(history),
                    "current_datetime": current_datetime,
                },
                ensure_ascii=False,
            ),
        }

        history_tail = self._config.orchestrator_history_tail
        messages = [sys_msg, orch_msg, *history[-history_tail:], user_msg]
        prompt_params = self._config.prompts.orchestrator
        resp = await self._chat.chat(
            messages=messages,
            **self._prompt_kwargs(prompt_params),
            response_format={"type": "json_object"},
        )
        try:
            content = resp["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            llm_scenario = int(parsed.get("scenario", 3))
            confidence = float(parsed.get("confidence", 0.5))
            threshold = self._config.orchestrator_confidence_threshold
            scenario = llm_scenario if confidence >= threshold else rule_guess
            clarifications = [str(item) for item in parsed.get("clarifications", [])][
                : self._config.clarifications_limit
            ]
            use_qe = parsed.get("use_query_expansion")
            if isinstance(use_qe, str):
                use_qe = use_qe.lower() in {"true", "1", "yes"}
            intent = parsed.get("intent")
            decision = ScenarioDecision(
                scenario=scenario,
                confidence=confidence,
                reason=str(parsed.get("reason", "")),
                follow_up=bool(parsed.get("follow_up", False)),
                clarifications=clarifications,
                use_query_expansion=use_qe if use_qe is not None else None,
                rule_guess=rule_guess,
                raw_response=parsed,
                intent=intent,
            )
        except Exception:
            decision = ScenarioDecision(
                scenario=rule_guess,
                confidence=0.0,
                reason="rule fallback",
                follow_up=False,
                clarifications=[],
                use_query_expansion=None,
                rule_guess=rule_guess,
                raw_response=None,
                intent=None,
            )
        return decision

    def _rule_guess_scenario(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        selected_ids: Sequence[int] | None,
    ) -> int:
        if selected_ids and len(selected_ids) > 0:
            return 3
        q = (query or "").lower()
        search_keywords = (
            "найти",
            "найди",
            "ищи",
            "поиск",
            "где",
            "какой договор",
            "какой документ",
            "покажи",
            "подбери",
        )
        if any(k in q for k in search_keywords):
            return 1
        if not q.strip():
            return 5
        return 2

    async def _adjust_scenario_for_documents(
        self,
        *,
        db: AsyncSession,
        selected_ids: Sequence[int] | None,
        scenario: int,
    ) -> tuple[int, dict[str, Any]]:
        debug: dict[str, Any] = {}
        if scenario in {3, 4} and selected_ids:
            docs, total_len = await self._load_documents(db, selected_ids)
            debug["selected_docs"] = {
                "ids": list(selected_ids),
                "total_length": total_len,
            }
            if total_len > self._max_context_chars:
                return 4, debug
            return 3, debug
        return scenario, debug

    def _tools_for_scenario(self, scenario: int, intent: str | None) -> list[str]:
        """
        Determine which tools the agent should have access to based on scenario and intent.
        Returns empty list for scenarios that don't need tools (predefined responses).
        """
        if scenario == 1:
            # Document search - only user documents
            return ["search_user_documents"]

        if scenario == 2:
            # General request - depends on intent (corporate KB, CBR, news, etc.)
            if intent == "small_talk" or intent == "off_topic":
                # No tools needed - use predefined responses
                return []
            elif intent == "cbr_rate":
                return ["fetch_cbr_data"]
            elif intent == "finance_news":
                return ["fetch_finance_news"]
            elif intent == "knowledge_base":
                return ["search_general_kb"]
            elif intent == "hybrid_kb_docs":
                # Multi-tool scenario: both knowledge base and user documents
                return ["search_general_kb", "search_user_documents"]
            else:
                # Fallback: allow corporate knowledge base search
                return ["search_general_kb"]

        if scenario == 3:
            # Full document context
            return ["load_documents_full"]

        if scenario == 4:
            # Targeted search in selected documents
            return ["search_user_documents"]

        # Scenario 5 (clarification) or unknown
        return []

    async def _run_tool_conversation(
        self,
        *,
        scenario: int,
        query: str,
        history: list[dict[str, str]],
        instructions: str,
        allowed_tools: list[str],
        db: AsyncSession,
        user: User,
        selected_ids: Sequence[int] | None,
        intent: str | None,
        current_datetime: str,
        use_query_expansion: bool | None,
    ) -> tuple[str, list[VectorSearchResult], list[dict[str, Any]]]:
        messages = self._build_tool_messages(
            scenario=scenario,
            query=query,
            history=history,
            instructions=instructions,
            selected_ids=selected_ids,
            intent=intent,
            current_datetime=current_datetime,
        )
        tool_specs = self._tool_registry.describe(allowed_tools)
        context = ToolContext(
            db=db,
            user=user,
            chat_id=None,
            history=history[-self._config.tool_history_tail :],
            selected_document_ids=selected_ids or [],
            scenario=scenario,
            instructions=instructions,
            intent=intent,
            current_datetime=current_datetime,
            use_query_expansion=use_query_expansion,
        )
        collected_chunks: list[VectorSearchResult] = []
        tool_debug: list[dict[str, Any]] = []
        max_iterations = 10

        # Check if parallel execution is enabled
        enable_parallel = getattr(settings, "RAG_ENABLE_PARALLEL_TOOLS", True)

        for iteration in range(max_iterations):
            response = await self._chat.chat(
                messages=messages,
                tools=tool_specs,
                tool_choice="auto",
            )
            message = response["choices"][0]["message"]
            role = message.get("role", "assistant")
            tool_calls = message.get("tool_calls") or []
            messages.append(
                {
                    "role": role,
                    "content": message.get("content"),
                    "tool_calls": tool_calls,
                }
            )

            if tool_calls:
                # Use parallel executor if enabled and multiple tools
                if enable_parallel and len(tool_calls) > 1:
                    logger.info(
                        "using-parallel-execution",
                        tool_count=len(tool_calls),
                        iteration=iteration + 1,
                    )

                    # Analyze dependencies and execute in parallel
                    executions = self._parallel_executor.analyze_dependencies(
                        tool_calls
                    )

                    try:
                        results = await self._parallel_executor.execute_plan(
                            executions, context
                        )

                        # Process results and add to messages
                        for call in tool_calls:
                            func = call.get("function", {})
                            name = func.get("name")

                            if name in results:
                                result = results[name]
                                collected_chunks.extend(result.used_chunks)

                                # Find matching execution for timing
                                exec_info = next(
                                    (e for e in executions if e.tool_name == name), None
                                )

                                tool_debug.append(
                                    {
                                        "name": name,
                                        "arguments": func.get("arguments"),
                                        "returned_chunks": len(result.used_chunks),
                                        "duration_ms": round(exec_info.duration_ms, 2)
                                        if exec_info
                                        else 0,
                                        "parallel": True,
                                    }
                                )

                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": call.get("id"),
                                        "name": name,
                                        "content": json.dumps(
                                            result.content,
                                            ensure_ascii=False,
                                            default=self._json_default,
                                        ),
                                    }
                                )
                            else:
                                # Tool failed - add error message
                                exec_info = next(
                                    (e for e in executions if e.tool_name == name), None
                                )
                                error_msg = (
                                    str(exec_info.error)
                                    if exec_info and exec_info.error
                                    else "Unknown error"
                                )

                                tool_debug.append(
                                    {
                                        "name": name,
                                        "arguments": func.get("arguments"),
                                        "error": error_msg,
                                        "parallel": True,
                                    }
                                )

                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": call.get("id"),
                                        "name": name,
                                        "content": json.dumps(
                                            {"status": "error", "message": error_msg},
                                            ensure_ascii=False,
                                        ),
                                    }
                                )

                    except Exception as exc:
                        logger.error("parallel-execution-failed", error=str(exc))
                        # Fallback to sequential execution
                        logger.info("falling-back-to-sequential")
                        enable_parallel = False  # Disable for rest of this conversation
                        continue

                else:
                    # Sequential execution (original logic)
                    for call in tool_calls:
                        function = call.get("function") or {}
                        name = function.get("name")
                        arguments = function.get("arguments")

                        try:
                            result = await self._tool_registry.execute(
                                name=name,
                                arguments_json=arguments,
                                context=context,
                            )
                            collected_chunks.extend(result.used_chunks)
                            tool_debug.append(
                                {
                                    "name": name,
                                    "arguments": arguments,
                                    "returned_chunks": len(result.used_chunks),
                                    "parallel": False,
                                }
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call.get("id"),
                                    "name": name,
                                    "content": json.dumps(
                                        result.content,
                                        ensure_ascii=False,
                                        default=self._json_default,
                                    ),
                                }
                            )
                        except Exception as exc:
                            logger.error(
                                "tool-execution-error", tool=name, error=str(exc)
                            )
                            # Add error as tool result so LLM can handle it
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call.get("id"),
                                    "name": name,
                                    "content": json.dumps(
                                        {"status": "error", "message": str(exc)},
                                        ensure_ascii=False,
                                    ),
                                }
                            )

                continue

            content = message.get("content") or ""
            return content, collected_chunks, tool_debug

        raise RuntimeError("tool loop exceeded maximum iterations")

    @staticmethod
    def _json_default(obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, set):
            return list(obj)
        return str(obj)

    def _build_tool_messages(
        self,
        *,
        scenario: int,
        query: str,
        history: list[dict[str, str]],
        instructions: str,
        selected_ids: Sequence[int] | None,
        intent: str | None,
        current_datetime: str,
    ) -> list[dict[str, Any]]:
        """
        Build message list for tool-based conversation with token-aware optimization.
        Includes system prompt, guidance, history, and structured user request.
        """
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        # Adaptive guidance based on scenario and intent
        guidance = self._build_guidance_message(
            scenario=scenario,
            intent=intent,
            current_datetime=current_datetime,
        )

        # Build user request with clear structure
        user_payload = self._build_user_request(
            scenario=scenario,
            intent=intent,
            query=query,
            selected_ids=selected_ids,
            current_datetime=current_datetime,
            instructions=instructions,
        )

        # Use token-aware context manager if enabled
        use_token_aware = getattr(settings, "RAG_USE_TOKEN_AWARE_CONTEXT", True)

        if use_token_aware:
            messages, stats = self._context_manager.build_optimal_context(
                system_prompt=system_prompt,
                guidance=guidance,
                history=history,
                user_query=user_payload,
                chunks=None,  # Chunks are added by tools, not at this stage
                chunk_weight=0.4,  # More weight to history for tool conversations
            )

            logger.debug(
                "token-aware-context-built",
                total_tokens=stats.get("total_tokens", 0),
                utilization=f"{stats.get('utilization', 0) * 100:.1f}%",
                history_count=stats.get("history_count", 0),
            )

            return messages
        else:
            # Fallback to original simple truncation
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": guidance},
            ]
            messages.extend(history[-self._messages_limit :])
            messages.append({"role": "user", "content": user_payload})
            return messages

    def _build_guidance_message(
        self, *, scenario: int, intent: str | None, current_datetime: str
    ) -> str:
        """Build scenario-specific guidance for the agent."""
        base_guidance = (
            f"Текущая дата и время (UTC): {current_datetime}\n\n"
            "Ты — финансовый ассистент с доступом к инструментам поиска.\n"
            "Порядок работы:\n"
            "1. Вызови необходимые инструменты для сбора фактов\n"
            "2. Проанализируй полученную информацию\n"
            "3. Сформируй окончательный ответ\n\n"
        )

        # Add intent-specific guidance
        intent_guidance = {
            "document_search": "Используй search_user_documents для поиска в документах пользователя.",
            "knowledge_base": "Используй search_general_kb для поиска в корпоративной базе знаний.",
            "cbr_rate": "Используй fetch_cbr_data для получения курсов валют или ключевой ставки ЦБ РФ.",
            "finance_news": "Используй fetch_finance_news для поиска актуальных финансовых новостей.",
            "hybrid_kb_docs": "Используй И search_general_kb, И search_user_documents для полного ответа.",
            "full_docs": "Используй load_documents_full для загрузки полного контекста документов.",
        }

        specific = intent_guidance.get(intent or "", "")
        if specific:
            base_guidance += f"{specific}\n\n"

        base_guidance += f"Формат ответа:\n{self._answer_format_instructions()}"
        return base_guidance

    def _build_user_request(
        self,
        *,
        scenario: int,
        intent: str | None,
        query: str,
        selected_ids: Sequence[int] | None,
        current_datetime: str,
        instructions: str,
    ) -> str:
        """Build structured user request with context."""
        scenario_descriptions = {
            1: "Поиск по всем документам пользователя",
            2: "Общий запрос (корпоративная база знаний / внешние данные)",
            3: "Анализ выбранных документов (полный контекст)",
            4: "Целевой поиск в выбранных документах",
            5: "Требуется уточнение",
        }

        parts = [
            "=== КОНТЕКСТ ЗАПРОСА ===",
            f"Сценарий: {scenario} - {scenario_descriptions.get(scenario, 'Неизвестно')}",
            f"Тип запроса (intent): {intent or 'не определён'}",
            f"Выбранные документы: {list(selected_ids) if selected_ids else 'нет'}",
            f"Текущая дата/время: {current_datetime}",
            "",
            "=== ВОПРОС ПОЛЬЗОВАТЕЛЯ ===",
            query,
            "",
            "=== ИНСТРУКЦИИ К ОТВЕТУ ===",
            instructions,
        ]

        return "\n".join(parts)

    async def _load_documents(
        self, db: AsyncSession, document_ids: Sequence[int]
    ) -> tuple[list[ParsedDocument], int]:
        docs = await ParsedDocumentRepository(db).get_many_by_ids(list(document_ids))
        total_len = sum(len(d.content) for d in docs if d.content)
        return list(docs), int(total_len)

    async def _search_chunks(
        self,
        *,
        db: AsyncSession,
        user: User,
        query: str,
        document_ids: Sequence[int] | None,
        limit: int | None = None,
    ) -> list[VectorSearchResult]:
        from services.document_service import search_document_chunks

        start = time.perf_counter()
        try:
            results = await search_document_chunks(
                db=db,
                user=user,
                query=query,
                limit=limit or self._top_k,
                score_threshold=self._score_threshold,
                document_ids=document_ids,
            )
        except Exception as exc:  # pragma: no cover - network/infra issues
            logger.error("vector-search-failed", reason=str(exc))
            raise VectorSearchError("Vector search is currently unavailable") from exc
        result_list = list(results)
        duration_ms = (time.perf_counter() - start) * 1000
        self._log_retrieval_event(
            stage="user_documents",
            duration_ms=duration_ms,
            result_count=len(result_list),
            metadata={"document_ids": bool(document_ids)},
        )
        return result_list

    async def _search_with_expansion(
        self,
        *,
        db: AsyncSession,
        user: User,
        query: str,
        document_ids: Sequence[int] | None,
        history: list[dict[str, str]],
        limit: int | None = None,
    ) -> tuple[list[VectorSearchResult], dict[str, Any]]:
        from services.document_service import search_document_chunks

        plan = await self._generate_fusion_plan(
            query=query, history=history, selected_ids=document_ids
        )
        expansions = plan.expansions
        target_limit = limit or self._top_k
        if not expansions:
            plain = await self._search_chunks(
                db=db,
                user=user,
                query=query,
                document_ids=document_ids,
                limit=target_limit,
            )
            return list(plain), {
                "expansions": [],
                "strategy": "plain",
                "plan_notes": plan.priority_notes,
                "rerank": plan.rerank,
            }

        per_query = max(2, math.ceil(target_limit / len(expansions)))
        results_by_query: list[list[VectorSearchResult]] = []
        start = time.perf_counter()
        try:
            for q in expansions:
                r = await search_document_chunks(
                    db=db,
                    user=user,
                    query=q,
                    limit=per_query,
                    score_threshold=self._score_threshold,
                    document_ids=document_ids,
                )
                results_by_query.append(list(r))
        except Exception as exc:  # pragma: no cover - network/infra issues
            logger.error("vector-search-expansion-failed", reason=str(exc))
            raise VectorSearchError(
                "Expanded vector search is currently unavailable"
            ) from exc

        fused = self._rrf_merge(
            results_by_query=results_by_query, k=self._rrf_k, limit=target_limit
        )
        duration_ms = (time.perf_counter() - start) * 1000
        self._log_retrieval_event(
            stage="fusion_search",
            duration_ms=duration_ms,
            result_count=sum(len(lst) for lst in results_by_query),
            metadata={
                "expansion_count": len(expansions),
                "per_query": per_query,
                "rerank": plan.rerank,
            },
        )
        debug = {
            "expansions": expansions,
            "notes": plan.priority_notes,
            "per_query": per_query,
            "merged": len(fused),
            "rerank": plan.rerank,
            "limit": target_limit,
        }
        return fused, debug

    async def _generate_fusion_plan(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        selected_ids: Sequence[int] | None,
    ) -> FusionPlan:
        try:
            return await self._fusion_planner.plan(
                query=query, history=history, selected_ids=selected_ids
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("fusion-plan-failed", reason=str(exc))
            return FusionPlan(
                base_query=query,
                refinements=[],
                subqueries=[],
                priority_notes="fallback-plan",
                rerank=False,
            )

    def _get_predefined_response(self, intent: str, query: str) -> str:
        """
        Return predefined responses for small_talk and off_topic intents.
        These responses are hardcoded as per system prompt requirements.
        """
        query_lower = query.lower().strip()

        if intent == "small_talk":
            # Check for greetings
            greetings = {
                "привет",
                "здравствуй",
                "добрый день",
                "добрый вечер",
                "доброе утро",
                "hi",
                "hello",
            }
            if any(greeting in query_lower for greeting in greetings):
                return (
                    "Здравствуйте! Я ваш финансовый ассистент. Могу помочь с анализом документов, "
                    "поиском информации в корпоративной базе знаний, актуальными данными по курсам валют "
                    "и финансовым новостям. Чем могу быть полезен?"
                )

            # Check for identity/capabilities questions
            identity_triggers = {
                "кто ты",
                "что ты",
                "что ты умеешь",
                "расскажи о себе",
                "твои возможности",
            }
            if any(trigger in query_lower for trigger in identity_triggers):
                return (
                    "Я — финансовый ассистент вашей компании. Мои возможности:\n"
                    "• Анализ ваших документов и поиск нужной информации\n"
                    "• Ответы на вопросы по корпоративной базе знаний\n"
                    "• Актуальные курсы валют и ключевая ставка ЦБ РФ\n"
                    "• Последние финансовые новости\n\n"
                    "Просто задайте вопрос или загрузите документы для анализа."
                )

            # Generic small talk fallback
            return (
                "Здравствуйте! Я специализируюсь на финансовых и бизнес-вопросах. "
                "Могу помочь с анализом документов, поиском информации и актуальными данными. "
                "Чем могу быть полезен?"
            )

        elif intent == "off_topic":
            return (
                "Извините, но я специализируюсь на финансовых и бизнес-вопросах. "
                "Могу помочь с анализом документов, финансовой информацией, данными по рынку "
                "и корпоративной базой знаний. Пожалуйста, задайте вопрос в этой области."
            )

        # Fallback
        return "Пожалуйста, уточните ваш вопрос."

    @staticmethod
    def _bias_news_query(query: str) -> str:
        base = query.strip()
        if not base:
            return "финансовые новости России"
        normalized = base.lower()
        if "россия" in normalized or "рф" in normalized:
            return base
        return f"{base} Россия"

    def _prioritize_news_results(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not results:
            return []

        deduped: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for item in results:
            url = (item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            deduped.append(item)

        russian: list[dict[str, Any]] = []
        global_: list[dict[str, Any]] = []
        for item in deduped:
            if self._is_russian_source(item):
                russian.append(item)
            else:
                global_.append(item)
        return russian + global_

    def _is_russian_source(self, item: dict[str, Any]) -> bool:
        url = (item.get("url") or "").strip()
        hostname = ""
        if url:
            try:
                hostname = urlparse(url).hostname or ""
            except ValueError:
                hostname = ""
        hostname = hostname.lower()
        if any(hostname.endswith(domain) for domain in self._preferred_news_domains):
            return True

        snippet = (
            f"{item.get('title', '')} {item.get('content', '')}".lower()
        )
        return any("а" <= ch <= "я" or ch == "ё" for ch in snippet)

    def _answer_format_instructions(self) -> str:
        """
        Return adaptive format instructions based on query complexity.
        These are general instructions - specific formatting is in system prompt.
        """
        return (
            "Адаптируй формат ответа под сложность вопроса:\n"
            "- Простой вопрос: краткий прямой ответ (1-3 абзаца).\n"
            "- Средней сложности: структура с разделами 'Ответ' и 'Источники'.\n"
            "- Сложный вопрос: полная структура с 'Краткий вывод', 'Подробный анализ', 'Источники'.\n"
            "\nИсточники указывай строго в формате:\n"
            "- [Название файла](URL) — для документов пользователя\n"
            "- [Финансовая база знаний] — для корпоративной БЗ\n"
            "- [cbr.ru] — для данных ЦБ РФ\n"
            "- [Название статьи](URL) — для веб-поиска\n"
            "\nНЕ используй технические термины типа 'Tavily API', 'чанк', 'векторный поиск'."
        )

    def _rrf_merge(
        self, *, results_by_query: list[list[VectorSearchResult]], k: int, limit: int
    ) -> list[VectorSearchResult]:
        # Reciprocal Rank Fusion across multiple query result lists
        rank_maps: list[dict[int, int]] = []
        for lst in results_by_query:
            rank_map: dict[int, int] = {}
            for idx, res in enumerate(lst):
                rank_map[res.chunk.chunk_id] = idx + 1  # ranks start at 1
            rank_maps.append(rank_map)

        fused_scores: dict[int, float] = {}
        best_result_for_chunk: dict[int, VectorSearchResult] = {}
        for lst in results_by_query:
            for idx, res in enumerate(lst):
                cid = res.chunk.chunk_id
                # use min rank across lists where chunk appears; sum 1/(k+rank) per list
                score_sum = fused_scores.get(cid, 0.0)
                rank = idx + 1
                score_sum += 1.0 / (k + rank)
                fused_scores[cid] = score_sum
                # keep the best scoring instance to carry payload and text
                if (
                    cid not in best_result_for_chunk
                    or res.score > best_result_for_chunk[cid].score
                ):
                    best_result_for_chunk[cid] = res

        fused = [
            (cid, score, best_result_for_chunk[cid])
            for cid, score in fused_scores.items()
        ]
        fused.sort(key=lambda x: x[1], reverse=True)
        top_results: list[VectorSearchResult] = []
        for _, _, res in fused[:limit]:
            top_results.append(res)
        return top_results

    def _resolve_instructions(self, custom_value: str | None) -> str:
        if custom_value:
            stripped = custom_value.strip()
            if stripped:
                return stripped
        return self._answer_format_instructions()

    async def _answer_with_full_context(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        documents: Sequence[ParsedDocument],
        instructions: str,
    ) -> str:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        context_parts: list[str] = []
        for idx, d in enumerate(documents, start=1):
            name = d.filename or f"Документ {d.document_id}"
            url = d.minio_url or "н/д"
            created = (
                d.created_at.isoformat() if getattr(d, "created_at", None) else "н/д"
            )
            content = d.content or ""
            link_display = (
                f"[Открыть документ]({url})" if url != "н/д" else "ссылка недоступна"
            )
            snippet = (
                f"### Документ {idx}: {name} (ID {d.document_id})\n"
                f"- Ссылка: {link_display}\n"
                f"- Дата загрузки: {created}\n"
                f"- Объём: {len(content)} символов\n\n"
                f"```markdown\n{content}\n```"
            )
            context_parts.append(snippet)
        context = "\n\n---\n\n".join(context_parts)

        user_content = (
            f"Вопрос клиента: {query}\n\n"
            f"Инструкции по ответу:\n{instructions}\n\n"
            "Ниже приведён контекст выбранных документов в формате Markdown. Используй его для ссылок и цитирования."
            f"\n\n{context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-self._messages_limit :],
            {"role": "user", "content": user_content},
        ]
        prompt_params = self._config.prompts.full_context_answer
        resp = await self._chat.chat(
            messages=messages,
            **self._prompt_kwargs(prompt_params),
        )
        return resp["choices"][0]["message"]["content"]

    async def _answer_with_chunks(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        chunks: Sequence[VectorSearchResult],
        instructions: str,
    ) -> str:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        snippets: list[str] = []
        for idx, r in enumerate(chunks, start=1):
            payload = r.payload or {}
            title = (
                payload.get("filename")
                or f"Документ {payload.get('document_id', 'н/д')}"
            )
            doc_id = payload.get("document_id")
            serial = r.chunk.chunk_serial
            url = (
                payload.get("minio_url")
                or (payload.get("document_metadata") or {}).get("minio_url")
                or "н/д"
            )
            snippet_text = r.chunk.chunk_content.strip()
            link_display = (
                f"[{title}]({url})" if url != "н/д" else f"{title} (ссылка недоступна)"
            )
            snippet_block = (
                f"### Источник {idx}: {title} (Документ {doc_id}, чанк {serial})"
                f"\n- Ссылка: {link_display}"
                f"\n- Оценка сходства: {r.score:.3f}"
                f"\n- Чанк: {serial}"
                f"\n\n```markdown\n{snippet_text}\n```"
            )
            snippets.append(snippet_block)
        context = "\n\n---\n\n".join(snippets)

        user_content = (
            f"Вопрос клиента: {query}\n\n"
            f"Инструкции по ответу:\n{instructions}\n\n"
            "Ниже приведены релевантные фрагменты документов с метаданными. Используй их и укажи ссылки на источники в формате [[Источник: …]]."
            f"\n\n{context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-self._messages_limit :],
            {"role": "user", "content": user_content},
        ]
        prompt_params = self._config.prompts.chunk_answer
        resp = await self._chat.chat(
            messages=messages,
            **self._prompt_kwargs(prompt_params),
        )
        return resp["choices"][0]["message"]["content"]

    def _vector_search_unavailable_message(self) -> str:
        return (
            "Не удалось подключиться к базе векторного поиска документов. "
            "Пожалуйста, повторите запрос чуть позже или сообщите администратору, если проблема сохраняется."
        )

    async def _answer_general(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        instructions: str,
    ) -> str:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        user_content = (
            f"Вопрос клиента: {query}\n\n"
            f"Инструкции по ответу:\n{instructions}\n\n"
            "Используй последние сообщения чата (выше) для контекста. Если источников нет, всё равно сохрани требуемую структуру и поясни отсутствие ссылок."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-self._messages_limit :],
            {"role": "user", "content": user_content},
        ]
        prompt_params = self._config.prompts.general_answer
        resp = await self._chat.chat(
            messages=messages,
            **self._prompt_kwargs(prompt_params),
        )
        return resp["choices"][0]["message"]["content"]

    async def _ask_clarification(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        clarifications: Sequence[str] | None = None,
    ) -> str:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        extra = ""
        if clarifications:
            bullets = "\n".join(f"- {c}" for c in clarifications)
            extra = (
                "Дополнительно попроси уточнить следующие моменты:\n" + bullets + "\n\n"
            )
        prompt_text = (
            "Недостаточно информации, чтобы выполнить поиск по документам. "
            "Сформулируй 1-3 уточняющих вопроса на русском, чтобы определить релевантные документы или условия. "
            "Зафиксируй вопросы в виде маркированного списка."
        )
        user_content = f"{query}\n\n{extra}{prompt_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-self._messages_limit :],
            {"role": "user", "content": user_content},
        ]
        prompt_params = self._config.prompts.clarification
        resp = await self._chat.chat(
            messages=messages,
            **self._prompt_kwargs(prompt_params),
        )
        return resp["choices"][0]["message"]["content"]

    def _prompt_kwargs(self, params: PromptParams) -> dict[str, Any]:
        return {
            "temperature": params.temperature,
            "top_p": params.top_p,
            "max_tokens": params.max_tokens,
        }

    async def _search_knowledge_base(
        self, *, query: str, limit: int | None = None
    ) -> list[VectorSearchResult]:
        if not query.strip():
            return []
        kb_settings = self._kb_settings
        if not self._kb_embeddings.is_enabled or not self._kb_store.is_enabled:
            return []

        try:
            start = time.perf_counter()
            embeddings = await self._kb_embeddings.embed_texts([query])
        except Exception as exc:  # pragma: no cover
            logger.warning("kb-embedding-failed", reason=str(exc))
            return []

        if not embeddings:
            return []

        filter_conditions = [
            FieldCondition(
                key="document_metadata.source", match=MatchValue(value="knowledge_base")
            )
        ]

        start = time.perf_counter()
        try:
            points = await self._kb_store.search_document_embeddings(
                user_id=kb_settings.user_id,
                query_embedding=embeddings[0],
                limit=limit or kb_settings.limit,
                score_threshold=kb_settings.score_threshold,
                extra_filter_conditions=filter_conditions,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("kb-search-failed", reason=str(exc))
            return []

        results: list[VectorSearchResult] = []
        for point in points:
            payload = getattr(point, "payload", {}) or {}
            chunk_id = payload.get("chunk_id") or getattr(point, "id", None) or 0
            chunk_serial = payload.get("chunk_serial") or 0
            chunk_content = payload.get("chunk_content") or (
                (payload.get("document_metadata") or {}).get("kb_annotation") or ""
            )
            chunk = SimpleNamespace(
                chunk_id=chunk_id,
                chunk_serial=chunk_serial,
                chunk_content=str(chunk_content),
            )
            results.append(
                VectorSearchResult(
                    chunk=chunk,
                    score=getattr(point, "score", 0.0),
                    payload=payload,
                )
            )
        duration_ms = (time.perf_counter() - start) * 1000
        self._log_retrieval_event(
            stage="knowledge_base",
            duration_ms=duration_ms,
            result_count=len(results),
            metadata={"collection": kb_settings.collection_name},
        )
        return results

    def _log_retrieval_event(
        self,
        *,
        stage: str,
        duration_ms: float,
        result_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "stage": stage,
            "duration_ms": round(duration_ms, 2),
            "result_count": result_count,
        }
        if metadata:
            payload.update(metadata)
        logger.info("rag-retrieval", **payload)

    @staticmethod
    def _coerce_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return None

    async def _tool_search_user_documents(
        self, invocation: ToolInvocation, context: ToolContext
    ) -> ToolResult:
        query = invocation.arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query is required for search_user_documents")
        document_ids = invocation.arguments.get("document_ids")
        if not document_ids:
            document_ids = context.selected_document_ids
        limit = invocation.arguments.get("limit")
        parsed_limit = int(limit) if isinstance(limit, int) else None

        requested_expansion = self._coerce_bool(
            invocation.arguments.get("use_query_expansion")
        )
        context_flag = (
            context.use_query_expansion
            if isinstance(context.use_query_expansion, bool)
            else None
        )
        default_flag: bool | None = None
        if context.intent in {"document_search", "hybrid_kb_docs"} or context.scenario in {
            1,
            2,
            4,
        }:
            default_flag = self._default_use_query_expansion

        should_expand = next(
            (
                flag
                for flag in (requested_expansion, context_flag, default_flag)
                if flag is not None
            ),
            False,
        )

        results: list[VectorSearchResult]
        search_meta: dict[str, Any] = {
            "strategy": "single_query",
            "limit": parsed_limit or self._top_k,
        }

        if should_expand:
            expanded, extra = await self._search_with_expansion(
                db=context.db,
                user=context.user,
                query=query,
                document_ids=list(document_ids or []) or None,
                history=context.history,
                limit=parsed_limit,
            )
            results = expanded
            search_meta = {
                "strategy": "query_expansion",
                "expansions": extra.get("expansions", []),
                "notes": extra.get("notes"),
                "per_query": extra.get("per_query"),
                "limit": extra.get("limit", parsed_limit or self._top_k),
            }
        else:
            results = await self._search_chunks(
                db=context.db,
                user=context.user,
                query=query,
                document_ids=list(document_ids or []) or None,
                limit=parsed_limit or self._top_k,
            )

        chunks_payload = [self._serialize_chunk(r) for r in results]
        return ToolResult(
            content={
                "status": "ok",
                "chunks": chunks_payload,
                "query": query,
                "meta": search_meta,
                "use_query_expansion": should_expand,
            },
            used_chunks=list(results),
        )

    async def _tool_load_documents_full(
        self, invocation: ToolInvocation, context: ToolContext
    ) -> ToolResult:
        document_ids = invocation.arguments.get("document_ids")
        if not document_ids:
            document_ids = context.selected_document_ids
        if not document_ids:
            raise ValueError("document_ids are required for load_documents_full")
        documents, total_len = await self._load_documents(context.db, document_ids)
        max_chars = invocation.arguments.get("max_chars")
        max_chars = (
            int(max_chars) if isinstance(max_chars, int) else self._max_context_chars
        )
        trimmed_docs: list[dict[str, Any]] = []
        remaining = max_chars
        for doc in documents:
            content = (doc.content or "")[: max(0, remaining)]
            remaining = max(0, remaining - len(content))
            trimmed_docs.append(
                {
                    "document_id": doc.document_id,
                    "filename": doc.filename,
                    "url": doc.minio_url,
                    "content": content,
                    "created_at": getattr(doc, "created_at", None),
                }
            )
            if remaining <= 0:
                break
        return ToolResult(
            content={
                "status": "ok",
                "documents": trimmed_docs,
                "total_length": total_len,
            }
        )

    async def _tool_search_general_kb(
        self, invocation: ToolInvocation, context: ToolContext
    ) -> ToolResult:
        query = invocation.arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query is required for search_general_kb")
        raw_limit = invocation.arguments.get("limit")
        limit = int(raw_limit) if isinstance(raw_limit, int) else None
        results = await self._search_knowledge_base(
            query=query, limit=min(limit, 10) if limit else None
        )
        payload = [self._serialize_chunk(r) for r in results]
        return ToolResult(
            content={"status": "ok", "chunks": payload, "query": query},
            used_chunks=list(results),
        )

    def _serialize_chunk(self, result: VectorSearchResult) -> dict[str, Any]:
        payload = result.payload or {}
        metadata = payload.get("document_metadata") or {}
        return {
            "document_id": payload.get("document_id"),
            "filename": payload.get("filename") or metadata.get("kb_id"),
            "url": payload.get("minio_url") or metadata.get("minio_url"),
            "score": result.score,
            "chunk_serial": result.chunk.chunk_serial,
            "content": result.chunk.chunk_content,
            "source": metadata.get("source") or payload.get("source"),
        }

    async def _tool_fetch_cbr_data(
        self, invocation: ToolInvocation, context: ToolContext
    ) -> ToolResult:
        mode = invocation.arguments.get("mode")
        if mode not in {"key_rate", "currency", "news"}:
            raise ValueError("mode must be one of key_rate|currency|news")
        payload = {
            "date": invocation.arguments.get("date"),
            "code": invocation.arguments.get("code"),
            "history": context.history,
        }
        response = await self._cbr_client.fetch(mode=mode, payload=payload)
        return ToolResult(content=response)

    async def _tool_fetch_finance_news(
        self, invocation: ToolInvocation, context: ToolContext
    ) -> ToolResult:
        query = invocation.arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query is required for fetch_finance_news")

        max_results = invocation.arguments.get("max_results")
        days = invocation.arguments.get("days")

        target_results = int(max_results) if isinstance(max_results, int) else 5
        window_days = int(days) if isinstance(days, int) else 7

        ru_query = self._bias_news_query(query)
        ru_response = await self._tavily_client.search(
            query=ru_query,
            max_results=target_results,
            search_depth="advanced",
            topic="news",
            days=window_days,
            include_domains=list(self._preferred_news_domains),
            include_answer=True,
        )
        ru_results = ru_response.get("results", [])

        combined_results = self._prioritize_news_results(ru_results)
        meta: dict[str, Any] = {
            "query": query,
            "ru_query": ru_query,
            "ru_results": len(ru_results),
            "preferred_domains": list(self._preferred_news_domains),
        }
        status = ru_response.get("status", "ok")
        cached = bool(ru_response.get("cached", False))

        if len(combined_results) < target_results:
            fallback_query = f"{query} финансы Россия"
            fallback = await self._tavily_client.search(
                query=fallback_query,
                max_results=target_results,
                search_depth="advanced",
                topic="news",
                days=window_days,
                include_answer=True,
            )
            fallback_results = fallback.get("results", [])
            meta["fallback_results"] = len(fallback_results)
            meta["fallback_query"] = fallback_query
            combined_results = self._prioritize_news_results(
                ru_results + fallback_results
            )
            status = fallback.get("status", status)
            cached = cached and bool(fallback.get("cached", False))

        final_results = combined_results[:target_results]
        meta["returned"] = len(final_results)

        return ToolResult(
            content={
                "status": status,
                "results": final_results,
                "cached": cached,
                "meta": meta,
            }
        )

    def _build_tool_registry(self) -> ToolRegistry:
        definitions = [
            ToolDefinition(
                name="search_user_documents",
                description=(
                    "Выполняет поиск релевантных фрагментов в документах пользователя."
                    " Требует текст запроса. Необходим для сценариев 1 и 4."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Текст запроса"},
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Необязательный список ID документов для фильтра",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "description": "Максимум возвращаемых фрагментов",
                        },
                        "use_query_expansion": {
                            "type": "boolean",
                            "description": "Включить расширение запроса для повышения полноты поиска",
                        },
                    },
                    "required": ["query"],
                },
                handler=self._tool_search_user_documents,
            ),
            ToolDefinition(
                name="load_documents_full",
                description=(
                    "Загружает полный контент выбранных документов, если общий объём"
                    " не превышает лимит. Используй перед генерацией без RAG."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Список ID документов",
                        },
                        "max_chars": {
                            "type": "integer",
                            "minimum": 1000,
                            "description": "Максимальный суммарный размер контекста",
                        },
                    },
                    "required": ["document_ids"],
                },
                handler=self._tool_load_documents_full,
            ),
            ToolDefinition(
                name="search_general_kb",
                description=(
                    "Поиск в корпоративной финансовой базе знаний компании. "
                    "Используй для ответов на вопросы о терминологии, определениях, "
                    "правилах, процедурах и общих финансовых концепциях. "
                    "База знаний содержит справочную информацию по финансам и бизнес-процессам."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос для корпоративной базы знаний",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Максимум результатов (по умолчанию 5)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self._tool_search_general_kb,
            ),
            ToolDefinition(
                name="fetch_cbr_data",
                description=(
                    "Получает данные Банка России: ключевая ставка, курсы валют,"
                    " новости. Обязательно указывай mode."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["key_rate", "currency", "news"],
                        },
                        "date": {"type": "string", "description": "Формат YYYY-MM-DD"},
                        "code": {
                            "type": "string",
                            "description": "ISO 4217 или код ЦБ",
                        },
                    },
                    "required": ["mode"],
                },
                handler=self._tool_fetch_cbr_data,
            ),
            ToolDefinition(
                name="fetch_finance_news",
                description=(
                    "Поиск актуальных финансовых и экономических новостей через веб-поиск. "
                    "Используй для запросов о последних событиях, рыночных тенденциях, "
                    "новостях компаний и экономической ситуации. "
                    "Возвращает заголовки, ссылки и краткое содержание статей."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос для финансовых новостей",
                        },
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 5,
                            "description": "Количество новостей для возврата",
                        },
                        "days": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 30,
                            "description": "Искать новости за последние N дней (опционально)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self._tool_fetch_finance_news,
            ),
        ]
        return ToolRegistry(definitions)
