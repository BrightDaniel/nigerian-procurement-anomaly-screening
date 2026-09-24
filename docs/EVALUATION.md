# Evaluation

**Project:** Design and Implementation of an Explainable Anomaly-Screening System for Nigerian Public Procurement Records

This document records the **authoritative evaluation results** for the implemented system, the methodology behind them, and the caveats required to interpret them correctly. All figures below were cross-checked against the repository scripts and the development database at documentation time.

---

## 1. What is being evaluated

Two distinct kinds of results exist; they must not be confused:

| Kind | Purpose | Labels | Where |
|---|---|---|---|
| **Synthetic detection evaluation** | Measure how well IF/LOF recover *injected* anomalies | Injection mask (5%, seed 42) | `run_final_evaluation.py`, Model Performance screen |
| **Persisted screening output** | What is actually stored after production-style runs on the real dataset | None (unsupervised) | `anomaly_flags`, dashboard, queue |
| **Explainability audit** | Structural quality of SHAP explanations (not accuracy) | n/a (rules/checks) | `run_explainability_eval.py` |

There is **no** ground-truth fraud benchmark in this project.

---

## 2. Synthetic evaluation setup

| Setting | Value |
|---|---|
| Base records | 16,637 contracts (6-feature matrix) |
| Injection rate | **5%** → **831** injected anomalies |
| Seed | 42 |
| Label timing | Assigned **before** training from injection mask |
| IF parameters | contamination 0.05, n_estimators 100, random_state 42 |
| LOF parameters | contamination 0.05, n_neighbors 20 |
| Timing measured | Fit + predict wall time for each model |

Script: `run_final_evaluation.py`. The same computation is surfaced interactively on `/model-performance/`.

> Note: 831 injected ≠ 832 persisted anomalous flags in the DB. The 832 figure is the production run’s flag count under contamination 0.05 on the un-injected matrix (5.00% of 16,637). Do not add or mix these counts.

---

## 3. Detection metrics (authoritative)

### 3.1 Isolation Forest (5% synthetic anomalies)

| Metric | Value |
|---|---|
| **Precision** | **0.1659** |
| **Recall** | **0.1661** |
| **F1** | **0.1660** |
| True Positives (TP) | 138 |
| False Positives (FP) | 694 |
| False Negatives (FN) | 693 |
| True Negatives (TN) | 15,112 |
| Execution time | **0.55 s** |

### 3.2 Local Outlier Factor (5% synthetic anomalies)

| Metric | Value |
|---|---|
| **Precision** | **0.0841** |
| **Recall** | **0.0842** |
| **F1** | **0.0842** |
| True Positives (TP) | 70 |
| False Positives (FP) | 762 |
| False Negatives (FN) | 761 |
| True Negatives (TN) | 15,044 |
| Execution time | **0.39 s** |

### 3.3 Reading these numbers (mandatory)

- Both models recover only a **small fraction** of injected anomalies at contamination 0.05 (IF ≈ 16.6% recall, LOF ≈ 8.4% recall).
- Precision is correspondingly low: most model-flagged records in this synthetic run were **not** the injected points.
- These results are **consistent with unsupervised anomaly detection on weakly separated tabular data** — they are **not** evidence that the system “detects fraud 16% of the time” or any such claim.
- F1 differences (IF 0.1660 vs LOF 0.0842) support treating **Isolation Forest as the primary model** and LOF as a secondary/diversity signal — which matches the implementation’s primary/secondary framing.

---

## 4. Contamination sensitivity

Anomaly counts produced when varying `contamination` (synthetic evaluation path / sensitivity table):

| Contamination | Anomalies flagged |
|---|---|
| 0.01 | **167** |
| 0.03 | **497** |
| 0.05 | **832** |
| 0.10 | **1,664** |

Interpretation: queue length scales roughly linearly with contamination (≈ 1% ≈ 167 records). Choosing contamination is a **review-capacity decision**, not a statistical truth about how many bad records exist.

---

## 5. Persisted screening results (production-style runs)

Verified directly in the database:

| Item | Value |
|---|---|
| Contracts | 16,637 |
| Anomaly flags total | 33,274 (2 per contract) |
| IF anomalous flags | **832** (5.00%) |
| LOF anomalous flags | **832** (5.00%) |
| Explanations | 1,664 (832 IF + 832 LOF) |
| Force-plot entries | 1,664 explanations → 9,984 feature entries (6 per explanation) |
| SHAP vector length | 6 for all audited explanations |
| Banned-language violations | **0** |
| Closing disclaimer present | **1,664 / 1,664** |

---

## 6. Model overlap analysis (persisted flags)

