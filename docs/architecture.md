# EFL IndexDB — Architecture

**Project:** Feasibility Study: GenAI Indexing Database for EFL Content

This document describes how the 14-stage offline pipeline, live FastAPI services,
FAISS/SQLite stores, Anthropic RAG path, and Material Dashboard React frontend
fit together.

---

## 1. System Architecture Diagram

```text
                         ┌─────────────────────────────────────┐
                         │         Anthropic API (Claude)      │
                         │   (external — RAG + Analyzer only)  │
                         └──────────────▲──────────────────────┘
                                        │
                                        │ HTTPS (server-side key)
                                        │
┌──────────┐   ┌────────────────────┐   │   ┌──────────────────────────────┐
│ Datasets │──▶│  14-stage Pipeline │───┼──▶│  Artefacts / Stores          │
│ data/raw │   │  backend/pipeline  │   │   │                              │
└──────────┘   │  Discover → … →    │   │   │  FAISS IndexFlatIP           │
               │  Predict           │───┼──▶│  data/embeddings/*.bin       │
               └────────────────────┘   │   │                              │
                                        │   │  SQLite Metadata             │
                                        │   │  data/processed/metadata.db  │
                                        │   │                              │
                                        │   │  SQLite Analytics            │
                                        │   │  data/processed/analytics.db │
                                        │   └──────────────▲───────────────┘
                                        │                  │
                                        │                  │ read / write
                                        │                  │
                         ┌──────────────┴──────────────────┴───────────────┐
                         │              FastAPI (backend/api)              │
                         │                                                 │
                         │  REST  /api/search  /api/qa  /api/recommend …   │
                         │  WS    /ws/pipeline                             │
                         │  SSE   /api/qa/ask-stream                       │
                         │                                                 │
                         │  Services: rag_service, analyzer_service,       │
                         │  recommend_service, duplicate_service, …        │
                         └──────────────────────▲──────────────────────────┘
                                                │
                                                │ HTTP / WS
                                                │
                         ┌──────────────────────┴──────────────────────────┐
                         │   Material Dashboard React (frontend/)          │
                         │   CRA · MUI · Axios · Chart.js · WS client      │
                         └─────────────────────────────────────────────────┘
```

Anthropic is **not** on the critical path for search, browse, metrics, or
pipeline training. It is called only from `rag_service` (Ask AI) and optionally
from `analyzer_service` (LLM classify). Missing `ANTHROPIC_API_KEY` yields a
clear error or CEFR-only fallback — never a fabricated LLM answer.

---

## 2. Pipeline Stage Dependency Graph

Each stage consumes artefacts from the previous stage (and shared config).
Linear chain:

```text
Discover
   │  01_discover_manifest.json
   ▼
Load
   │  02_loaded.parquet
   ▼
Integrate
   │  03_integrated.parquet + MetadataStore upsert
   ▼
EDA
   │  04_eda_report.json + eda_plots/*.png
   ▼
Clean
   │  05_cleaned.parquet
   ▼
Split
   │  splits/{train,val,test}/*.parquet
   ▼
Preprocess
   │  embeddings/*.npy + *_ids.json
   ▼
Balance
   │  balanced_train.parquet (+ balanced embeddings)
   ▼
Train
   │  FAISS index + LR/TF-IDF models + duplicate_candidates.json
   ▼
Evaluate
   │  10_evaluation_report.json
   ▼
Explain Global ──▶ Explain Local ──▶ Explain Quality
   │                  │                   │
   │ SHAP report      │ LIME report       │ quality report
   ▼                  ▼                   ▼
Predict
   └── demo retrieval / CEFR predict report
```

`pipeline_state.json` tracks `PENDING | RUNNING | COMPLETE | FAILED` per stage
and is broadcast over WebSockets for the Pipeline Monitor UI.

---

## 3. Embedding Pipeline Detail

Used by Stage 07 Preprocess, live Search/RAG/Recommend, and the Analyzer.

```text
  raw_text (cleaned string)
        │
        ▼
  SBERT tokeniser          (WordPiece / model tokenizer)
        │
        ▼
  Transformer encoder      (all-MiniLM-L6-v2 by default)
        │
        ▼
  Pooling                  (sentence embedding, typically mean-pool)
        │
        ▼
  L2 normalisation         (unit vector — SBERTEmbedder.embed*)
        │
        ▼
  float32 vector (dim D)
        │
        ├──▶ FAISS IndexFlatIP.add / search   (Train + Analyzer add_single)
        └──▶ LogisticRegression CEFR clf      (Train / Evaluate / query CEFR)
```

