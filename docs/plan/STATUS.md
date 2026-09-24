# STATUS.md

**Last updated:** 2026-09-23

## Current Phase

**Final Experimental Evaluation — Complete**

### Checklist Progress

| # | Task | Status |
|---|------|--------|
| 1 | Scaffold Django project (`config/`, `apps/core`, `apps/accounts`) and PostgreSQL DB | Done |
| 2 | Confirm NOCOPO access route (API vs CSV export); document fallback to OCP data | Done |
| 3 | Build `apps/ingestion`: importer that lands raw records into `data/raw/` and a `RawRecord` staging table | Done |
| 4 | Retain a fixed, documented snapshot of the data used, for reproducibility | Done |
| 5 | Preprocessing: schema inspection, missing-value handling, de-duplication, type casting, categorical encoding, data-quality report | Done |
| 6 | Feature engineering: implement the five feature groups | Done |
| 7 | Write Chapters 1–2 draft in parallel | Not started |
| 8 | UI/UX Design System + North-Star Screens (Dashboard & Anomaly Detail) | Done |
| 9 | All 14 screen templates created with sidebar navigation | Done |
| 10 | QA audit + critical fix pass (security, authorization, responsive, URLs) | Done |
| 11 | `ml/pipelines/run_pipeline.py` with baseline Isolation Forest | Done |
| 12 | Begin LOF comparator | Done |
| 13 | `apps/explainability`: first-pass SHAP integration on the baseline model | Done |
| 14 | Contamination-parameter sensitivity analysis (0.01, 0.03, 0.05, 0.1) | Done |
| 15 | `apps/dashboard`: analysis_runs and model_performance views with real data | Done |
| 16 | Management command `run_detection` for running detection pipeline | Done |
| 17 | Real-data pipeline: import 16,637 contracts from OCP | Done |
| 18 | Feature engineering on real data (6 active features) | Done |
| 19 | Real-data sanity check + diagnostic report | Done |
| 20 | SHAP installed + explanations generated for 832 anomalies | Done |
| 21 | NULL vendor handling fixed in feature engineering | Done |
| 22 | price_deviation removed (OCP has no category field) | Done |
| 23 | AnalysisRun model for persisting detection run history | Done |
| 24 | Batch B: Import Dataset screen (CSV upload + OCP download) | Done |
| 25 | Batch B: Analysis Runs screen (persisted run history) | Done |
| 26 | Batch B: Model Performance screen (synthetic eval, sensitivity) | Done |
| 27 | Batch C: Profile functional (real user data) | Done |
| 28 | Batch C: Users management (admin create auditor, activate/deactivate) | Done |
| 29 | Batch C: Settings (real system stats) | Done |
| 30 | Batch C: Investigation workflow (Anomaly Detail → Create → Report Detail) | Done |
| 31 | Batch C: InvestigationReport model + migration | Done |
| 32 | QA Fix: AnomalyFlag OneToOne → unique_together(contract, model_used) | Done |
| 33 | QA Fix: LOF risk score normalization (flagged-only rank-based) | Done |
| 34 | QA Fix: SHAP explanations auto-generated and persisted after detection | Done |
| 35 | QA Fix: Remove stale price_deviation template references | Done |
| 36 | Final Synthetic Anomaly Evaluation (IF + LOF, P/R/F1, sensitivity) | Done |
| 37 | Final Explainability Evaluation (coverage, model matching, feature integrity, ethical language) | Done |
| 38 | IF/LOF model overlap resolved (137 dual-flagged, authoritative) | Done |

**Sprint 1 completion: 100%**
**Sprint 2 completion: 100%**
**Batch B completion: 100%**
**Batch C completion: 100%**
**Final Evaluation: Complete**

### Verified Pipeline State

```
OCP procurement data (17,417 raw records)
        ↓
Validation / preprocessing (780 rejected)
        ↓
16,637 valid contracts
        ↓
Feature engineering (6 active features)
        ↓
16,637 feature records
        ↓
Isolation Forest (832 anomalies at c=0.05)
LOF (832 anomalies at c=0.05)
        ↓
Anomaly flags (33,274 records — IF + LOF coexist)
        ↓
SHAP explanations (1,664 total — 832 IF + 832 LOF)
        ↓
IF/LOF overlap: 137 contracts flagged by both
```

### Database State

| Table | Records |
|---|---|
| Contracts | 16,637 |
| Features | 16,637 |
| AnomalyFlags | 33,274 (IF + LOF) |
| Explanations | 1,664 (IF + LOF) |
| ProcuringEntities | 257 |
| Vendors | 10,499 |
| AnalysisRuns | 2+ (IF + LOF) |

### Active Features (6)

| Feature | Category | Type |
|---|---|---|
| log_contract_value | Transaction | Continuous |
| single_bidder_flag | Competition | Binary |
| vendor_win_frequency | Supplier | Continuous |
| vendor_win_concentration | Supplier | Continuous |
| splitting_flag | Splitting | Binary |
| splitting_count | Splitting | Discrete |

### Excluded Features

| Feature | Reason |
|---|---|
| price_deviation | OCP dataset has no usable category field |

### Final Evaluation Results (Chapter 4 values)

**Isolation Forest (contamination=0.05, n_estimators=100):**
- Precision: 0.1659
- Recall: 0.1661
- F1: 0.1660
- TP: 138, FP: 694, FN: 693, TN: 15,112
- Detected: 832 anomalies out of 16,637 records

**LOF (contamination=0.05, n_neighbors=20):**
- Precision: 0.0841
- Recall: 0.0842
- F1: 0.0842
- TP: 70, FP: 762, FN: 761, TN: 15,044
- Detected: 832 anomalies out of 16,637 records

**Contamination Sensitivity (IF):**
- 0.01 → 167 anomalies
- 0.03 → 497 anomalies
- 0.05 → 832 anomalies
- 0.10 → 1,664 anomalies

**Model Overlap (persisted DB, c=0.05):**
- IF flagged: 832, LOF flagged: 832
- Both: 137, IF only: 695, LOF only: 695
- Jaccard: 0.0897

**Explainability:**
- Coverage: 1,664/1,664 (100%)
- Model mismatches: 0
- Feature integrity: 0 errors (all 6 SHAP values, all 5 top-k features match active set, all values match DB)
- Dual-model: 137/137 dual-flagged contracts have both IF+LOF explanations
- Ethical language: 0 banned-word violations outside disclaimer
- Force-plot: 9,984 entries, 0 stale feature references

### Next Tasks

1. Write Chapters 1–5 (research + results writing)
2. Any remaining sprints as needed

### Open Blockers

- LIME explainer is a placeholder (stretch goal, deferred)
- Chapters 1–5 not started
