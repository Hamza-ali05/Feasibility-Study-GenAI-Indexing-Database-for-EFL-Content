# EFL IndexDB — Architecture notes

## Overview

Backend FastAPI serves search, RAG, recommendations, analytics, and live
WebSocket updates over a FAISS + SQLite metadata index built by the 14-stage
pipeline under `backend/pipeline/`.

## Vector index (FAISS)

- Index type: `IndexFlatIP` on L2-normalised SBERT embeddings (cosine via inner product).
- Artefacts: `data/embeddings/faiss_index.bin`, `faiss_id_map.json`.
- Live add: `VectorStore.add_single` appends a vector and persists the id map
  (used by AI Resource Analyzer).

### Soft-delete / tombstones (Duplicate Detection)

**Limitation:** FAISS `IndexFlatIP` does **not** support true in-place vector
deletion. Removing a row would require rebuilding the entire index (stage Train).

**Approach:** When an admin resolves a duplicate with `action=deleted_b`, we:

1. Delete the row from the SQLite metadata store (`MetadataStore.delete`).
2. Add `resource_id_b` to a persisted tombstone set
   (`data/embeddings/faiss_tombstones.json`).
3. Filter tombstoned ids out of `VectorStore.search()` **after** FAISS retrieval
   (with over-fetch so `top_k` is still filled).

Tombstoned vectors still occupy a row in the on-disk index (ids stay stable for
the rest of the map). A full Train rebuild produces a clean index without
tombstones.

## Duplicate Detection

- Fast path: `data/processed/duplicate_candidates.json` from stage Train.
- Resolutions: `data/processed/duplicate_resolutions.json` so reviewed pairs are
  not re-flagged.
- Live pending count: WebSocket event `duplicates_update` with
  `duplicate_candidates_pending`.

## Analytics

- Separate SQLite DB: `data/processed/analytics.db` (`search_events`,
  `resource_views`).
