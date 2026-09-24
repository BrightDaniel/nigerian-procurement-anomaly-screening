# Machine Learning Methodology

**Project:** Design and Implementation of an Explainable Anomaly-Screening System for Nigerian Public Procurement Records

This document describes exactly what the implementation trains, on which features, how scores and explanations are produced, and what the outputs mean. It is aligned with `apps/detection/`, `apps/features/`, and `apps/explainability/` as they exist in the repository.

---

## 1. Problem framing

**Unsupervised anomaly detection** over tabular procurement records:

- No ground-truth “fraud” labels are used for training.
- The models learn a notion of “normal” from feature vectors of published contracts and score how isolated each record is relative to that structure.
- The product is a **screening and prioritisation** system, not a classification system and not a fraud detector.

---

## 2. Feature engineering (six active features)

Single source of truth: `FEATURE_COLUMNS` in `apps/detection/trainer.py`.

| # | Feature | Definition (as implemented) | Type / range |
|---|---|---|---|
| 1 | `single_bidder_flag` | `1` if `num_bidders <= 1`, else `0` | Binary {0,1} |
| 2 | `vendor_win_frequency` | Contract count of the vendor ÷ total valid contracts; 0 if vendor unknown | [0,1] |
| 3 | `vendor_win_concentration` | For the vendor: largest share of its awards going to one procuring entity (entity-level win concentration for that vendor); 0 if unknown | [0,1] |
| 4 | `splitting_flag` | `1` if the vendor has ≥ `SPLITTING_MIN` (default 3) contracts with the **same entity** inside a rolling `SPLITTING_WINDOW_DAYS` (default 30) window on award date, else `0` | Binary {0,1} |
| 5 | `splitting_count` | Maximum number of such same-entity same-window contracts observed for the vendor | Integer ≥ 0 |
| 6 | `log_contract_value` | `log1p(amount)` natural log of contract value | Continuous ≥ 0 |

Computation lives in `apps/features/engineering.py` (with registry metadata in `apps/features/registry.py`). Rows are written with `bulk_create(..., ignore_conflicts=True)` keyed by the `Feature` one-to-one contract id.

### Feature explicitly excluded

| Feature | Status |
|---|---|
| `price_deviation` | Column exists on the `Feature` model but is **not computed** and **not used** in training. There is no reliable unit-price / category-normalisation field in the current dataset, so a defensible price-deviation measure could not be defined. Any residual UI mention of price deviation in older dashboard contribution helpers is a display artefact, not a model feature (see README / handoff discrepancy list). |

### Engineering caveats

- Missing amounts are treated as 0 in `log_contract_value` when present as NaN → 0 at matrix load (`load_feature_matrix`).
- Vendor/entity features are computed from the **full** contracted set (not time-split), so they are transductive statistics rather than strictly point-in-time features.
- `splitting_*` uses calendar windows of 30 days by default; constants are configurable in the engineering module.

---

## 3. Feature matrix construction

`load_feature_matrix()` (`apps/detection/`):

1. Query all `Feature` rows joined to contract ids.
2. Select exactly `FEATURE_COLUMNS` in fixed order.
3. Replace NaN with 0 (`DataFrame.fillna(0)`).
4. Return `(X, contract_ids)` where `contract_ids[i]` aligns with `X.iloc[i]`.

No scaling/standardisation is applied. Tree-based isolation methods are scale-invariant across features; this is intentional.

---

## 4. Models

Both models implement `BaseDetector` (`apps/detection/base.py`) with:

- `fit(X)`
- `predict(X)` → {-1 anomalous, +1 inlier} (sklearn convention)
- `score_samples(X)` → raw model scores
- `get_anomaly_scores(X, predictions)` → **normalised** scores (model-specific; see §5)
- `get_params()`

### 4.1 Isolation Forest (primary)

File: `apps/detection/isolation_forest.py`, wrapping `sklearn.ensemble.IsolationForest`.

| Parameter | Value | Source |
|---|---|---|
| `contamination` | `0.05` default (CLI-overridable) | `run_detection` / trainer |
| `n_estimators` | `100` | detector default |
| `random_state` | `42` | detector default |
| `max_samples` | sklearn default (`auto`) | sklearn |
| `behaviour` | not set (sklearn ≥0.22 fixed behaviour) | — |

Algorithmic idea: isolation is easier for anomalies; the forest averages path lengths of random feature-value splits.

### 4.2 Local Outlier Factor (secondary)

