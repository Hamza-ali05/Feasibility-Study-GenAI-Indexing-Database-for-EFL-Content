# Appendix: Model Statistics

*Auto-generated appendix compiling evaluation and explainability artefacts.*

## Full classification reports

### SBERT

| Metric | Value |
| --- | --- |
| Accuracy | 0.5436 |
| Precision (macro) | 0.5649 |
| Recall (macro) | 0.5291 |
| F1 (macro) | 0.5324 |

### TF-IDF

| Metric | Value |
| --- | --- |
| Accuracy | 0.5768 |
| Precision (macro) | 0.6377 |
| Recall (macro) | 0.5650 |
| F1 (macro) | 0.5540 |


## Confusion matrices

### SBERT

| True \ Pred | A1 | A2 | B1 | B2 | C1 | C2 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 34 | 9 | 0 | 2 | 0 | 0 |
| A2 | 9 | 29 | 3 | 1 | 0 | 0 |
| B1 | 2 | 3 | 10 | 20 | 3 | 1 |
| B2 | 0 | 4 | 3 | 28 | 10 | 2 |
| C1 | 0 | 0 | 2 | 17 | 11 | 3 |
| C2 | 0 | 0 | 1 | 4 | 11 | 19 |

### TF-IDF

| True \ Pred | A1 | A2 | B1 | B2 | C1 | C2 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 36 | 9 | 0 | 0 | 0 | 0 |
| A2 | 13 | 28 | 0 | 1 | 0 | 0 |
| B1 | 2 | 5 | 7 | 24 | 1 | 0 |
| B2 | 0 | 4 | 2 | 32 | 8 | 1 |
| C1 | 0 | 0 | 0 | 11 | 20 | 2 |
| C2 | 0 | 0 | 0 | 2 | 17 | 16 |


## ROC curves and AUC values

- ROC / AUC artefacts: see `research/reports/metrics/` if exported by ResearchMetricsExporter.

## Per-query metric distributions

#### Method: `sbert` (n=954)

| metric          |   count |   mean |    std |   min |    25% |    50% |    75% |    max |
|:----------------|--------:|-------:|-------:|------:|-------:|-------:|-------:|-------:|
| precision_at_5  |     954 | 0.2887 | 0.2499 |     0 | 0      | 0.2    | 0.4    | 1      |
| recall_at_5     |     954 | 0.0034 | 0.0071 |     0 | 0      | 0.001  | 0.005  | 0.1    |
| f1_at_5         |     954 | 0.0064 | 0.012  |     0 | 0      | 0.002  | 0.0098 | 0.1333 |
| ap_at_5         |     954 | 0.1647 | 0.1912 |     0 | 0      | 0.1    | 0.28   | 1      |
| mrr_at_5        |     954 | 0.3574 | 0.3241 |     0 | 0      | 0.3333 | 0.5    | 1      |
| precision_at_10 |     954 | 0.2988 | 0.2349 |     0 | 0.1    | 0.3    | 0.5    | 0.9    |
| recall_at_10    |     954 | 0.0063 | 0.0111 |     0 | 0.0015 | 0.0029 | 0.0062 | 0.2    |
| f1_at_10        |     954 | 0.0115 | 0.0167 |     0 | 0.0029 | 0.0059 | 0.0121 | 0.2    |
| ap_at_10        |     954 | 0.1601 | 0.1707 |     0 | 0.02   | 0.1    | 0.2504 | 0.7764 |
| mrr_at_10       |     954 | 0.3727 | 0.31   |     0 | 0.1667 | 0.3333 | 0.5    | 1      |

#### Method: `tfidf` (n=954)

