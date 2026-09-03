"""
AI Question Answering (RAG) router.

POST /ask — full answer JSON. GET /ask-stream — SSE token stream for Ask AI chat.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.services import rag_service
from backend.utils import pipeline_state
from backend.utils.logger import get_logger
from backend.utils.sanitizer import sanitize_search_query

logger = get_logger("efl_indexdb.api.qa")

router = APIRouter(tags=["qa"])

class QAAskRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)

class QASource(BaseModel):
    resource_id: str
    title: str
    text_snippet: str
    similarity_score: float
    cefr_level: str | None = None
    skill_type: str | None = None
    topic_domain: str | None = None
    source_name: str | None = None

class QAAskResponse(BaseModel):
    answer: str
    sources: list[QASource]
    model: str

def _require_predict_complete() -> None:
    if not pipeline_state.is_pipeline_ready():
        raise HTTPException(
            status_code=503,
            detail="Stage Predict is not COMPLETE. Run the pipeline through Predict first.",
        )

@router.post("/ask", response_model=QAAskResponse)
def ask(body: QAAskRequest) -> QAAskResponse:
    _require_predict_complete()
    question = sanitize_search_query(body.question or "")
    if not question:
        raise HTTPException(status_code=422, detail="question must be a non-empty string")

    logger.info("POST /api/qa/ask received question=%r top_k=%s", question[:80], body.top_k)
    try:
        result = rag_service.ask(question=question, top_k=body.top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)

        if "credit balance" in detail.lower():
            raise HTTPException(status_code=402, detail=detail) from exc

        if "ANTHROPIC_API_KEY" in detail:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=503, detail=detail) from exc
    except Exception as exc:
        logger.exception("RAG ask failed")
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    return QAAskResponse(
        answer=result["answer"],
        sources=[QASource(**s) for s in result["sources"]],
        model=result["model"],
    )

@router.get("/ask-stream")
async def ask_stream(
    question: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
) -> EventSourceResponse:
    """
    Server-Sent Events for the Ask AI chat page.

    1. Emit ``type: done`` with ``sources`` (known after retrieval, before tokens).
    2. Stream answer chunks as ``type: token``.
    3. Emit ``type: complete`` when the model finishes.
    """
    _require_predict_complete()
    q = question.strip()
    if not q:
        raise HTTPException(status_code=422, detail="question must be a non-empty string")

    try:

        contexts = rag_service.retrieve_context(q, top_k=top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    sources_payload = [
        {
            "resource_id": c["resource_id"],
            "title": c["title"],
            "text_snippet": c["text_snippet"],
            "similarity_score": c["similarity_score"],
            "cefr_level": c.get("cefr_level"),
            "skill_type": c.get("skill_type"),
            "topic_domain": c.get("topic_domain"),
            "source_name": c.get("source_name"),
        }
        for c in contexts
    ]

    async def event_generator():

        yield {
            "event": "message",
            "data": json.dumps({"type": "done", "sources": sources_payload}),
        }
        try:
            async for chunk in rag_service.ask_stream(q, top_k=top_k):
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "token", "text": chunk}),
                }
            yield {
                "event": "message",
                "data": json.dumps({"type": "complete"}),
            }
        except ValueError as exc:
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "detail": str(exc)}),
            }
        except Exception as exc:
            logger.exception("RAG stream failed")
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "detail": f"LLM stream failed: {exc}"}),
            }

    return EventSourceResponse(event_generator())
