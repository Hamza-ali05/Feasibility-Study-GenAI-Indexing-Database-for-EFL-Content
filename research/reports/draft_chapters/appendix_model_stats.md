# Appendix: Model Statistics

*Auto-generated appendix compiling evaluation and explainability artefacts.*

## Full classification reports

### SBERT

| Metric | Value |
| --- | --- |
| Accuracy | 0.7800 |
| Precision (macro) | 0.7600 |
| Recall (macro) | 0.7500 |
| F1 (macro) | 0.7500 |

### TF-IDF

| Metric | Value |
| --- | --- |
| Accuracy | 0.6400 |
| Precision (macro) | 0.6200 |
| Recall (macro) | 0.6100 |
| F1 (macro) | 0.6100 |


## Confusion matrices

### SBERT

| True \ Pred | A1 | A2 | B1 | B2 | C1 | C2 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 10 | 1 | 0 | 0 | 0 | 0 |
| A2 | 1 | 12 | 2 | 0 | 0 | 0 |
| B1 | 0 | 2 | 15 | 1 | 0 | 0 |
| B2 | 0 | 0 | 2 | 14 | 1 | 0 |
| C1 | 0 | 0 | 0 | 1 | 11 | 2 |
| C2 | 0 | 0 | 0 | 0 | 1 | 9 |

### TF-IDF

| True \ Pred | A1 | A2 | B1 | B2 | C1 | C2 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 8 | 2 | 1 | 0 | 0 | 0 |
| A2 | 2 | 9 | 3 | 1 | 0 | 0 |
| B1 | 1 | 3 | 11 | 3 | 1 | 0 |
| B2 | 0 | 1 | 3 | 10 | 2 | 1 |
| C1 | 0 | 0 | 1 | 2 | 8 | 3 |
| C2 | 0 | 0 | 0 | 1 | 3 | 7 |


## ROC curves and AUC values

- ROC / AUC artefacts: see `research/reports/metrics/` if exported by ResearchMetricsExporter.

## Per-query metric distributions

[PLACEHOLDER: 10 (10_per_query_metrics.json)]

## SHAP feature importance (full table from Stage 11)

[DATA NOT AVAILABLE — run stage 11]

- Faithfulness: 0.1200
- Stability: 0.8100

## LIME explanation details

[DATA NOT AVAILABLE — run stage 12]

## Complete experiment log (summary)

| ID | Name | Method | Status | MAP/P@k | Completed |
| --- | --- | --- | --- | --- | --- |
| 29c79c00 | Experiment 3: SBERT + Metadata | sbert_metadata | failed | — | 2026-08-05T11:59:59 |
| 67809dfe | Experiment 3: SBERT + Metadata | sbert_metadata | failed | 0.2583 | 2026-08-05T12:01:24 |
| 1150eca0 | Experiment 3: SBERT + Metadata | sbert_metadata | completed | 0.2583 | 2026-08-05T12:02:47 |

- Full JSON: `D:/Documents/Yousaf/efl-indexdb/research/experiments/experiment_log.json`