| metric          |   count |   mean |    std |   min |    25% |    50% |    75% |    max |
|:----------------|--------:|-------:|-------:|------:|-------:|-------:|-------:|-------:|
| precision_at_5  |     954 | 0.1878 | 0.2014 |     0 | 0      | 0.2    | 0.4    | 1      |
| recall_at_5     |     954 | 0.0025 | 0.0046 |     0 | 0      | 0.0005 | 0.0031 | 0.0336 |
| f1_at_5         |     954 | 0.0048 | 0.0089 |     0 | 0      | 0.001  | 0.0062 | 0.0649 |
| ap_at_5         |     954 | 0.0949 | 0.1405 |     0 | 0      | 0.05   | 0.1467 | 1      |
| mrr_at_5        |     954 | 0.2577 | 0.2982 |     0 | 0      | 0.25   | 0.3333 | 1      |
| precision_at_10 |     954 | 0.221  | 0.1826 |     0 | 0.1    | 0.2    | 0.3    | 0.9    |
| recall_at_10    |     954 | 0.005  | 0.0081 |     0 | 0.0005 | 0.002  | 0.0056 | 0.0769 |
| f1_at_10        |     954 | 0.0093 | 0.0142 |     0 | 0.001  | 0.0039 | 0.0106 | 0.1132 |
| ap_at_10        |     954 | 0.0951 | 0.1131 |     0 | 0.0111 | 0.0583 | 0.1403 | 0.9    |
| mrr_at_10       |     954 | 0.2845 | 0.2796 |     0 | 0.1111 | 0.25   | 0.3333 | 1      |


## SHAP feature importance (full table from Stage 11)

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

- Faithfulness: 0.2000
- Stability: 0.6842

## LIME explanation details

#### Sample 1: `32eeb8ff-de39-41ac-9d9f-c17401adb44e`

- Predicted: A1
- True: A1
- Title: None
- Human-readable: Predicted A1 (true A1); influential approx tokens: voters(dim 255:+0.020), staff(dim 52:+0.018), vi(dim 48:+0.018), belong(dim 185:+0.017), global(dim 80:+0.016)
- Top features: `[{"dim": 255, "weight": 0.020066695349554294, "approx_token": "voters", "lime_feature": "dim_255 <= -0.06"}, {"dim": 52, "weight": 0.01810633728956606, "approx_token": "staff", "lime_feature": "dim_52 <= -0.04"}, {"dim": 48, "weight": 0.017632153341569128, "approx_token": "vi", "lime_feature": "dim_48 > 0.05"}, {"dim": 185, "weight": 0.0169506267738583, "approx_token": "belong", "lime_feature": "dim_185 > 0.03"}, {"dim": 80, "weight": 0.016341991760576092, "approx_token": "global", "lime_feature`

#### Sample 2: `41533da5-3024-4e8a-8783-8a77f72ff581`

- Predicted: A1
- True: A1
- Title: None
- Human-readable: Predicted A1 (true A1); influential approx tokens: camouflage(dim 94:+0.031), multi(dim 180:+0.025), voters(dim 255:+0.020), ##vr(dim 68:+0.018), curling(dim 269:+0.017)
- Top features: `[{"dim": 94, "weight": 0.030910597034141493, "approx_token": "camouflage", "lime_feature": "dim_94 <= -0.01"}, {"dim": 180, "weight": 0.024963232963691698, "approx_token": "multi", "lime_feature": "dim_180 <= -0.03"}, {"dim": 255, "weight": 0.02046455265389876, "approx_token": "voters", "lime_feature": "dim_255 <= -0.06"}, {"dim": 68, "weight": 0.01844584057721448, "approx_token": "##vr", "lime_feature": "dim_68 <= -0.03"}, {"dim": 269, "weight": 0.016858080899084846, "approx_token": "curling", `

#### Sample 3: `56dc42f3-f9e6-4bd5-a53b-fd545fdfc9d8`

- Predicted: A2
- True: A2
- Title: None
- Human-readable: Predicted A2 (true A2); influential approx tokens: global(dim 80:+0.025), clinton(dim 382:+0.023), pr(dim 295:-0.022), ##aby(dim 188:+0.021), lu(dim 18:+0.020)
- Top features: `[{"dim": 80, "weight": 0.024950902395602888, "approx_token": "global", "lime_feature": "dim_80 <= -0.04"}, {"dim": 382, "weight": 0.022523016162259747, "approx_token": "clinton", "lime_feature": "dim_382 <= -0.07"}, {"dim": 295, "weight": -0.022010009351719765, "approx_token": "pr", "lime_feature": "dim_295 <= -0.04"}, {"dim": 188, "weight": 0.021278175566313968, "approx_token": "##aby", "lime_feature": "dim_188 > 0.07"}, {"dim": 18, "weight": 0.019671418707711386, "approx_token": "lu", "lime_fe`

#### Sample 4: `2197a725-1ae2-4241-8b50-f3f34844e039`

