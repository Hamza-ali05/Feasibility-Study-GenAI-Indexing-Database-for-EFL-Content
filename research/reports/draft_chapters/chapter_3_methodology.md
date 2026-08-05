# Chapter 3: Methodology (Technical Implementation Section)

*Auto-generated draft. Section numbers (3.X) should be aligned with the final thesis outline.*

## 3.X Implementation Environment

| Item | Value |
| --- | --- |
| Python | 3.13.14 |
| OS | Windows |
| Machine | AMD64 |
| CPU count | 8 |
| GPU available | False |
| GPU device | None |
| Snapshot timestamp | 2026-08-05T15:32:15.573861+00:00 |

### Key package versions

| Package | Version |
| --- | --- |
| sentence-transformers | 5.6.1 |
| faiss-cpu | 1.15.0 |
| scikit-learn | 1.9.0 |
| pandas | 3.0.5 |
| numpy | 2.4.6 |
| shap | 0.52.0 |
| lime | 0.2.0.1 |
| anthropic | 0.120.2 |
| fastapi | 0.141.1 |
| torch | 2.13.0 |

### Hardware specifications

- Processor: Intel64 Family 6 Model 142 Stepping 12, GenuineIntel
- GPU memory (GB): —
- Random seeds: {"python_random": 42, "numpy_random": 42, "sklearn_random_state": 42}

## 3.X+1 Dataset Preparation

### Data sources and licensing

- Curated open EFL / graded-reader / public-domain text sources under `data/raw/` (see Discover manifest and dataset README for licensing notes).
- Dataset hash (raw dir): `79823fe53561a96a169c5e2e897fa943afc5a91713281300ec7e75367a79b80e`

### Data collection procedure

- Offline 14-stage pipeline: Discover → Load → Integrate → EDA → Clean → Split → Preprocess → Balance → Train → Evaluate → Explain* → Predict.
- Integration produces a unified resource table with CEFR, skill, topic, and text fields.

### Dataset statistics (EDA)

- Total resources: 29732
- Integrated rows (snapshot): 0
- Train / val / test rows: 18953 / 4062 / 4062

| Source | Count |
| --- | --- |
| (unknown) | 25008 |
| gutenberg | 2916 |
| kids.frontiersin | 458 |
| commonlit | 296 |
| simple.wikipedia | 275 |
| wikipedia | 274 |
| africanstorybook | 250 |
| online-literature | 95 |
| digitallibrary | 61 |
| freekidsbooks | 50 |

## 3.X+2 System Architecture

- Architecture diagram: `research/reports/figures/system_architecture.png` (present)
- Also: `data_flow_diagram.png`, `component_diagram.png`, `pipeline_flowchart.png`.

### Component descriptions

- **Pipeline package:** offline ETL, training, evaluation, explainability.
- **Services:** search, RAG, recommend, analyzer, duplicates, analytics.
- **Stores:** FAISS vectors, SQLite metadata, SQLite analytics.
- **Frontend:** Pipeline Monitor, Search, Insights, Admin, Practitioner Evaluation.

### Technology stack

| Layer | Technology |
| --- | --- |
| Embeddings | all-MiniLM-L6-v2 |
| Vector index | IndexFlatIP |
| Classifier | LogisticRegression |
| API | FastAPI (REST + WebSocket) |
| Frontend | Material Dashboard React |
| LLM (RAG / Analyzer) | Anthropic API |
| Metadata / Analytics | SQLite |