File: `apps/detection/local_outlier.py`, wrapping `sklearn.neighbors.LocalOutlierFactor`.

| Parameter | Value |
|---|---|
| `contamination` | `0.05` default (CLI-overridable) |
| `n_neighbors` | `20` |
| `novelty` | `False` (transductive; `fit_predict` path) |
| `metric` | sklearn default (`minkowski` / euclidean) |

Algorithmic idea: density-based; points with substantially lower local density than neighbours are outliers. Because `novelty=False`, the detector is used in the inductive/transductive train-and-predict sense on the full matrix.

### 4.3 Two-model coexistence

Flags and explanations are stored **per model** (`model_used` ∈ {`isolation_forest`, `local_outlier_factor`}). Re-running one model replaces only that model’s flags. Both models have been run on the current dataset (832 anomalous flags each).

---

## 5. Scoring (important — two different normalisations)

The UI displays `risk_score` in [0,1]. Higher = more anomalous. The raw sklearn scores are **not** shown.

| Model | Normalisation of displayed score |
|---|---|
| **Isolation Forest** | Min–max normalisation of inverted `score_samples` over **all** records: `score = (max − s) / (max − min)` after negation so that more-isolated → higher score. Every contract gets a continuous score. Implemented in `BaseDetector` / IF path. |
| **LOF** | **Rank-based among flagged (predicted anomaly) records only.** Flagged records receive evenly spaced ranks mapped to (0,1]; non-flagged records store `0.0`. Implemented by LOF’s `get_anomaly_scores` override. |

Consequences:

- IF and LOF scores are **not on the same calibrated scale** — compare within a model.
- LOF “0.0” means “not flagged by LOF”, not “perfectly normal”.
- Score distribution charts mixing both models should be read with this caveat.

### Priority thresholds (two schemes — documented discrepancy)

| Scheme | Where | High | Medium | Normal |
|---|---|---|---|---|
| **UI absolute thresholds** | `apps/dashboard/views.py` (`_default_priority`) and templates | `score ≥ 0.80` | `0.60 ≤ score < 0.80` | `< 0.60` |
| **Trainer percentiles** | `apps/detection/trainer.py` `PRIORITY_THRESHOLDS` | ≥ 95th percentile of run scores | ≥ 80th percentile | below |

The percentile thresholds are **computed and logged** during training (useful for run diagnostics) but the **on-screen badges and filters use the fixed 0.80 / 0.60 cut-offs**. This dual scheme is a known inconsistency reported in the project handoff; it is not silently reconciled here.

---

## 6. Anomaly decision rule

A record is treated as **flagged anomalous** for display when `AnomalyFlag.is_anomaly == True` for that model, i.e. the detector returned `-1` under its `contamination` parameter.

- Default contamination `0.05` → roughly 5% of records marked anomalous per model.
- With 16,637 contracts: observed **832** anomalous flags per model (≈ 5.00%).
- Contamination is the primary lever controlling queue size (`--contamination` on `run_detection`, sensitivity table on Model Performance).

---

## 7. SHAP explanations

### 7.1 What is computed

File: `apps/explainability/shap_explainer.py`.

1. Fit (or reuse) an **IsolationForestDetector** on the current feature matrix.
2. Build `shap.TreeExplainer(fitted_if_model)`.
3. For each contract to explain: take its row `x` from the matrix → `shap_values = explainer.shap_values(x)` (length 6, aligned to `FEATURE_COLUMNS`).
4. Build top-5 `feature_importance`: features sorted by `|shap_value|`, each with `feature`, `shap_value`, `direction` (`positive` pushes score toward anomaly / higher, `negative` pushes lower), and the `feature value`.
5. Build `force_plot_data`: per-feature contribution entries compatible with the simplified force-plot UI.

### 7.2 Model labelling caveat (reported, not changed)

`TreeExplainer` requires a tree ensemble, so the **explainer always uses the Isolation Forest estimator**, even when generating explanations for LOF flags (`generate_explanations --model local_outlier_factor`, or the auto-explain block after a LOF run). The stored `Explanation.model_used` records **which model’s flag** the explanation is attached to (so the UI can pair flag ↔ explanation), not which estimator produced the SHAP numbers.

Interpretation guideline: read LOF-attached SHAP text as “Isolation-forest-based feature attribution shown alongside the LOF flag”, and prefer IF explanations for strictly model-consistent attribution.

### 7.3 Natural-language rendering

`apps/explainability/natural_language.py`:

