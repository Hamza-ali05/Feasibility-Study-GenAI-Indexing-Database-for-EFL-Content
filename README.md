# EFL IndexDB

**Feasibility Study: GenAI Indexing Database for EFL Content**

---

## 1. Project Overview

This repository is an academic feasibility prototype for a generative-AI-assisted indexing database that discovers, cleans, embeds, and retrieves English as a Foreign Language (EFL) learning resources using sentence embeddings, vector search, CEFR-aware classification, and explainability tooling. The study evaluates whether SBERT/FAISS semantic retrieval — compared with classical TF-IDF baselines under realistic pipeline and UI constraints — can support discovery and organisation of EFL content at a quality and operational cost suitable for a small-scale research deployment.

---

## 2. Research Question

Can a generative-AI-assisted indexing database — combining sentence embeddings, vector search, CEFR-aware classification, and explainability — feasibly support discovery and organisation of English as a Foreign Language (EFL) learning resources at a quality and operational cost suitable for a small-scale academic prototype, and what design trade-offs emerge when SBERT/FAISS retrieval is compared with classical TF-IDF baselines under realistic pipeline and UI constraints?

---

## 3. Tech Stack

| Layer | Technology |
|-------|------------|
| Backend runtime | Python 3.11+ |
| API | FastAPI |
| Real-time | WebSockets (`/ws/pipeline`), SSE (RAG stream) |
| Embeddings | SBERT (`sentence-transformers` / all-MiniLM-L6-v2) |
| Vector index | FAISS (`IndexFlatIP`, L2-normalised cosine) |
| Explainability | SHAP (global), LIME (local) |
| LLM (optional) | Anthropic API (RAG + Analyzer classification) |
| Metadata / analytics | SQLite (`metadata.db`, `analytics.db`) |
| Frontend | React 18 (Create React App) |
| UI kit | EFL IndexDB (MUI) |
| HTTP / charts | Axios, Chart.js |

---

## 4. Quick Start

### Prerequisites

- Python **3.11+**
- Node.js **18+** (npm)
- Git
- (Optional) GNU Make for `backend/Makefile` targets
- (Optional) Anthropic API key for Ask AI / Analyzer LLM classify

### Dataset setup

**Place your own EFL datasets in `data/raw/`.**  
This project does **not** ship download, scrape, or fabrication scripts. Supported formats: `.csv`, `.json`, `.jsonl`, `.txt`, `.pdf`. See `data/raw/README_PLACE_DATASETS_HERE.txt`. If `data/raw/` is empty (apart from the README / `.gitkeep`), the Discover stage fails with a clear error.

### Backend setup

```powershell
cd D:\Documents\Yousaf\efl-indexdb
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Copy environment defaults and edit secrets locally (never commit `.env`):

```powershell
copy backend\.env.example .env
# Edit .env — set JWT_SECRET, ADMIN_PASSWORD_HASH, optional ANTHROPIC_API_KEY
```

Run the API (from **repo root**, with venv active — not from `backend\`):

```powershell
cd D:\Documents\Yousaf\efl-indexdb
$env:PYTHONPATH="D:\Documents\Yousaf\efl-indexdb;D:\Documents\Yousaf\efl-indexdb\backend"
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Or use the launcher scripts (recommended on Windows):

```powershell
cd D:\Documents\Yousaf\efl-indexdb
.\start.bat
# or backend only:
.\scripts\run_backend.bat
```

Or via Make (from `backend/` — Make cds to the repo root for you):

```powershell
cd D:\Documents\Yousaf\efl-indexdb\backend
make api
```

> **Windows tip:** Running `uvicorn backend.api.main:app` while your cwd is `backend\` without `PYTHONPATH` set to the repo root raises `ModuleNotFoundError: No module named 'backend'`. Always start from the repo root (or use `run_backend.bat` / `make api`).

Run the full 14-stage pipeline after datasets are in place:

```powershell
cd D:\Documents\Yousaf\efl-indexdb\backend
make pipeline-all
```

### Frontend setup

Clone EFL IndexDB into `frontend/` (if not already present), then install and start CRA:

```powershell
cd D:\Documents\Yousaf\efl-indexdb
git clone https://github.com/creativetimofficial/material-dashboard-react.git frontend
cd frontend
npm install
npm start
```

The app defaults to [http://localhost:3000](http://localhost:3000) and expects the API at `http://localhost:8000` (see `CORS_ORIGIN` in `.env`).

