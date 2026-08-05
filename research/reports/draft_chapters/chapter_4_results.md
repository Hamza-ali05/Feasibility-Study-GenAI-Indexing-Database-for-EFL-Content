# Chapter 4: Results

*Auto-generated draft. All figures and tables cite pipeline artefacts; replace placeholders after re-running missing stages.*

## 4.1 Dataset Overview

- **Number of EFL resources collected:** 29732

### Source breakdown

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

### CEFR distribution

| CEFR Level | Count |
| --- | --- |
| A1 | 288 |
| A2 | 272 |
| B1 | 205 |
| B2 | 286 |
| C1 | 241 |
| C2 | 202 |

*Figure reference:* CEFR distribution chart from Stage 04 EDA (`data/processed/plots/…`).

### Skill type distribution

| Skill | Count |
| --- | --- |
| Reading | 0 |
| Writing | 0 |
| Listening | 0 |
| Speaking | 0 |
| Grammar | 0 |
| Vocabulary | 0 |

### Topic domain distribution

| Topic | Count |
| --- | --- |
| Business | 0 |
| Science | 0 |
| Culture | 0 |
| Technology | 0 |
| Daily Life | 0 |
| Academic | 0 |
| Travel | 0 |
| Health | 0 |

## 4.2 Pipeline Execution Summary

- **Total runtime:** [PLACEHOLDER: re-run pipeline stages to record timings]

### Per-stage durations

| Stage | Status | Duration (s) | Error |
| --- | --- | --- | --- |
| Discover | COMPLETE | — |  |
| Load | COMPLETE | — |  |
| Integrate | COMPLETE | — |  |
| EDA | COMPLETE | — |  |
| Clean | COMPLETE | — |  |
| Split | COMPLETE | — |  |
| Preprocess | COMPLETE | — |  |
| Balance | COMPLETE | — |  |
| Train | COMPLETE | — |  |
| Evaluate | COMPLETE | — |  |
| Explain Global | COMPLETE | — |  |
| Explain Local | COMPLETE | — |  |
| Explain Quality | COMPLETE | — |  |
| Predict | COMPLETE | — |  |

### Re-runs / failures

- No failed stages recorded in the current pipeline state.

## 4.3 Retrieval Performance

### SBERT vs TF-IDF comparison

| Method                   | P@5   | P@10   | R@5   | R@10   | MAP    | MRR    | F1@10   |
|:-------------------------|:------|:-------|:------|:-------|:-------|:-------|:--------|
| TF-IDF Baseline          | —     | 0.55   | —     | 0.48   | 0.51   | —      | 0.51    |
| SBERT (all-MiniLM-L6-v2) | —     | 0.72   | —     | 0.61   | 0.68   | —      | 0.66    |
| SBERT + Metadata Filters | —     | 0.3768 | —     | 0.0106 | 0.2583 | 0.4961 | 0.0197  |
| SBERT + Metadata + RAG   | —     | —      | —     | —      | —      | —      | —       |

### Metric deltas

- **Δ Precision@10 (SBERT − TF-IDF):** 0.1700
- **Δ Recall@10 (SBERT − TF-IDF):** 0.1300
- **Δ MAP (SBERT − TF-IDF):** 0.1700
- **Δ F1@10 (SBERT − TF-IDF):** 0.1500

### Statistical significance

Per-query metrics unavailable. Re-run Stage 10 Evaluate to write 10_per_query_metrics.json.

*Figure X: Retrieval metrics comparison* — see `research/reports/benchmark/retrieval_comparison_bars.png` (regenerate via `BenchmarkReportGenerator.generate_full_report()`).

## 4.4 Classification Performance

| Method                   | Accuracy   | Precision   | Recall   | F1 (macro)   |
|:-------------------------|:-----------|:------------|:---------|:-------------|
| TF-IDF Baseline          | 0.64       | 0.62        | 0.61     | 0.61         |
| SBERT (all-MiniLM-L6-v2) | 0.78       | 0.76        | 0.75     | 0.75         |
| SBERT + Metadata Filters | 0.5436     | 0.5649      | 0.5291   | 0.5324       |
| SBERT + Metadata + RAG   | —          | —           | —        | —            |

### Per-class F1 scores

| CEFR | F1 |
| --- | --- |
| A1 | 0.8700 |
| A2 | 0.8000 |
| B1 | 0.8300 |
| B2 | 0.8200 |
| C1 | 0.7900 |
| C2 | 0.7500 |

### Confusion matrix analysis

Confusion matrices are available for labels ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']. See `research/reports/benchmark/confusion_matrices.png` and Appendix.

### Bias flags (explainability quality)

- skill Speaking F1=0.700 < 0.70 (at risk)

## 4.5 Explainability Analysis

### SHAP global feature importance summary

[PLACEHOLDER: 11 (SHAP global features empty — re-run Explain Global)]

- Samples explained: 50
- Embedding dim: 384

### LIME local explanation examples

[PLACEHOLDER: 12 (LIME local explanations)]

### Faithfulness and stability

- **Faithfulness score:** 0.1200
- **Stability score:** 0.8100
- **Bias threshold:** 0.7000

### Bias audit findings

- skill Speaking F1=0.700 < 0.70 (at risk)

## 4.6 Live Feature Evaluation

### RAG answer quality

- Last Predict artefact present (`14_last_predict.json`): query=reading comprehension B2 news; top_k=10.
- Qualitative RAG answer grading: see practitioner interview themes / experiment notes.

### Recommendation relevance

- Recommendation relevance (practitioner): [PLACEHOLDER: complete practitioner SUS / interviews]

### Resource Analyzer

- Classification accuracy on new uploads: Stage 10 SBERT accuracy on held-out test = 0.7800 (proxy; live Analyzer uses the same CEFR model).

### Duplicate detection

- Duplicate candidates recorded: 139
