# Chapter 5: Evaluation and Discussion

*Auto-generated draft from evaluation artefacts and practitioner module.*

## 5.1 Technical Feasibility Assessment

- **System completed all 14 stages:** YES
  - All recorded stages are COMPLETE.
- **All live features operational:** NO
  - Gaps: RAG (Anthropic)
- **Retrieval performance meets threshold:** SBERT MAP=0.6800. This exceeds a conventional 0.5 MAP feasibility threshold used in the study protocol.

## 5.2 Practitioner Evaluation

### Participant demographics

[PLACEHOLDER: collect demographics questionnaire responses]

- Mean years experience: 0.0
- Recruited / interviewed / coded: 0 / 0 / 0

### SUS score summary

- Mean SUS: —
- SD: —
- Range: — – —
- n respondents: 0
- Adjective rating: —

### Thematic analysis findings

[PLACEHOLDER: code interviews / generate thematic map]

### Usability assessment summary

[PLACEHOLDER: SUS responses]

## 5.3 Comparison with Existing Approaches

### Performance improvement over TF-IDF baseline

| Metric       |   Improvement % |
|:-------------|----------------:|
| Precision@10 |           30.91 |
| Recall@10    |           27.08 |
| MAP          |           33.33 |
| F1@10        |           29.41 |
| MRR          |          nan    |
| Accuracy     |           21.88 |

### Positioning against the literature

- Dense retrieval with SBERT is expected to outperform sparse TF-IDF on semantic EFL queries; confirm against the literature review gaps (domain-specific CEFR resources, practitioner UX).
- Metadata-filtered retrieval and RAG remain partially evaluated — see experiment log for completed variants.

## 5.4 Limitations

- **Dataset size / coverage:** EDA reports 29732 resources; proposal noted a smaller curated subset for early feasibility — discuss generalisability carefully.
- **Single embedding model tested:** all-MiniLM-L6-v2 (384-d); larger multilingual models not compared.
- **Practitioner sample size:** target n=6–8; actual interviewed = 0.
- **Prototype scope vs production:** offline pipeline + FastAPI prototype; not a hardened multi-tenant production deployment.

## 5.5 Ethical and Security Considerations

### GDPR compliance summary

- Practitioner data uses pseudonyms; withdrawal purges transcripts/codes (see `research/practitioner_eval`).
- Admin JWT protects mutation endpoints; search is read-oriented.
- See `docs/architecture.md` §11 for the controls table.

### Algorithmic bias findings

- skill Speaking F1=0.700 < 0.70 (at risk)

### Security evaluation results

- [PLACEHOLDER: Phase 16 security evaluation (not yet available)]
