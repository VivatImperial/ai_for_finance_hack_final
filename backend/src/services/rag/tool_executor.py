"""Parallel tool execution with retry logic."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from services.rag.tool_registry import ToolContext, ToolRegistry, ToolResult

logger = structlog.get_logger(__name__)


@dataclass
class ToolExecution:
    """Represents a tool execution with dependencies."""

    tool_name: str
    arguments: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    result: ToolResult | None = None
    error: Exception | None = None
    duration_ms: float = 0.0


class ParallelToolExecutor:
    """Execute tools in parallel when possible, with retry logic."""

    def __init__(self, registry: ToolRegistry, max_retries: int = 2):
        self._registry = registry
        self._max_retries = max_retries

    async def execute_plan(
        self,
        executions: list[ToolExecution],
        context: ToolContext,
    ) -> dict[str, ToolResult]:
        """
        Execute tools respecting dependencies.
        Independent tools run in parallel.
        Returns dict of tool_name -> ToolResult.
        """
        if not executions:
            return {}

        results: dict[str, ToolResult] = {}
        completed: set[str] = set()
        pending = {ex.tool_name: ex for ex in executions}

        while pending:
            # Find tools ready to execute (dependencies met)
            ready = [
                ex
                for ex in pending.values()
                if all(dep in completed for dep in ex.depends_on)
            ]

            if not ready:
                # Check for circular dependency
                remaining = list(pending.keys())
                logger.error(
                    "circular-dependency-detected",
                    remaining_tools=remaining,
                    dependencies={name: ex.depends_on for name, ex in pending.items()},
                )
                raise RuntimeError(
                    f"Circular dependency in tool execution. Remaining: {remaining}"
                )

            # Execute ready tools in parallel
            logger.info(
                "executing-tools-parallel",
                count=len(ready),
                tools=[ex.tool_name for ex in ready],
            )

            tasks = {
                ex.tool_name: self._execute_with_retry(ex, context) for ex in ready
            }

            # Wait for completion
            completed_tasks = await asyncio.gather(
                *tasks.values(), return_exceptions=True
            )

            # Process results
            for tool_name, result in zip(tasks.keys(), completed_tasks):
                execution = pending[tool_name]

                if isinstance(result, Exception):
                    logger.error(
                        "tool-execution-failed",
                        tool=tool_name,
                        error=str(result),
                        error_type=type(result).__name__,
                    )
                    execution.error = result
                    # Don't add to results, but mark as completed to unblock dependents
                else:
                    results[tool_name] = result
                    execution.result = result
                    logger.info(
                        "tool-execution-success",
                        tool=tool_name,
                        duration_ms=round(execution.duration_ms, 2),
                        has_chunks=len(result.used_chunks) > 0,
                    )

                completed.add(tool_name)
                del pending[tool_name]

        return results

    async def _execute_with_retry(
        self,
        execution: ToolExecution,
        context: ToolContext,
    ) -> ToolResult:
        """Execute single tool with exponential backoff retry."""
        import json

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                start = time.perf_counter()

                result = await self._registry.execute(
                    name=execution.tool_name,
                    arguments_json=json.dumps(execution.arguments),
                    context=context,
                )

                execution.duration_ms = (time.perf_counter() - start) * 1000

                if attempt > 0:
                    logger.info(
                        "tool-retry-success",
                        tool=execution.tool_name,
                        attempt=attempt + 1,
                        duration_ms=round(execution.duration_ms, 2),
                    )

                return result

            except Exception as exc:
                last_error = exc

                if attempt < self._max_retries:
                    # Exponential backoff: 1s, 2s, 4s, etc.
                    backoff = 2**attempt
                    logger.warning(
                        "tool-execution-retry",
                        tool=execution.tool_name,
                        attempt=attempt + 1,
                        max_retries=self._max_retries,
                        backoff_seconds=backoff,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        "tool-execution-max-retries",
                        tool=execution.tool_name,
                        attempts=self._max_retries + 1,
                        final_error=str(exc),
                    )

        # All retries exhausted
        raise last_error or RuntimeError(
            f"Tool {execution.tool_name} failed without exception"
        )

    def analyze_dependencies(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[ToolExecution]:
        """
        Analyze tool calls and detect dependencies.
        Returns list of ToolExecution with depends_on populated.
        """
        import json

        executions = []
        tool_names = []

        for call in tool_calls:
            func = call.get("function", {})
            tool_name = func.get("name")
            if not tool_name:
                continue

            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            # Detect dependencies (heuristics)
            depends_on = []

            # load_documents_full depends on search results if no explicit IDs
            if tool_name == "load_documents_full":
                if (
                    not args.get("document_ids")
                    and "search_user_documents" in tool_names
                ):
                    depends_on.append("search_user_documents")

            # If multiple searches, they're independent (run in parallel)

            executions.append(
                ToolExecution(
                    tool_name=tool_name,
                    arguments=args,
                    depends_on=depends_on,
                )
            )
            tool_names.append(tool_name)

        return executions


__all__ = ["ParallelToolExecutor", "ToolExecution"]