> **Note:** This repo’s EFL IndexDB customisations (routes, theme, layouts, services) are layered **on top of** the cloned template. Do not scaffold a competing frontend.

### Optional: Anthropic API key (RAG / Analyzer)

In project-root `.env` (or `backend/.env`):

```env
ANTHROPIC_API_KEY=sk-ant-...
RAG_MODEL=claude-sonnet-4-6
```

Without a key, Ask AI returns a clear configuration error (no fabricated answers). The Resource Analyzer falls back to CEFR-only classification and sets `classify_manually` when skill/topic cannot be labelled by the LLM.

### Optional: Admin password hash

```powershell
cd D:\Documents\Yousaf\efl-indexdb
$env:PYTHONPATH="D:\Documents\Yousaf\efl-indexdb;D:\Documents\Yousaf\efl-indexdb\backend"
python -m backend.auth.generate_password_hash "your-chosen-password"
```

Paste the printed bcrypt hash into `.env` as `ADMIN_PASSWORD_HASH=...`, set `ADMIN_USERNAME=admin`, and set a long random `JWT_SECRET`.

---

## 5. Pipeline Stages

| # | Stage | Input | Output | Description |
|---|-------|-------|--------|-------------|
| 01 | Discover | `data/raw/**` | `01_discover_manifest.json` | Scan raw files; fail if empty |
| 02 | Load | Discover manifest | `02_loaded.parquet` | Load CSV/JSON/TXT/PDF into one frame |
| 03 | Integrate | Loaded parquet | `03_integrated.parquet`, SQLite metadata | Canonical schema + `MetadataStore` upsert |
| 04 | EDA | Integrated parquet | `04_eda_report.json`, `eda_plots/*.png` | Distributions and four charts |
| 05 | Clean | Integrated parquet | `05_cleaned.parquet` | HTML strip, NFKC, drop &lt;20 chars, truncate |
| 06 | Split | Cleaned parquet | `splits/{train,val,test}/*.parquet` | Stratified 70/15/15 |
| 07 | Preprocess | Split parquets | `*_embeddings.npy`, `*_ids.json` | SBERT batch embeddings |
| 08 | Balance | Train split + embeddings | `balanced_train.parquet` (+ emb) | Class rebalance for CEFR |
| 09 | Train | Balanced train | FAISS index, LR/TF-IDF models, dup candidates | Classifier + vector index |
| 10 | Evaluate | Test + models + FAISS | `10_evaluation_report.json` | P@10, MAP, F1, clf metrics |
| 11 | Explain Global | Trained classifier | SHAP report + plot | Global feature attributions |
| 12 | Explain Local | Samples + classifier | LIME report | Local explanations |
| 13 | Explain Quality | Eval artefacts | Quality report | Explanation quality checks |
| 14 | Predict | Query + index | Prediction report | Demo retrieval / CEFR predict |

Stage status is persisted in `data/processed/pipeline_state.json` and streamed over WebSockets for the Pipeline Monitor UI.

---

## 6. Live Feature Set

| Feature | Priority | Purpose | Primary route | Primary API endpoint(s) |
|---------|----------|---------|---------------|-------------------------|
| AI Semantic Search | ⭐⭐⭐⭐⭐ | Natural-language retrieval over FAISS | `/search` | `POST /api/search` |
| AI Question Answering (RAG) | ⭐⭐⭐⭐⭐ | Ask questions grounded in indexed excerpts | `/ask-ai` | `POST /api/qa/ask`, `GET /api/qa/ask-stream` |
| Intelligent Recommendations | ⭐⭐⭐⭐⭐ | Similar resources with diversity cap | `/recommendations/:resourceId` | `GET /api/recommend/{resource_id}` |
| Smart Filters | ⭐⭐⭐⭐ | Filter by CEFR / skill / topic | `/search` | `GET /api/search/facets`, filters on `POST /api/search` |
| AI Resource Analyzer | ⭐⭐⭐⭐ | Live clean → classify → embed → index upload | `/analyzer` | `POST /api/analyzer/upload`, `POST /api/analyzer/confirm-duplicate` |
| Dashboard | ⭐⭐⭐⭐ | Pipeline + DB monitoring | `/dashboard` | `GET /api/dashboard/summary` |
| Search Analytics | ⭐⭐⭐⭐ | Usage insights from `analytics.db` | `/analytics` | `GET /api/analytics/summary`, `GET /api/analytics/searches-per-day` |
| Duplicate Detection | ⭐⭐⭐ | Review / resolve near-duplicates | `/duplicates` | `GET /api/duplicates`, `POST /api/duplicates/resolve`, `POST /api/duplicates/rescan` |
| Document Preview | ⭐⭐⭐ | Rich resource detail + related | `/resources` (detail modal/page) | `GET /api/resources/{id}`, `GET /api/resources/{id}/view` |
| Admin Panel | ⭐⭐ | Auth, overview, manage, logs | `/admin/*` | `POST /api/admin/login`, `GET /api/admin/overview`, … |
| Pipeline Monitor | — | Run / reset stages with live progress | `/pipeline/*` | `GET /api/pipeline/status`, `POST /api/pipeline/run/{stage}`, `WS /ws/pipeline` |

