#!/usr/bin/env python3
"""
One-off ETL script that ingests `knowledge_base/train_data.csv`, splits rows into
markdown-aware chunks, embeds them via OpenRouter, and stores vectors inside a
dedicated Qdrant collection for the internal knowledge base.

Usage:
    python kb_etl.py --collection-name knowledge_base_chunks
"""

from __future__ import annotations

import argparse
import asyncio
import ast
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Awaitable, Callable, Iterator, TypeVar


# Ensure backend modules are importable (DocumentVectorManager helpers, config, etc.)
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO_ROOT / "backend" / "src"

import sys

if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from config import settings  # type: ignore  # noqa: E402
from services.document_processing.chunk_splitter import (  # type: ignore  # noqa: E402
    ChunkSplitter,
)
from services.document_processing.models import MarkdownDocument  # type: ignore  # noqa: E402
from services.document_processing.vector_manager import (  # type: ignore  # noqa: E402
    ChunkRecord,
)
from services.embeddings.openrouter import (  # type: ignore  # noqa: E402
    OpenRouterEmbeddingClient,
)
from services.qdrant.vector_store import QdrantVectorStore  # type: ignore  # noqa: E402


DEFAULT_COLLECTION = "knowledge_base_chunks"
T = TypeVar("T")


@dataclass(frozen=True)
class KnowledgeBaseRow:
    ordinal: int
    source_id: str
    annotation: str
    tags: list[str]
    text: str

    @property
    def title(self) -> str:
        cleaned = (self.annotation or "").strip()
        return cleaned or self.source_id

    @property
    def filename(self) -> str:
        return f"{self.source_id}.md"


@dataclass(frozen=True)
class KBChunk:
    chunk_id: int
    chunk_content: str
    chunk_serial: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index KB CSV into Qdrant.")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=Path(__file__).with_name("train_data.csv"),
        help="Path to the CSV file with knowledge base articles.",
    )
    parser.add_argument(
        "--collection-name",
        default=DEFAULT_COLLECTION,
        help="Qdrant collection name for KB chunks.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1200,
        help="Target chunk size for the markdown splitter.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Overlap (characters) between chunks.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of rows to process (for testing).",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=50,
        help="Progress logging frequency (in documents).",
    )
    parser.add_argument(
        "--chunk-id-start",
        type=int,
        default=1_000_000,
        help="Starting integer for generated chunk IDs (must be positive).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Split data but skip embedding/upsert (for debugging).",
    )
    parser.add_argument(
        "--embed-retries",
        type=int,
        default=3,
        help="Number of attempts for embedding requests.",
    )
    parser.add_argument(
        "--upsert-retries",
        type=int,
        default=3,
        help="Number of attempts for Qdrant upsert requests.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="Base delay in seconds between retry attempts.",
    )
    parser.add_argument(
        "--reset-collection",
        action="store_true",
        help="Drop the target Qdrant collection before indexing.",
    )
    return parser.parse_args()


def load_rows(csv_path: Path, limit: int | None = None) -> Iterator[KnowledgeBaseRow]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for ordinal, row in enumerate(reader, start=1):
            if limit and ordinal > limit:
                break
            source_id = (row.get("id") or f"kb_{ordinal}").strip()
            annotation = (row.get("annotation") or "").strip()
            tags = parse_tags(row.get("tags"))
            text = (row.get("text") or "").strip()
            if not text:
                continue
            yield KnowledgeBaseRow(
                ordinal=ordinal,
                source_id=source_id,
                annotation=annotation,
                tags=tags,
                text=text,
            )


def parse_tags(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    cleaned = raw_value.strip()
    try:
        parsed = ast.literal_eval(cleaned)
    except (SyntaxError, ValueError):
        parsed = None
    if isinstance(parsed, (list, tuple)):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [tag.strip() for tag in cleaned.split(",") if tag.strip()]


async def run_with_retries(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    base_delay: float,
    label: str,
) -> T:
    attempts = max(1, attempts)
    delay = max(0.0, base_delay)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            sleep_for = delay * attempt if delay else 0.0
            print(
                f"[retry] {label} failed (attempt {attempt}/{attempts}): {exc}. "
                f"Retrying in {sleep_for:.1f}s..."
            )
            if sleep_for:
                await asyncio.sleep(sleep_for)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"{label} failed without exception")


