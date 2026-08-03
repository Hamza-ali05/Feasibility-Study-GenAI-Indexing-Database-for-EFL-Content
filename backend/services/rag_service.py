"""
AI Question Answering (RAG) — retrieve indexed EFL context, then ask Claude.

Answers are grounded in FAISS-retrieved resources only. If
``Config.ANTHROPIC_API_KEY`` is missing, callers get a clear ``ValueError``
rather than a fabricated answer.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from backend.db.metadata_store import MetadataStore
from backend.db.vector_store import get_vector_store
from backend.models.embedder import get_embedder
from backend.utils.config import Config
from backend.utils.logger import get_logger

logger = get_logger("efl_indexdb.rag")

SNIPPET_CHARS = 480


def _require_api_key() -> str:
    key = Config.ANTHROPIC_API_KEY
    if not key or not str(key).strip():
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Add it to the project-root .env file "
            "to enable AI Question Answering (RAG). No answer was fabricated."
        )
    return str(key).strip()


def _snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def retrieve_context(question: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Embed ``question``, FAISS top-k, attach metadata ``raw_text`` snippets."""
    q = (question or "").strip()
    if not q:
        return []

    k = max(1, min(int(top_k), 20))
    logger.info("RAG retrieve: loading SBERT embedder (first call can take minutes)…")
    embedder = get_embedder()
    logger.info("RAG retrieve: embedding question…")
    query_vec = embedder.encode([q], batch_size=1, show_progress_bar=False)[0]
    logger.info("RAG retrieve: querying FAISS top_k=%s…", k)
    store = get_vector_store()
    hits = store.search(query_vec, top_k=k)

    meta_by_id = MetadataStore().get_by_ids([rid for rid, _ in hits])
    contexts: list[dict[str, Any]] = []
    for resource_id, score in hits:
        meta = meta_by_id.get(resource_id)
        if meta is None:
            continue
        raw = str(meta.get("raw_text") or "")
        title = meta.get("title") or (_snippet(raw, 80) if raw else resource_id)
        contexts.append(
            {
                "resource_id": resource_id,
                "title": str(title),
                "text_snippet": _snippet(raw),
                "similarity_score": float(score),
            }
        )
    logger.info("RAG retrieve: %s context chunks", len(contexts))
    return contexts


def build_prompt(question: str, contexts: list[dict[str, Any]]) -> str:
    """Instruct the LLM to answer only from supplied EFL index context."""
    if not contexts:
        context_block = "(No indexed resources were retrieved for this question.)"
    else:
        parts: list[str] = []
        for i, ctx in enumerate(contexts, start=1):
            parts.append(
                f"[{i}] Title: {ctx.get('title')}\n"
                f"    Resource ID: {ctx.get('resource_id')}\n"
                f"    Similarity: {ctx.get('similarity_score')}\n"
                f"    Excerpt: {ctx.get('text_snippet')}"
            )
        context_block = "\n\n".join(parts)

    return (
        "You are an assistant for an EFL (English as a Foreign Language) "
        "indexing database. Answer the user's question ONLY using the indexed "
        "resource excerpts below. Do not use outside knowledge.\n\n"
        "If the excerpts are insufficient to answer, reply exactly with:\n"
        "I don't have enough information in the indexed EFL resources to answer that.\n\n"
        "When you do answer, cite the resource titles you used (e.g. according to "
        "\"Title\").\n\n"
        f"Indexed context:\n{context_block}\n\n"
        f"Question: {question.strip()}\n\n"
        "Answer:"
    )


def _raise_anthropic_error(exc: Exception) -> None:
    """Map Anthropic SDK errors to ValueError; never invent an answer."""
    msg = str(exc)
    lower = msg.lower()
    if "credit balance is too low" in lower or "purchase credits" in lower:
        raise ValueError(
            "Anthropic API credit balance is too low. "
            "Add credits at https://console.anthropic.com (Plans & Billing), "
            "then retry. No answer was fabricated."
        ) from exc
    if "invalid api key" in lower or "authentication" in lower:
        raise ValueError(
            "Anthropic API authentication failed. Check ANTHROPIC_API_KEY in .env. "
            "No answer was fabricated."
        ) from exc
    raise ValueError(f"Anthropic API request failed: {exc}") from exc


def ask(question: str, top_k: int = 5) -> dict[str, Any]:
    """Retrieve context and call Anthropic once; return answer + sources + model."""
    api_key = _require_api_key()
    model = Config.RAG_MODEL
    contexts = retrieve_context(question, top_k=top_k)
    prompt = build_prompt(question, contexts)

    try:
        from anthropic import Anthropic, APIError
    except ImportError as exc:
        raise ValueError(
            "The anthropic package is not installed. "
            "Install backend requirements to enable RAG."
        ) from exc

    client = Anthropic(api_key=api_key)
    logger.info("RAG ask: calling Anthropic model=%s…", model)
    try:
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as exc:
        logger.warning("Anthropic API error: %s", exc)
        _raise_anthropic_error(exc)

    logger.info("RAG ask: Anthropic response received")
    parts = []
    for block in message.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    answer = "".join(parts).strip() or (
        "I don't have enough information in the indexed EFL resources to answer that."
    )
    logger.info("RAG ask model=%s sources=%s", model, len(contexts))
    return {"answer": answer, "sources": contexts, "model": model}


async def ask_stream(question: str, top_k: int = 5) -> AsyncGenerator[str, None]:
    """Same grounding as ``ask``, streaming answer tokens via Anthropic."""
    api_key = _require_api_key()
    model = Config.RAG_MODEL
    contexts = retrieve_context(question, top_k=top_k)
    prompt = build_prompt(question, contexts)

    try:
        from anthropic import APIError, AsyncAnthropic
    except ImportError as exc:
        raise ValueError(
            "The anthropic package is not installed. "
            "Install backend requirements to enable RAG."
        ) from exc

    client = AsyncAnthropic(api_key=api_key)
    try:
        async with client.messages.stream(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text
    except APIError as exc:
        logger.warning("Anthropic stream API error: %s", exc)
        _raise_anthropic_error(exc)