---

## 7. API Endpoints

Auth column: **JWT** = Bearer token from `POST /api/admin/login`.

| Method | Path | Auth? | Description |
|--------|------|-------|-------------|
| GET | `/health` | No | Liveness + `pipeline_ready` |
| WS | `/ws/pipeline` | No | Live pipeline / search / duplicate events |
| POST | `/api/search` | No | Semantic search (+ Smart Filters) |
| GET | `/api/search/suggest` | No | Title autocomplete |
| GET | `/api/search/facets` | No | CEFR / skill / topic facet counts |
| GET | `/api/pipeline/status` | No | All 14 stage statuses |
| GET | `/api/pipeline/artifact/{slug}` | No | Stage report JSON artefact |
| POST | `/api/pipeline/run/{stage_name}` | JWT | Start one pipeline stage |
| POST | `/api/pipeline/run-all` | JWT | Chain all incomplete stages |
| POST | `/api/pipeline/reset/{stage_name}` | JWT | Reset one stage to PENDING |
| POST | `/api/pipeline/reset-all` | JWT | Reset all stages |
| GET | `/api/dashboard/summary` | No | Dashboard KPIs |
| GET | `/api/metrics` | No | Evaluation / metrics payload |
| GET | `/api/explain/global` | No | Global SHAP explain report |
| GET | `/api/explain/local` | No | Local LIME samples |
| GET | `/api/explain/quality` | No | Explanation quality report |
| POST | `/api/qa/ask` | No | RAG answer + sources (needs API key) |
| GET | `/api/qa/ask-stream` | No | SSE token stream for Ask AI |
| GET | `/api/recommend/{resource_id}` | No | Similar resources |
| POST | `/api/analyzer/upload` | No | Upload / paste resource for live indexing |
| POST | `/api/analyzer/confirm-duplicate` | No | Force-insert after duplicate dialog |
| GET | `/api/analytics/summary` | No | Search analytics aggregates |
| GET | `/api/analytics/searches-per-day` | No | Searches time series |
| GET | `/api/duplicates` | No | Unresolved near-duplicate pairs |
| POST | `/api/duplicates/resolve` | No | Resolve pair (`kept_both` / `merged` / `deleted_b`) |
| POST | `/api/duplicates/rescan` | No | Refresh duplicate candidates |
| GET | `/api/resources` | No | Paginated browse / admin table |
| GET | `/api/resources/{resource_id}` | No | Document preview detail |
| GET | `/api/resources/{resource_id}/view` | No | Log a resource view (204) |
| PATCH | `/api/resources/{resource_id}` | No* | Manual skill/topic labels (10-min window) |
| DELETE | `/api/resources/{resource_id}` | JWT | Delete metadata + FAISS tombstone |
| POST | `/api/admin/login` | No | Exchange username/password for JWT |
| GET | `/api/admin/me` | JWT | Current admin username |
| GET | `/api/admin/overview` | JWT | Admin home summary |
| POST | `/api/admin/pipeline/run/{stage_name}` | JWT | Admin alias: run stage |
| POST | `/api/admin/pipeline/run-all` | JWT | Admin alias: run all |
| POST | `/api/admin/pipeline/reset/{stage_name}` | JWT | Admin alias: reset stage |
| DELETE | `/api/admin/resources/{resource_id}` | JWT | Admin delete resource |
| GET | `/api/admin/logs` | JWT | Tail application log lines |
| GET | `/static/...` | No | Static processed artefacts (plots, etc.) |

\*PATCH is unauthenticated but restricted to recent analyzer-created rows and label fields only.