def build_markdown(row: KnowledgeBaseRow) -> MarkdownDocument:
    lines = [f"# {row.title}"]
    if row.annotation:
        lines.append("")
        lines.append(row.annotation.strip())
    lines.append("")
    lines.append(row.text.strip())
    metadata = {
        "kb_id": row.source_id,
        "kb_tags": row.tags,
        "kb_row": row.ordinal,
        "source": "knowledge_base",
    }
    return MarkdownDocument(content="\n".join(lines).strip(), metadata=metadata)


async def embed_and_upsert(
    *,
    row: KnowledgeBaseRow,
    splitter: ChunkSplitter,
    embed_client: OpenRouterEmbeddingClient,
    vector_store: QdrantVectorStore,
    chunk_id_counter: int,
    collection_name: str,
    dry_run: bool,
    embed_retries: int,
    upsert_retries: int,
    retry_delay: float,
) -> tuple[int, int]:
    document = build_markdown(row)
    payloads = splitter.split(document)
    if not payloads:
        return 0, chunk_id_counter

    chunk_records: list[ChunkRecord] = []
    for payload in payloads:
        chunk_id_counter += 1
        kb_chunk = KBChunk(
            chunk_id=chunk_id_counter,
            chunk_content=payload.content,
            chunk_serial=payload.serial,
        )
        chunk_records.append(
            ChunkRecord(
                chunk=kb_chunk,
                metadata={
                    **(payload.metadata or {}),
                    "kb_serial": payload.serial,
                    "kb_collection": collection_name,
                },
            )
        )

    if dry_run:
        return len(chunk_records), chunk_id_counter

    async def _embed() -> list[list[float]]:
        return await embed_client.embed_texts(
            [record.chunk.chunk_content for record in chunk_records]
        )

    embeddings = await run_with_retries(
        _embed,
        attempts=max(1, embed_retries),
        base_delay=retry_delay,
        label="embedding",
    )
    document_stub = SimpleNamespace(
        document_id=row.ordinal,
        user_id=0,
        filename=row.filename,
        minio_url=None,
        created_at=datetime.now(timezone.utc),
    )
    async def _upsert() -> None:
        await vector_store.upsert_document_embeddings(
            document=document_stub,
            chunk_records=chunk_records,
            embeddings=embeddings,
            document_metadata={
                "kb_id": row.source_id,
                "kb_tags": row.tags,
                "kb_annotation": row.annotation,
                "kb_row": row.ordinal,
                "source": "knowledge_base",
                "collection": collection_name,
            },
        )

    await run_with_retries(
        _upsert,
        attempts=max(1, upsert_retries),
        base_delay=retry_delay,
        label="qdrant-upsert",
    )
    return len(chunk_records), chunk_id_counter


async def run_pipeline(args: argparse.Namespace) -> None:
    splitter = ChunkSplitter(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    embed_client = OpenRouterEmbeddingClient.from_settings()
    if not embed_client.is_enabled and not args.dry_run:
        raise RuntimeError(
            "OpenRouter embeddings are disabled. Set OPENROUTER_API_KEY or use --dry-run."
        )

    vector_store = QdrantVectorStore(
        url=settings.QDRANT_URL,
        collection_name=args.collection_name,
        batch_size=settings.QDRANT_BATCH_SIZE,
    )
    if not vector_store.is_enabled and not args.dry_run:
        raise RuntimeError("Qdrant is not configured (check QDRANT_URL).")

    if args.reset_collection and not args.dry_run:
        print(
            f"[{datetime.now(timezone.utc).isoformat()}] "
            f"Dropping collection {args.collection_name}..."
        )
        await vector_store.drop_collection()

    total_docs = 0
    total_chunks = 0
    chunk_id_counter = max(1, args.chunk_id_start)

    for row in load_rows(args.csv_path, limit=args.limit):
        doc_chunks, chunk_id_counter = await embed_and_upsert(
            row=row,
            splitter=splitter,
            embed_client=embed_client,
            vector_store=vector_store,
            chunk_id_counter=chunk_id_counter,
            collection_name=args.collection_name,
            dry_run=args.dry_run,
            embed_retries=args.embed_retries,
            upsert_retries=args.upsert_retries,
            retry_delay=args.retry_delay,
        )
        if doc_chunks == 0:
            continue

        total_docs += 1
        total_chunks += doc_chunks

        if total_docs % args.log_every == 0:
            print(
                f"[{datetime.now(timezone.utc).isoformat()}] "
                f"Indexed {total_docs} docs / {total_chunks} chunks."
            )

    print(
        f"Completed. Documents: {total_docs}, chunks: {total_chunks}, "
        f"collection: {args.collection_name}. Dry run: {args.dry_run}"
    )


def main() -> None:
    args = parse_args()
    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()