Comparison of **which contracts** IF vs LOF marked anomalous:

| Item | Value |
|---|---|
| Flagged by both models | **137** |
| IF only | **695** |
| LOF only | **695** |
| Union of flagged contracts | 1,527 |
| **Jaccard similarity** | **0.0897** (137 / 1,527) |

### 6.1 Synthetic overlap (different experiment — do not conflate)

During synthetic evaluation, agreement between model predictions and/or across model runs has been measured at **141** in the overlap sense used by that experiment’s script output. The figure **141 belongs to the synthetic-labelled run**; the figure **137** is the persisted production-flag overlap. Always label which experiment an overlap number comes from.

### 6.2 What low overlap means

- Jaccard ≈ 0.09 → IF and LOF flag largely **different** records.
- This is expected: isolation-based vs density-based geometry, plus score normalisation differences.
- Operational consequence: reviewing **both** queues surfaces more distinct candidates than either alone; “flagged by both” (137) is a high-consensus subset some teams may prioritise first — still **not** a fraud list.

---

## 7. Priority distribution (persisted anomalous flags)

Among stored anomaly flags with anomalous status (score banded by UI thresholds):

| Priority | Condition | Count |
|---|---|---|
| High | score ≥ 0.80 | **530** |
| Medium | 0.60 ≤ score < 0.80 | **635** |
| Normal | score < 0.60 | **499** |
| **Total** | | **1,664** |

(UI thresholds: `apps/dashboard/views.py`. Trainer percentile thresholds are separate — see ML_METHODOLOGY.md §5.)

---

## 8. Explainability evaluation

Script: `run_explainability_eval.py` (read-only audit).

| Check | Result |
|---|---|
| SHAP vector length = 6 (`FEATURE_COLUMNS`) | Pass (all audited rows) |
| Top-k feature list non-empty & schema-valid | Pass |
| Banned terms (fraud/guilty/corrupt/…) in natural language | **0 violations** |
| Mandatory closing disclaimer present | **1,664 / 1,664** |
| Force-plot JSON structure usable by UI | Pass (1,664 plots, 9,984 entries) |
| Explanation ↔ flag model pairing | Pass (UI loads by `model_used`) |

These are **structural and ethical-language checks**, not fidelity-vs-oracle scores. A deeper fidelity comparison (e.g., SHAP vs perturbation) was not established as a benchmark in this project — noted as future work in LIMITATIONS.

---

## 9. Performance / runtime

| Operation | Observed time (evaluation environment) |
|---|---|
| IF fit + predict (16,637 × 6) | 0.55 s |
| LOF fit + predict (16,637 × 6) | 0.39 s |
| SHAP explanation (per-record TreeExplainer rows, batch) | Dominated by Python loop overhead; acceptable for 832/model at this scale |
| Detection command end-to-end (incl. DB writes) | Seconds-scale on local PostgreSQL |

No multi-second training bottleneck exists at this dataset size; scalability concerns are discussed in LIMITATIONS (larger volumes, richer features).

---

## 10. Evaluation limitations (summary)

1. **Synthetic labels ≠ real fraud** — injection changes feature patterns in controlled ways; real irregularities may look different.
2. **Single dataset, single snapshot** — no temporal hold-out, no external validation on another jurisdiction.
3. **Low absolute P/R/F1** — expected for weakly supervised-free settings; must be reported honestly (done here).
4. **Contamination chooses recall/precision trade-off** — not estimated from data-driven thresholding in production UI (absolute score bands instead).
5. **No explanation-fidelity benchmark** — audit checks structure/language only.
6. **Overlap experiments differ** — 137 (persisted) vs 141 (synthetic) must be cited with their experiment context.

Full narrative: [LIMITATIONS.md](LIMITATIONS.md).

---

## 11. How to re-run evaluations

```bash
# Synthetic detection evaluation (writes no model artifacts required beyond DB/features)
python run_final_evaluation.py

# Explainability audit (read-only)
python run_explainability_eval.py

# Interactive equivalents
# Log in → /model-performance/   (synthetic table + sensitivity)
```

Ensure `DJANGO_SETTINGS_MODULE` matches a settings module that loads (`config.settings.dev` as used by `manage.py`). Standalone scripts that assume `config.settings` only work if that package exports settings — see discrepancy report (scripts currently set `config.settings` while `config/settings/__init__.py` is empty).

---

## Related documents

- [ML_METHODOLOGY.md](ML_METHODOLOGY.md) — model configuration behind these numbers
- [DATASET.md](DATASET.md) — corpus size and composition
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — where results persist
- [LIMITATIONS.md](LIMITATIONS.md) — responsible interpretation boundaries
