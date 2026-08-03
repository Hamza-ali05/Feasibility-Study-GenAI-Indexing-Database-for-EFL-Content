# Frontend adaptation notes — EFL IndexDB

**Project:** Feasibility Study: GenAI Indexing Database for EFL Content  
**Base template:** [Material Dashboard React](https://github.com/creativetimofficial/material-dashboard-react) (Creative Tim, Material Dashboard 2 React v2.2.0), cloned into `frontend/`  
**Rule:** Do not scaffold a competing frontend. Edit the cloned layout (`src/layouts`, `src/components`, `src/examples`, `src/assets/theme`, `routes.js`, `src/context`).

These notes capture discovery from Phase 0 (Prompt 0-C) and the adaptation plan before any theme/route edits.

---

## 1. Default template pages → EFL IndexDB

| Material Dashboard React default | EFL IndexDB fate |
|----------------------------------|------------------|
| Dashboard | **Keep / repurpose** → **Dashboard** (pipeline + DB monitoring) |
| Tables | **Repurpose** → **Browse Resources** (resource catalogue / tabular browse) |
| Billing | **Removed** |
| RTL | **Removed** |
| Notifications | **Removed** (keep `MDSnackbar` / alert patterns for live status only) |
| Profile | **Repurpose** → **Admin Panel** |
| Sign In | **Kept** and wired to real backend admin auth |
| Sign Up | **Removed** (single-admin research tool; no public registration) |

Shell pieces that stay regardless of page deletion: `examples/Sidenav`, `examples/Navbars/DashboardNavbar`, `examples/LayoutContainers/DashboardLayout`, Charts, DataTable, and all `components/MD*`.

---

## 2. New pages (not in the template)

| New page | Purpose | Typical `layouts/` home |
|----------|---------|-------------------------|
| Search | AI Semantic Search (+ Smart Filters UI) | e.g. `layouts/search` |
| Pipeline Monitor | Run/watch pipeline; **14-stage submenu** | e.g. `layouts/pipeline` (+ per-stage children) |
| Ask AI | AI Question Answering (RAG) chat | e.g. `layouts/ask-ai` |
| Recommendations | Intelligent Recommendations | e.g. `layouts/recommendations` |
| Resource Analyzer | AI Resource Analyzer (upload + classify) | e.g. `layouts/analyzer` |
| Search Analytics | Search Analytics dashboards | e.g. `layouts/analytics` |
| Duplicate Review | Duplicate Detection review queue | e.g. `layouts/duplicates` |
| Document Preview | Document Preview for a selected resource | e.g. `layouts/preview` |
| Metrics / Evaluation | Train/Evaluate metrics surfaces | e.g. `layouts/metrics` |
| Explainability | Explain Global / Local / Quality | e.g. `layouts/explain` (or three routes) |
| About | Project / feasibility study about page | e.g. `layouts/about` |

Every live feature must call the real backend. If a prerequisite pipeline artefact is missing (e.g. FAISS index), the UI shows an honest **“Pipeline stage X not complete yet”** state — never mock JSON.

---

## 3. Final sidebar tree (preview for `routes.js`)

> Authoritative wiring lands in a later routes prompt (Prompt 4-D). This tree is the documented preview so sidebar intent is fixed before code changes.

```
EFL IndexDB
│
├── Dashboard                          ← live: Dashboard (pipeline + DB monitoring)
│
├── Pipeline Monitor
│   ├── Discover
│   ├── Load
│   ├── Integrate
│   ├── EDA
│   ├── Clean
│   ├── Split
│   ├── Preprocess
│   ├── Balance
│   ├── Train
│   ├── Evaluate
│   ├── Explain Global
│   ├── Explain Local
│   ├── Explain Quality
│   └── Predict
│
├── Live Features
│   ├── AI Semantic Search             ← Search (+ Smart Filters on this page)
│   ├── AI Question Answering (RAG)    ← Ask AI
│   ├── Intelligent Recommendations
│   ├── Smart Filters                  ← may deep-link / share filters with Search
│   ├── AI Resource Analyzer
│   ├── Search Analytics
│   ├── Duplicate Detection            ← Duplicate Review
│   └── Document Preview
│
├── Browse Resources                   ← repurposed Tables
├── Metrics / Evaluation
├── Explainability
│   ├── Explain Global
│   ├── Explain Local
│   └── Explain Quality
│
├── Admin Panel                        ← repurposed Profile (+ Sign In gate)
├── Sign In                            ← real backend auth (not shown when already authed)
└── About
```

**Not in sidebar:** Billing, RTL, Notifications, Sign Up.

**Pipeline stage names** (exact, used everywhere — sidebar, API, state file, tests):

`Discover`, `Load`, `Integrate`, `EDA`, `Clean`, `Split`, `Preprocess`, `Balance`, `Train`, `Evaluate`, `Explain Global`, `Explain Local`, `Explain Quality`, `Predict`

**Live feature names** (exact):

`AI Semantic Search`, `AI Question Answering (RAG)`, `Intelligent Recommendations`, `Smart Filters`, `AI Resource Analyzer`, `Dashboard`, `Search Analytics`, `Duplicate Detection`, `Document Preview`, `Admin Panel`

---

## 4. UI kit confirmation — Material UI (MUI) stays

The frontend remains on **Material UI** via the Creative Tim Material Dashboard React kit.

We **reuse** the shipped MD wrappers instead of inventing parallel primitives:

| Template component | Role |
|--------------------|------|
| `MDBox` | Layout / spacing surface |
| `MDTypography` | Text |
| `MDButton` | Actions |
| `MDBadge` | Status / CEFR chips (colours from theme tokens) |
| `MDInput` | Forms / search |
| `MDAlert` | Honest pipeline / missing-artefact messages |
| `MDProgress` | Pipeline stage progress |
| `MDSnackbar` | Transient notifications |
| `MDAvatar`, `MDPagination` | As needed |

Theme recolour (greyish EFL palette + CEFR / status tokens) is done **centrally** in:

- `frontend/src/assets/theme/` (and `theme-dark/` if kept)
- especially `base/colors.js`, `base/typography.js`, `base/globals.js`

**Never** hardcode hex colours inside individual page/component files.

---

## Related paths (from 0-C discovery)

| Concern | Location |
|---------|----------|
| Routes / sidenav entries | `frontend/src/routes.js` |
| App shell + theme provider | `frontend/src/App.js` |
| Sidenav | `frontend/src/examples/Sidenav/` |
| Dashboard navbar | `frontend/src/examples/Navbars/DashboardNavbar/` |
| Layout chrome | `frontend/src/examples/LayoutContainers/` |
| Light theme entry | `frontend/src/assets/theme/index.js` |
| Palette tokens | `frontend/src/assets/theme/base/colors.js` |
| Controller context | `frontend/src/context/index.js` |