Interactive docs when the API is running: [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 8. Frontend Routes

From `frontend/src/routes.js` (EFL IndexDB sidenav + React Router):

| Route | Page | Description |
|-------|------|-------------|
| `/dashboard` | Dashboard | Pipeline + database monitoring |
| `/search` | Search | AI Semantic Search + Smart Filters |
| `/ask-ai` | Ask AI | RAG chat (SSE stream) |
| `/resources` | Browse Resources | Paginated catalogue + preview |
| `/recommendations/:resourceId` | Recommendations | Similar resources (contextual; hidden from sidenav) |
| `/analyzer` | Resource Analyzer | Upload / paste live ingestion |
| `/pipeline/discover` … `/pipeline/predict` | Pipeline Monitor (14) | Per-stage status, run, artefacts |
| `/metrics` | Metrics | Retrieval / classification / explain tabs |
| `/analytics` | Search Analytics | Usage charts from analytics DB |
| `/duplicates` | Duplicate Detection | Review and resolve pairs |
| `/admin/overview` | Admin Overview | Auth-gated admin home |
| `/admin/resources` | Manage Resources | Auth-gated resource table |
| `/admin/logs` | Logs | Auth-gated log tail |
| `/authentication/sign-in` | Sign In | Admin JWT login |
| `/about` | About | Static study / author page |

---

## 9. Project Structure

```text
efl-indexdb/
├── data/
│   ├── raw/                      ← YOU place datasets here (no download scripts)
│   ├── processed/                ← pipeline reports, SQLite DBs, models, plots
│   ├── embeddings/               ← SBERT .npy, FAISS index + id map
│   └── splits/{train,val,test}/
├── backend/
│   ├── api/                      ← FastAPI app, routers, WebSocket manager
│   ├── pipeline/                 ← stage_01 … stage_14
│   ├── services/                 ← RAG, recommend, analyzer, analytics, …
│   ├── db/                       ← MetadataStore, FAISSVectorStore, AnalyticsStore
│   ├── models/                   ← SBERTEmbedder singleton
│   ├── auth/                     ← JWT admin auth + password hash helper
│   ├── utils/                    ← Config, logger, pipeline_state, text_cleaning
│   ├── requirements.txt
│   ├── Makefile
│   └── .env.example
├── frontend/                     ← cloned material-dashboard-react + EFL customisations
├── notebooks/                    ← jupytext sources (01_eda, 02_tfidf, 03_sbert)
├── tests/                        ← pytest (pipeline, API, live features)
├── docs/                         ← architecture + frontend adaptation notes
├── logs/
└── README.md
```

`frontend/` is the [Creative Tim EFL IndexDB](https://github.com/creativetimofficial/material-dashboard-react) repository with EFL IndexDB routes, theme tokens, layouts, and API clients layered in — not a greenfield CRA app.

---

## 10. Evaluation Metrics

Defined in Stage 10 (`10_evaluation_report.json`) and notebooks:

| Metric | Definition (this study) |
|--------|-------------------------|
| **P@10** (`precision_at_10`) | Fraction of the top-10 retrieved IDs that are relevant |
| **R@10** (`recall_at_10`) | Fraction of all relevant IDs recovered in the top-10 |
| **MAP** (`map`) | Mean average precision over test queries (k=10) |
| **F1@10** (`f1_at_10`) | Harmonic mean of P@10 and R@10 |
| **Relevance rule** | Same `cefr_level` if labelled; else same `source_name` |
| **Accuracy** | CEFR label accuracy on labelled test rows |
| **Precision / Recall / F1 (macro)** | Macro-averaged over CEFR classes A1–C2 |
| **Δ (delta)** | SBERT metric − TF-IDF metric (positive favours SBERT) |

Retrieval engines compared: **SBERT + FAISS** vs **TF-IDF + cosine**. Classification: logistic regression on SBERT embeddings vs TF-IDF features.

---

## 11. Ethics & GDPR compliance note

This prototype is designed for academic feasibility work, not production multi-tenant SaaS.

- **No personal data in the EFL corpus itself** — indexed content is teaching / learning material you place in `data/raw/`, not student PII profiles.
- **Informed consent** — any human participants in related study activities (e.g. usability feedback) must be informed of purpose, voluntary participation, and how feedback is stored.
- **Data security** — admin access uses bcrypt password hashes and short-lived JWTs; secrets live only in local `.env` (never committed). API keys for Anthropic are optional and server-side only.
- **Retention** — research artefacts and logs are intended for a **12-month** retention window aligned with the dissertation / ethics plan, after which local copies should be reviewed for deletion or anonymised archival as required by the institution.
- **LLM calls** — when `ANTHROPIC_API_KEY` is set, question text and retrieved snippets are sent to the Anthropic API for RAG / classification; do not paste personal data into Ask AI or Analyzer uploads.

Treat operational hardening (rate limits, multi-user IAM, encryption at rest) as **out of scope** for this feasibility study.

---

## 12. Research Modules (Phases 9–16)

Academic deliverables live under `research/` and are exposed via admin-authenticated API routes and Material Dashboard pages.

| Phase | Module | Purpose | API / UI |
|-------|--------|---------|----------|
| **9** | `research/practitioner_eval/` | Interviews, SUS, thematic coding, exports | `/api/practitioner` · `/practitioner/overview`, `/practitioner/manage` |
| **10** | `research/metrics_export.py` | Publication tables (CSV / booktabs TeX / PNG) | `POST /api/metrics/export` · Metrics → “Export Publication Tables” |
| **11** | `research/experiment_tracker.py`, `run_experiment.py` | Track TF-IDF / SBERT / metadata / RAG runs | `/api/experiments` · `/experiments` |
| **12** | `research/reproducibility.py` | Environment + dataset hash snapshots; stage timings | `GET /api/pipeline/reproducibility` · Discover → Environment panel |
| **13** | `research/dissertation_figures.py` | Architecture / DFD / sequence / CEFR diagrams | `POST /api/figures/export` · `/figures` |
| **14** | `research/benchmark_report.py` | GenAI vs TF-IDF report + significance tests | CLI / `research/reports/benchmark/` |
| **15** | `research/research_report.py` | Draft dissertation chapters from live artefacts | `/api/report` · `/report` |
| **16** | `research/security_eval/` | OWASP-aligned audit + hardening | `/api/security` · `/security` · `tests/test_security.py` |

### Useful commands

```powershell
# Publication metrics
python -c "from research.metrics_export import ResearchMetricsExporter; print(ResearchMetricsExporter().export_all())"

# Dissertation figures
python -c "from research.dissertation_figures import DissertationFigureGenerator; print(DissertationFigureGenerator().export_all())"

# Benchmark markdown report
python -c "from research.benchmark_report import BenchmarkReportGenerator; print(BenchmarkReportGenerator().generate_full_report())"

# Draft chapters
python -c "from research.research_report import ResearchReportGenerator; print(ResearchReportGenerator().generate_all())"

# Security audit (API must be reachable for live probes)
python -c "from research.security_eval import SecurityAuditor; a=SecurityAuditor(); a.run_full_audit(); print(a.generate_security_report())"
```

Sensitive interview transcripts / coding stores under `research/interviews/` and `research/coding/` are gitignored; generated tables and figures under `research/reports/` are kept for the dissertation appendix.

---

## 13. References

Selected references underpinning the feasibility design (SBERT retrieval, CEFR labelling, vector search, and explainability). Consult the full dissertation / proposal PDF for the complete bibliography and citation style required by CCCU.

1. Reimers, N., & Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* EMNLP-IJCNLP.
2. Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). *BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding.* NAACL-HLT.
3. Johnson, J., Douze, M., & Jégou, H. (2019). *Billion-scale similarity search with GPUs.* IEEE Transactions on Big Data (FAISS).
4. Council of Europe. (2001 / companion volumes). *Common European Framework of Reference for Languages (CEFR).*
5. Lundberg, S. M., & Lee, S.-I. (2017). *A Unified Approach to Interpreting Model Predictions (SHAP).* NeurIPS.
6. Ribeiro, M. T., Singh, S., & Guestrin, C. (2016). *“Why Should I Trust You?” Explaining the Predictions of Any Classifier (LIME).* KDD.
7. Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS.
8. Anthropic. (2024–). *Claude API documentation* — https://docs.anthropic.com (RAG / classification integration).
9. Pedregosa, F., et al. (2011). *Scikit-learn: Machine Learning in Python.* JMLR.
10. Creative Tim. *EFL IndexDB* — https://github.com/creativetimofficial/material-dashboard-react (UI template).

---

## License / academic use

Academic prototype for **Canterbury Christ Church University** (MSc Cybersecurity feasibility study). Not a production product. EFL IndexDB retains Creative Tim’s license terms for the frontend template code.
