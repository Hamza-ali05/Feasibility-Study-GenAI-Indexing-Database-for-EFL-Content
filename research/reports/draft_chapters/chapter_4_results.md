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

- **Total runtime:** 2013.9 seconds

### Per-stage durations

| Stage | Status | Duration (s) | Error |
| --- | --- | --- | --- |
| Discover | COMPLETE | 2.48 |  |
| Load | COMPLETE | 9.89 |  |
| Integrate | COMPLETE | 9.59 |  |
| EDA | COMPLETE | 3.26 |  |
| Clean | COMPLETE | 15.48 |  |
| Split | COMPLETE | 2.16 |  |
| Preprocess | COMPLETE | 1639.11 |  |
| Balance | COMPLETE | 1.57 |  |
| Train | COMPLETE | 13.35 |  |
| Evaluate | COMPLETE | 28.17 |  |
| Explain Global | COMPLETE | 2.36 |  |
| Explain Local | COMPLETE | 86.22 |  |
| Explain Quality | COMPLETE | 186.66 |  |
| Predict | COMPLETE | 13.54 |  |

### Re-runs / failures

- No failed stages recorded in the current pipeline state.

## 4.3 Retrieval Performance

### SBERT vs TF-IDF comparison

| Method                   | P@5    |   P@10 | R@5    |   R@10 |    MAP |    MRR |   F1@10 |
|:-------------------------|:-------|-------:|:-------|-------:|-------:|-------:|--------:|
| TF-IDF Baseline          | 0.1878 | 0.221  | 0.0025 | 0.005  | 0.0951 | 0.2845 |  0.0093 |
| SBERT (all-MiniLM-L6-v2) | 0.2887 | 0.2988 | 0.0034 | 0.0063 | 0.1601 | 0.3727 |  0.0115 |
| SBERT + Metadata Filters | —      | 0.3768 | —      | 0.0106 | 0.2583 | 0.4961 |  0.0197 |
| SBERT + Metadata + RAG   | —      | 0.3768 | —      | 0.0106 | 0.2583 | 0.4961 |  0.0197 |

### Metric deltas

- **Δ Precision@10 (SBERT − TF-IDF):** 0.0779
- **Δ Recall@10 (SBERT − TF-IDF):** 0.0013
- **Δ MAP (SBERT − TF-IDF):** 0.0651
- **Δ F1@10 (SBERT − TF-IDF):** 0.0021

### Statistical significance

- Paired t-test p = 0.0000 (n=954; significant@0.05=True)
- Wilcoxon p = 0.0000
- Cohen's d = 0.3728

*Figure X: Retrieval metrics comparison* — see `research/reports/benchmark/retrieval_comparison_bars.png` (regenerate via `BenchmarkReportGenerator.generate_full_report()`).

## 4.4 Classification Performance

| Method                   |   Accuracy |   Precision |   Recall |   F1 (macro) |
|:-------------------------|-----------:|------------:|---------:|-------------:|
| TF-IDF Baseline          |     0.5768 |      0.6377 |   0.565  |       0.554  |
| SBERT (all-MiniLM-L6-v2) |     0.5436 |      0.5649 |   0.5291 |       0.5324 |
| SBERT + Metadata Filters |     0.5436 |      0.5649 |   0.5291 |       0.5324 |
| SBERT + Metadata + RAG   |     0.5436 |      0.5649 |   0.5291 |       0.5324 |

### Per-class F1 scores

| CEFR | F1 |
| --- | --- |
| A1 | 0.7556 |
| A2 | 0.6667 |
| B1 | 0.3448 |
| B2 | 0.4706 |
| C1 | 0.3235 |
| C2 | 0.6333 |

### Confusion matrix analysis

Confusion matrices are available for labels ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']. See `research/reports/benchmark/confusion_matrices.png` and Appendix.

### Bias flags (explainability quality)

- CEFR B1 F1=0.345 < 0.60 (at risk)
- CEFR B2 F1=0.471 < 0.60 (at risk)
- CEFR C1 F1=0.324 < 0.60 (at risk)
- skill_type unavailable or fully null — per_skill_f1 not computed

## 4.5 Explainability Analysis

### SHAP global feature importance summary

| Feature | Importance |
| --- | --- |
| dim_80 | — |
| dim_196 | — |
| dim_381 | — |
| dim_315 | — |
| dim_48 | — |
| dim_316 | — |
| dim_265 | — |
| dim_180 | — |
| dim_68 | — |
| dim_81 | — |
| dim_260 | — |
| dim_94 | — |
| dim_208 | — |
| dim_55 | — |
| dim_107 | — |
| dim_124 | — |
| dim_98 | — |
| dim_63 | — |
| dim_367 | — |
| dim_210 | — |

- Samples explained: 1053
- Embedding dim: 384

### LIME local explanation examples

**Example 1** (`32eeb8ff-de39-41ac-9d9f-c17401adb44e`): predicted=A1, true=A1. Top features: ? (0.0201), ? (0.0181), ? (0.0176), ? (0.0170), ? (0.0163). Predicted A1 (true A1); influential approx tokens: voters(dim 255:+0.020), staff(dim 52:+0.018), vi(dim 48:+0.018), belong(dim 185:+0.017), global(dim 80:+0.016)

**Example 2** (`41533da5-3024-4e8a-8783-8a77f72ff581`): predicted=A1, true=A1. Top features: ? (0.0309), ? (0.0250), ? (0.0205), ? (0.0184), ? (0.0169). Predicted A1 (true A1); influential approx tokens: camouflage(dim 94:+0.031), multi(dim 180:+0.025), voters(dim 255:+0.020), ##vr(dim 68:+0.018), curling(dim 269:+0.017)

**Example 3** (`56dc42f3-f9e6-4bd5-a53b-fd545fdfc9d8`): predicted=A2, true=A2. Top features: ? (0.0250), ? (0.0225), ? (-0.0220), ? (0.0213), ? (0.0197). Predicted A2 (true A2); influential approx tokens: global(dim 80:+0.025), clinton(dim 382:+0.023), pr(dim 295:-0.022), ##aby(dim 188:+0.021), lu(dim 18:+0.020)

### Faithfulness and stability

- **Faithfulness score:** 0.2000
- **Stability score:** 0.6842
- **Bias threshold:** 0.6000

### Bias audit findings

- CEFR B1 F1=0.345 < 0.60 (at risk)
- CEFR B2 F1=0.471 < 0.60 (at risk)
- CEFR C1 F1=0.324 < 0.60 (at risk)
- skill_type unavailable or fully null — per_skill_f1 not computed

## 4.6 Live Feature Evaluation

### RAG answer quality

- Last Predict artefact present (`14_last_predict.json`): query=EFL reading comprehension practice; top_k=10.
- Qualitative RAG answer grading: see practitioner interview themes / experiment notes.

### Recommendation relevance

- Recommendation relevance (practitioner): [PLACEHOLDER: complete practitioner SUS / interviews]

### Resource Analyzer

- Classification accuracy on new uploads: Stage 10 SBERT accuracy on held-out test = 0.5436 (proxy; live Analyzer uses the same CEFR model).

### Duplicate detection

- Duplicate candidates recorded: 139