- Predicted: A2
- True: A2
- Title: None
- Human-readable: Predicted A2 (true A2); influential approx tokens: facility(dim 196:+0.024), quickly(dim 381:+0.019), mile(dim 316:-0.018), account(dim 361:+0.018), clinton(dim 382:+0.018)
- Top features: `[{"dim": 196, "weight": 0.023897317363701567, "approx_token": "facility", "lime_feature": "dim_196 > 0.04"}, {"dim": 381, "weight": 0.01919327364018879, "approx_token": "quickly", "lime_feature": "dim_381 > 0.05"}, {"dim": 316, "weight": -0.01832729236408674, "approx_token": "mile", "lime_feature": "dim_316 <= -0.05"}, {"dim": 361, "weight": 0.018271083379778542, "approx_token": "account", "lime_feature": "dim_361 <= -0.04"}, {"dim": 382, "weight": 0.018161106841752244, "approx_token": "clinton"`

#### Sample 5: `5f104170-783f-4ab0-a1f0-39b290721ac0`

- Predicted: B1
- True: B1
- Title: None
- Human-readable: Predicted B1 (true B1); influential approx tokens: senior(dim 123:+0.015), ##vr(dim 68:+0.013), camouflage(dim 94:+0.013), lucky(dim 10:+0.012), advantage(dim 1:+0.012)
- Top features: `[{"dim": 123, "weight": 0.01463203232236424, "approx_token": "senior", "lime_feature": "dim_123 <= -0.02"}, {"dim": 68, "weight": 0.01318029482865247, "approx_token": "##vr", "lime_feature": "dim_68 > 0.04"}, {"dim": 94, "weight": 0.012906932772514475, "approx_token": "camouflage", "lime_feature": "dim_94 > 0.06"}, {"dim": 10, "weight": 0.012466868403914987, "approx_token": "lucky", "lime_feature": "dim_10 > 0.04"}, {"dim": 1, "weight": 0.012166730992113784, "approx_token": "advantage", "lime_fe`

#### Sample 6: `fbe1eccc-c9dd-4f1b-b354-0bacfcfb554c`

- Predicted: B2
- True: B1
- Title: None
- Human-readable: Predicted B2 (true B1); influential approx tokens: usa(dim 97:+0.020), ##ress(dim 78:+0.019), pl(dim 156:+0.019), license(dim 311:-0.017), resolve(dim 189:+0.017)
- Top features: `[{"dim": 97, "weight": 0.020087234454207355, "approx_token": "usa", "lime_feature": "dim_97 > 0.03"}, {"dim": 78, "weight": 0.019132589640933513, "approx_token": "##ress", "lime_feature": "dim_78 <= -0.02"}, {"dim": 156, "weight": 0.018503005393020824, "approx_token": "pl", "lime_feature": "dim_156 <= -0.02"}, {"dim": 311, "weight": -0.01724478739229941, "approx_token": "license", "lime_feature": "dim_311 > 0.03"}, {"dim": 189, "weight": 0.017002950671615086, "approx_token": "resolve", "lime_fea`

#### Sample 7: `c53b5824-9458-4077-90a8-7d915b7da6ea`

- Predicted: B2
- True: B2
- Title: None
- Human-readable: Predicted B2 (true B2); influential approx tokens: .(dim 63:+0.024), follow(dim 360:+0.022), usa(dim 97:-0.018), inches(dim 77:+0.018), voters(dim 255:-0.017)
- Top features: `[{"dim": 63, "weight": 0.02448388643839478, "approx_token": ".", "lime_feature": "dim_63 <= -0.01"}, {"dim": 360, "weight": 0.022300254002165825, "approx_token": "follow", "lime_feature": "dim_360 > 0.03"}, {"dim": 97, "weight": -0.018206659613517345, "approx_token": "usa", "lime_feature": "dim_97 <= -0.04"}, {"dim": 77, "weight": 0.017709549104543663, "approx_token": "inches", "lime_feature": "dim_77 > 0.03"}, {"dim": 255, "weight": -0.016715674175174715, "approx_token": "voters", "lime_feature`

#### Sample 8: `524f2fa5-228a-47a9-b4fe-3f61753bb161`

- Predicted: C1
- True: B2
- Title: None
- Human-readable: Predicted C1 (true B2); influential approx tokens: global(dim 80:-0.021), ##tri(dim 55:+0.020), vi(dim 48:-0.017), facility(dim 196:+0.017), thousands(dim 204:-0.016)
- Top features: `[{"dim": 80, "weight": -0.02109782608070067, "approx_token": "global", "lime_feature": "dim_80 <= -0.04"}, {"dim": 55, "weight": 0.019996580481565437, "approx_token": "##tri", "lime_feature": "dim_55 <= -0.03"}, {"dim": 48, "weight": -0.017495470456881247, "approx_token": "vi", "lime_feature": "dim_48 > 0.05"}, {"dim": 196, "weight": 0.017321636790900402, "approx_token": "facility", "lime_feature": "dim_196 <= -0.03"}, {"dim": 204, "weight": -0.015913743437624975, "approx_token": "thousands", "l`

