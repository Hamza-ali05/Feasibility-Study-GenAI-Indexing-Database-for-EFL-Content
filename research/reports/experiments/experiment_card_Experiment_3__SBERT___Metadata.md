# Experiment Card: Experiment 3: SBERT + Metadata

**ID:** `1150eca0-aaa1-4676-9e90-b8b45f856777`  
**Status:** completed  
**Started:** 2026-08-05T12:02:05.005405+00:00  
**Completed:** 2026-08-05T12:02:47.360391+00:00  

Test retrieval with metadata post-filters

## Configuration

| Parameter | Value |
| --- | --- |
| Retrieval method | `sbert_metadata` |
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| Classifier | logistic_regression |
| FAISS index | IndexFlatIP |
| Metadata filters | True |
| RAG enabled | False |
| top_k | 10 |
| random_seed | 42 |

## Dataset

| Split | Size |
| --- | ---: |
| Total | 27077 |
| Train | 18953 |
| Val | 4062 |
| Test | 4062 |
| Dataset hash | `a1e085127bd633e7` |

## Results

### Retrieval

| Metric | Value |
| --- | ---: |
| P@k | 0.3768343815513627 |
| R@k | 0.010589163590276703 |
| MAP | 0.25829115503643807 |
| F1@k | 0.019668977550447598 |
| MRR | 0.4960887324881036 |

### Classification

| Metric | Value |
| --- | ---: |
| Accuracy | 0.5435684647302904 |
| Precision (macro) | 0.5649150654413811 |
| Recall (macro) | 0.5290628599139237 |
| F1 (macro) | 0.5324167981368793 |

### Confusion matrix

```
  34     9     0     2     0     0
   9    29     3     1     0     0
   2     3    10    20     3     1
   0     4     3    28    10     2
   0     0     2    17    11     3
   0     0     1     4    11    19
```

### Per-class F1

| Class | F1 |
| --- | ---: |
| A1 | 0.7556 |
| A2 | 0.6667 |
| B1 | 0.3448 |
| B2 | 0.4706 |
| C1 | 0.3235 |
| C2 | 0.6333 |

## Environment

```json
{
  "note": "reproducibility module (Phase 12) not available; environment snapshot deferred",
  "captured_at": "2026-08-05T12:02:47.360987+00:00"
}
```

## Notes

_None._