Inner product on L2-normalised vectors ≈ **cosine similarity**. That is why
every path that writes or queries FAISS normalises before indexing/search.

---

## 4. CEFR Classification Flow

```text
  Query text  ──embed──▶  query_vec (L2-normalised)
                                │
                                ▼
                   LogisticRegression (SBERT features)
                   sbert_lr_classifier.joblib
                                │
                                ▼
                      predicted CEFR ∈ {A1…C2}
```

- **Search:** optional `query_cefr_prediction` attached to the response for UI hints.
- **Analyzer (no Anthropic key):** same LR used as CEFR-only fallback;
  `skill_type` / `topic_domain` left null with `classify_manually=true`.
- **TF-IDF baseline:** parallel LR on TF-IDF features for Evaluate comparison only.

---

## 5. Search Flow

```text
  User query (Search page)
        │
        ▼
  POST /api/search
        │
        ├─▶ require pipeline_ready (Predict COMPLETE)
        │
        ▼
  SBERTEmbedder.embed_single(query)
        │
        ▼
  FAISSVectorStore.search(query_vec, top_k' )     # over-fetch
        │                                         # skip tombstoned ids
        ▼
  MetadataStore.get_by_ids(hit ids)
        │
        ▼
  Smart Filters: keep rows matching cefr_level /
                 skill_type / topic_domain (if set)
        │
        ▼
  Ranked SearchResult[] (similarity_score, tags, …)
        │
        ▼
  AnalyticsStore.log_search(...)  +  WS search_event
```

Suggest / facets are separate cheap metadata queries (`GET /api/search/suggest`,
`GET /api/search/facets`) and do not require FAISS.

---

## 6. RAG Flow

```text
  Question (Ask AI page)
        │
        ▼
  POST /api/qa/ask  or  GET /api/qa/ask-stream (SSE)
        │
        ├─▶ Config.require(ANTHROPIC_API_KEY)   # else clear 4xx / stream error
        │
        ▼
  retrieve_context:
        embed question → FAISS top-k → attach metadata snippets
        │
        ▼
  build_prompt(question, contexts)
        │   (instruct: answer ONLY from indexed excerpts; cite titles)
        ▼
  Anthropic messages.create / messages.stream
        │
        ▼
  Answer text + sources[{resource_id, title, snippet, score, cefr}]
```

Streaming path emits sources first (`type: done`), then tokens (`type: token`),
then `type: complete`. Billing / auth failures are mapped to explicit errors;
the service never invents an answer when the model call fails.

---

## 7. Live Ingestion Flow (AI Resource Analyzer)

```text
  Upload / paste  (POST /api/analyzer/upload)
        │
        ├─▶ require Train COMPLETE (FAISS must exist)
        │
        ▼
  clean_text()                 # shared with Stage 05 rules
        │
        ▼
  classify                     # Anthropic JSON labels OR CEFR LR fallback
        │
        ▼
  embed_single(cleaned)
        │
        ▼
  find_near_duplicate(emb)     # FAISS neighbours ≥ threshold
        │
        ├─ if dup and not force:
        │      WS duplicate_flag
        │      return { indexed:false, duplicate_of }
        │
        └─ if force or no dup:
               FAISSVectorStore.add_single(emb, new_id)  # save_index()
               MetadataStore.upsert_one(...)
               link_faiss(new_id, row)
               WS pipeline-style progress (Resource Analyzer steps)
               return { indexed:true, resource_id, … }
```

`POST /api/analyzer/confirm-duplicate` sets `force=true` after the UI dialog.

---

## 8. Real-Time Architecture

### Backend

- `ConnectionManager` in `backend/api/websocket_manager.py` holds active
  `/ws/pipeline` sockets.
- Pipeline stages and services may run **off** the asyncio loop (subprocess /
  thread). Broadcast helpers use `asyncio.run_coroutine_threadsafe` against the
  loop captured at startup / first connect.
- Keep-alive: server waits ~25s for client text; responds to `ping`/`pong`.

### Event types

| `type` | Emitter | Purpose |
|--------|---------|---------|
| `connected` | WS accept | Channel handshake |
| `pipeline_update` | Stages / Analyzer progress | Stage name, status, `progress_pct` |
| `search_event` | `analytics_service` after search log | Query + `result_count` for Dashboard feed |
| `duplicate_flag` | Analyzer near-dup block | Pair ids + similarity |
| `duplicates_update` | Resolve / rescan | Pending candidate count |

