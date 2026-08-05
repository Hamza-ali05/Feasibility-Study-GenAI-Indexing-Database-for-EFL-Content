# Benchmark Comparison Report

Auto-generated comparison of retrieval and CEFR classification methods for the
EFL IndexDB GenAI feasibility study.

## Dataset Summary

- **Total resources:** 29732
- **Queries evaluated (Stage 10):** 954
- **Labeled test rows (classification):** 241

### CEFR distribution

- A1: 288
- A2: 272
- B1: 205
- B2: 286
- C1: 241
- C2: 202

### Source breakdown

- (unknown): 25008
- gutenberg: 2916
- kids.frontiersin: 458
- commonlit: 296
- simple.wikipedia: 275
- wikipedia: 274
- africanstorybook: 250
- online-literature: 95
- digitallibrary: 61
- freekidsbooks: 50

## Retrieval Performance Comparison

| Method                   | P@5    |   P@10 | R@5    |   R@10 |    MAP |    MRR |   F1@10 |
|:-------------------------|:-------|-------:|:-------|-------:|-------:|-------:|--------:|
| TF-IDF Baseline          | 0.1878 | 0.221  | 0.0025 | 0.005  | 0.0951 | 0.2845 |  0.0093 |
| SBERT (all-MiniLM-L6-v2) | 0.2887 | 0.2988 | 0.0034 | 0.0063 | 0.1601 | 0.3727 |  0.0115 |
| SBERT + Metadata Filters | —      | 0.3768 | —      | 0.0106 | 0.2583 | 0.4961 |  0.0197 |
| SBERT + Metadata + RAG   | —      | 0.3768 | —      | 0.0106 | 0.2583 | 0.4961 |  0.0197 |

Artefacts: `retrieval_comparison.csv` / `.tex` / `.png`

![Retrieval bar chart](retrieval_comparison_bars.png)

### Statistical significance

- Metric: `precision_at_10` (sbert vs tfidf)
- Paired n: 954
- Paired t-test p: 8.231567202806485e-29
- Wilcoxon p: 4.2230684912938276e-24
- Cohen's d: 0.3728
- Significant at α=0.05: True

## Classification Performance Comparison

| Method                   |   Accuracy |   Precision |   Recall |   F1 (macro) |
|:-------------------------|-----------:|------------:|---------:|-------------:|
| TF-IDF Baseline          |     0.5768 |      0.6377 |   0.565  |       0.554  |
| SBERT (all-MiniLM-L6-v2) |     0.5436 |      0.5649 |   0.5291 |       0.5324 |
| SBERT + Metadata Filters |     0.5436 |      0.5649 |   0.5291 |       0.5324 |
| SBERT + Metadata + RAG   |     0.5436 |      0.5649 |   0.5291 |       0.5324 |

Artefacts: `classification_comparison.csv` / `.tex` / `.png`

![Confusion matrices](confusion_matrices.png)

## Performance Improvement Summary

Best GenAI method vs TF-IDF: **SBERT + Metadata Filters**

| Metric | Improvement % |
|--------|---------------|
| Precision@10 | +70.54 |
| Recall@10 | +112.98 |
| MAP | +171.72 |
| F1@10 | +110.70 |
| MRR | +74.40 |

### Key findings

- SBERT + Metadata Filters improves MAP by +171.7% relative to the TF-IDF baseline.
- Precision@10 improvement vs TF-IDF: +70.5%.
- F1@10 improvement vs TF-IDF: +110.7%.
- Paired t-test on per-query precision_at_10 (sbert vs tfidf, n=954): p=8.232e-29 (significant at α=0.05); Cohen's d=0.3728.

## Methodology Notes

- **Embedding model:** sentence-transformers/all-MiniLM-L6-v2 (384-d)
- **Index type:** FAISS IndexFlatIP (inner product on L2-normalised vectors ≈ cosine)
- **Baseline retrieval:** TF-IDF + cosine similarity
- **Classifier:** Logistic Regression (SBERT embeddings vs TF-IDF features)
- **Evaluation protocol:** leave-query-out style test-set retrieval; relevance =
  same `cefr_level` when labeled, else same `source_name`
- **Cut-offs:** P/R/F1 @5 and @10; MAP / MRR @10
- **Random seed:** 42
- **Per-query metrics file:** `D:/Documents/Yousaf/efl-indexdb/data/processed/10_per_query_metrics.json`

### Data sources

- `D:/Documents/Yousaf/efl-indexdb/data/processed/10_evaluation_report.json`
- `D:/Documents/Yousaf/efl-indexdb/research/experiments/experiment_log.json`
- `D:/Documents/Yousaf/efl-indexdb/data/processed/04_eda_report.json`

### Exported tables

- `retrieval_comparison.csv`
- `retrieval_comparison.tex`
- `retrieval_comparison.png`
- `classification_comparison.csv`
- `classification_comparison.tex`
- `classification_comparison.png`
- `improvement_summary.csv`
- `improvement_summary.tex`
- `improvement_summary.png`