#### Sample 9: `2040e5c8-5e76-4045-8934-10f57f660360`

- Predicted: C1
- True: C1
- Title: None
- Human-readable: Predicted C1 (true C1); influential approx tokens: quickly(dim 381:+0.021), vi(dim 48:+0.019), global(dim 80:+0.019), anthem(dim 263:+0.017), ##ce(dim 208:-0.015)
- Top features: `[{"dim": 381, "weight": 0.020626547484452445, "approx_token": "quickly", "lime_feature": "dim_381 <= -0.05"}, {"dim": 48, "weight": 0.019493903935352424, "approx_token": "vi", "lime_feature": "dim_48 <= -0.02"}, {"dim": 80, "weight": 0.01852024827254526, "approx_token": "global", "lime_feature": "dim_80 > 0.04"}, {"dim": 263, "weight": 0.016808186839393, "approx_token": "anthem", "lime_feature": "dim_263 > 0.03"}, {"dim": 208, "weight": -0.015275908165313871, "approx_token": "##ce", "lime_featur`

#### Sample 10: `26087369-40cd-40da-a415-f90fed971148`

- Predicted: C2
- True: C2
- Title: None
- Human-readable: Predicted C2 (true C2); influential approx tokens: co(dim 107:+0.018), identical(dim 226:+0.016), pl(dim 256:+0.016), usa(dim 97:-0.015), annoyed(dim 98:+0.014)
- Top features: `[{"dim": 107, "weight": 0.017872745850382475, "approx_token": "co", "lime_feature": "dim_107 <= -0.01"}, {"dim": 226, "weight": 0.016174329658078055, "approx_token": "identical", "lime_feature": "dim_226 <= -0.05"}, {"dim": 256, "weight": 0.015877088625420418, "approx_token": "pl", "lime_feature": "dim_256 <= -0.03"}, {"dim": 97, "weight": -0.014854808582124202, "approx_token": "usa", "lime_feature": "dim_97 > 0.03"}, {"dim": 98, "weight": 0.014280711706182688, "approx_token": "annoyed", "lime_f`


## Complete experiment log (summary)

| ID | Name | Method | Status | MAP/P@k | Completed |
| --- | --- | --- | --- | --- | --- |
| 29c79c00 | Experiment 3: SBERT + Metadata | sbert_metadata | failed | — | 2026-08-05T11:59:59 |
| 67809dfe | Experiment 3: SBERT + Metadata | sbert_metadata | failed | 0.2583 | 2026-08-05T12:01:24 |
| 1150eca0 | Experiment 3: SBERT + Metadata | sbert_metadata | completed | 0.2583 | 2026-08-05T12:02:47 |
| 77f4a51c | Baseline TF-IDF | tfidf | completed | 0.0951 | 2026-08-05T16:52:24 |
| f10988b0 | SBERT Semantic | sbert | completed | 0.1601 | 2026-08-05T16:52:41 |
| b68e51aa | Baseline TF-IDF | tfidf | completed | 0.0951 | 2026-08-05T16:58:06 |
| 58237291 | SBERT Semantic Retrieval | sbert | completed | 0.1601 | 2026-08-05T18:59:34 |
| 7936a03b | TF-IDF Baseline Retrieval | tfidf | completed | 0.0951 | 2026-08-05T18:59:40 |
| 7222f375 | Baseline TF-IDF | tfidf | completed | 0.0951 | 2026-08-05T19:14:36 |
| 558ca82a | SBERT Semantic | sbert | completed | 0.1601 | 2026-08-05T19:15:07 |
| e17cb423 | SBERT + Metadata | sbert_metadata | completed | 0.2583 | 2026-08-05T19:15:51 |
| cf42a1b6 | SBERT + Metadata + RAG | sbert_metadata_rag | completed | 0.2583 | 2026-08-05T19:18:37 |

- Full JSON: `D:/Documents/Yousaf/efl-indexdb/research/experiments/experiment_log.json`
