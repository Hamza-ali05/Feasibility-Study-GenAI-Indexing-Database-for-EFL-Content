"""Pydantic v2 request/response schemas for EFL IndexDB API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

class SearchQuery(BaseModel):
    query: str
    cefr_level: str | None = None
    skill_type: str | None = None
    topic_domain: str | None = None
    top_k: int = 10

class SearchResult(BaseModel):
    rank: int
    resource_id: str
    title: str
    cefr_level: str | None = None
    skill_type: str | None = None
    topic_domain: str | None = None
    source_name: str | None = None
    similarity_score: float
    tags: list[str] = Field(default_factory=list)

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    query_cefr_prediction: str | None = None
    engine: str

class StageStatusItem(BaseModel):
    name: str
    status: str
    run_at: str | None = None
    progress_pct: float | None = None
    error: str | None = None

class PipelineStatus(BaseModel):
    stages: list[StageStatusItem]
    current_stage: str
    pipeline_ready: bool

class MetricsResponse(BaseModel):
    retrieval: dict[str, Any]
    classification: dict[str, Any]
    evaluation_run_at: str | None = None
    confusion_matrix_sbert: list[list[int]] | None = None
    confusion_matrix_tfidf: list[list[int]] | None = None
    confusion_matrix_labels: list[str] | None = None

class ExplainGlobalResponse(BaseModel):
    top_features: list[dict[str, Any]]
    plot_url: str

class ExplainLocalResponse(BaseModel):
    samples: list[dict[str, Any]]

class QualityResponse(BaseModel):
    faithfulness_score: float
    stability_score: float
    bias_flags: list[str]
    per_cefr_f1: dict[str, float]

class ResourceOut(BaseModel):
    resource_id: str
    title: str
    cefr_level: str | None = None
    skill_type: str | None = None
    topic_domain: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    raw_text_preview: str
    created_at: str | None = None

class ResourceListResponse(BaseModel):
    items: list[ResourceOut]
    total: int
    page: int
    page_size: int

class ResourceDetail(ResourceOut):
    """Document Preview payload — full text + related recommendations."""

    raw_text_full: str
    related: list[dict[str, Any]] = Field(default_factory=list)
