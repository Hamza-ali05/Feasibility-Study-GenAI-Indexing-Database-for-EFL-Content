EFL IndexDB — place your datasets here
======================================

Feasibility Study: GenAI Indexing Database for EFL Content

Drop all EFL content files into this folder (data/raw/) or into
subfolders under it. The pipeline Discovery/Load stages read ONLY
what you actually place here. Nothing is downloaded, scraped, or
fabricated by the project.

If this folder is empty (apart from this README and .gitkeep), the
pipeline must fail with a clear error telling you to place datasets
here.

Supported formats
-----------------
  .csv
  .json
  .jsonl
  .txt
  .pdf

Recommended columns / fields
----------------------------
Use these names where possible so Integrate can map sources consistently
(alternate names in parentheses are also recognised later in the pipeline):

  title
  raw_text          (or: text, content, body)
  cefr_level        (or: level)
  skill_type        (or: skill)
  topic_domain      (or: topic)
  source_name
  source_url

Example open-licence sources (from the proposal)
------------------------------------------------
These are examples only — not bundled with the repo:

  - British Council Learn English
  - Cambridge English public resources
  - LibriVox

Place copies (or exports) of whatever sources you choose under
data/raw/. The pipeline will discover and load only those files.