### Frontend reconnect / backoff

`frontend/src/services/socket.js` (`connectPipelineSocket`):

- On unexpected close → schedule reconnect with **exponential backoff**:
  `delay = min(1000 * 2^attempt, 10000)` ms.
- Successful `onopen` resets `attempt` to 0.
- `disconnectSocket` sets `closedByUser` so unmount does not reconnect.
- Non-JSON frames (plain `pong`) are ignored; JSON messages update
  `PipelineContext` activity feed + stage snapshot (with REST status refresh).

---

## 9. Explainability Architecture

```text
  Explain Global (Stage 11)
        │
        ▼
  SHAP on CEFR classifier in embedding space
        │
        ▼
  Top contributing dimensions / feature importances
  → 11_explain_global_report.json + static plot under /static/explain/

  Explain Local (Stage 12)
        │
        ▼
  LIME on selected samples / queries
        │
        ▼
  Per-instance feature weights
  → 12_explain_local_report.json

  Explain Quality (Stage 13)
        │
        ▼
  Faithfulness · stability · bias / audit checks over explanations
  → 13_explain_quality_report.json
```

API surface: `GET /api/explain/{global,local,quality}`. Metrics UI tabs consume
these reports without re-running SHAP/LIME on every page load.

---

## 10. Deletion & Tombstoning

### Why IndexFlatIP cannot truly delete

FAISS `IndexFlatIP` is a flat matrix of vectors. It has **no** efficient
in-place remove that preserves stable row indices for the rest of the map.
Physically deleting one resource would require rebuilding the entire index
(Stage Train) — too slow for Admin / Duplicate Detection UX.

### Soft-delete workaround

```text
  deleted_b / Admin delete
        │
        ├─▶ MetadataStore.delete(id)           # gone from browse / detail
        │
        └─▶ FAISSVectorStore.tombstone(id)
                 │
                 ├─ add id to in-memory set `tombstoned`
                 └─ persist data/processed/tombstoned_ids.json

  Every search / recommend / RAG retrieve:
        FAISS returns neighbours (over-fetch)
             │
             ▼
        drop any hit whose id ∈ tombstoned
             │
             ▼
        return [{id, score}, …] up to top_k
```

- Tombstoned vectors still occupy a row on disk (id map stays consistent).
- Legacy file `data/embeddings/faiss_tombstones.json` is merged on load if present.
- A full **Train** rebuild can produce a clean index without tombstones.

---

## 11. Security & Data Privacy

### GDPR / ethics (feasibility scope)

- **No personal data in the EFL dataset itself** — `data/raw/` holds teaching /
  learning content you supply, not student identity profiles.
- **Anonymisation** — study feedback / any participant data (if collected
  outside this repo) should be anonymised before analysis.
- **Secure storage** — research artefacts and any audio/media used in related
  study procedures are intended to live on a **secure institutional server**
  under access control, not on public object storage.
- **12-month retention** — align local DBs, logs, and artefacts with the
  dissertation ethics plan; review for deletion or archival after ~12 months.
- **Informed consent** — required for human participants in usability or
  evaluation activities related to the study.

### Application controls

| Control | Implementation |
|---------|----------------|
| Admin auth | Single-admin JWT (`HS256`, fixed expiry hours) via `POST /api/admin/login` |
| Passwords | `bcrypt` hashes in `.env` (`ADMIN_PASSWORD_HASH`); plaintext never stored |
| JWT secret | `JWT_SECRET` from env via `Config.require`; never logged |
| Anthropic key | `ANTHROPIC_API_KEY` server-side only; never returned in API JSON; never written to frontend bundles; auth module does not log secrets or raw passwords |
| CORS | `CORS_ORIGIN` (default CRA `http://localhost:3000`) |
| Analytics WAL | `PRAGMA journal_mode=WAL` so dashboard reads do not block search writes |

This is an **academic prototype**: rate limiting, multi-tenant IAM, and
encryption-at-rest hardening are intentionally out of scope for the
feasibility study.

---

## Related docs

- Root [`README.md`](../README.md) — quick start, API table, metrics definitions
- [`frontend_adaptation_notes.md`](frontend_adaptation_notes.md) — Material Dashboard mapping