- Builds sentences from top contributions (highest |SHAP| first) with neutral verbs: “flagged”, “contributed to the anomaly score”, “pushed higher/lower”.
- **Never** uses: fraud, guilty, corrupt, illegal, offender, criminal, etc.
- **Always** ends with the closing disclaimer: feature contributions indicate records that may warrant further review; the system flags records for investigation — it does not detect fraud or wrongdoing.
- Stored on `Explanation.natural_language`; also used as `AnomalyFlag.explanation_text` when written during detection.

Banned-language audit (current DB): **0 violations** across stored explanations; closing disclaimer present on **1,664 / 1,664** explanation-linked displays checked.

### 7.4 Regeneration integrity

`Explanation` unique on `(contract, model_used)`; writes use `update_or_create`. Re-running explanation generation for model A does not delete model B’s rows (verified).

---

## 8. LIME (optional, not in production path)

`apps/explainability/lime_explainer.py` provides an optional LIME tabular explainer that:

- Lazily imports `lime`;
- Degrades gracefully with a clear message if `lime` is not installed;
- Is **not** invoked by `run_detection`, `generate_explanations`, or any dashboard view.

`lime` is therefore intentionally absent from `requirements.txt` (SHAP is the supported method; see discrepancy list for the missing `shap` pin).

---

## 9. Training command and parameters

```bash
python manage.py run_detection --model isolation_forest   # or local_outlier_factor / lof
# options: --contamination 0.05  --no-save  --sensitivity
```

Behaviour (save path):

1. Load feature matrix.
2. Instantiate detector with contamination.
3. `fit` + `predict` + `get_anomaly_scores`.
4. Persist `AnomalyFlag` rows (delete-then-insert for this `model_used` only).
5. Persist `AnalysisRun` with duration and score statistics.
6. Optionally auto-generate SHAP explanations for newly flagged records.

`--sensitivity` prints/records anomaly counts across contaminations `{0.01, 0.03, 0.05, 0.10}` without changing the primary saved run unless combined with save semantics of the command.

---

## 10. Evaluation methodology

Full figures and caveats: [EVALUATION.md](EVALUATION.md). Summary of the **method** here:

1. **Synthetic anomaly injection** (`apps/detection/synthetic.py`): inject 5% (default, seed 42) controlled anomalies into the feature matrix **before** training; labels are assigned from the injection mask (not from model output).
2. Train IF and LOF with default settings on the contaminated matrix.
3. Compare predictions to injection labels → Precision, Recall, F1, confusion counts.
4. **Contamination sensitivity**: anomaly counts at 0.01 / 0.03 / 0.05 / 0.10.
5. **Explainability audit** (`run_explainability_eval.py`, read-only): vector lengths, banned language, disclaimer presence, top-feature sanity — not accuracy metrics.

**What evaluation does not establish:** real-world fraud detection accuracy, legal validity of any flag, or performance under distribution shift on future data.

---

## 11. Reproducibility controls

| Control | Value |
|---|---|
| `random_state` (IF) | 42 |
| Synthetic injection seed | 42 |
| Feature column order | fixed list in `trainer.py` |
| Contamination default | 0.05 |
| LOF `n_neighbors` | 20 |
| NaN policy | fill 0 at matrix load |
| Idempotent flag writes | per-`model_used` replace |
| Idempotent explanation writes | `update_or_create` |

Python/package versions at documentation time: Python 3.14, Django 6.1.1, pandas 3.0.5, scikit-learn 1.9.1, SHAP 0.52.0 (see `requirements.txt` for pins that exist; note `shap` currently **missing** from that file — reported discrepancy).

---

## 12. Intended use and appropriate interpretation

**Intended use:**

- Prioritise manual review of published procurement records.
- Show *which engineered features* drove an anomaly score.
- Support auditors in documenting investigation findings.

**Not intended use:**

- Proving fraud, corruption, or illegality.
- Automatic sanctions, blacklisting, or vendor punishment.
- Comparing vendors or MDAs as “most corrupt”.
- Real-time blocking of awards (system is batch/screening oriented).

See [LIMITATIONS.md](LIMITATIONS.md) for the full responsible-use boundary.

---

## Related documents

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — how components wire together
- [DATASET.md](DATASET.md) — input data characteristics
- [EVALUATION.md](EVALUATION.md) — metric values and overlap analysis
- [USER_GUIDE.md](USER_GUIDE.md) — how explanations appear in the UI
