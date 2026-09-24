# Dataset

**Project:** Design and Implementation of an Explainable Anomaly-Screening System for Nigerian Public Procurement Records

This datasheet-style document describes the data used by the system: origin, composition, processing path, and quality characteristics — as verified against the repository and the development database.

---

## 1. Source

| Property | Value |
|---|---|
| **Publisher** | Open Contracting Data Standard (OCDS) / Nigerian Open Contracting (OCP / NOCOPO) publications |
| **Publication** | Publication 64 bundle (national procurement award data) |
| **Primary URL configuration** | `NOCOPO_CSV_URL`, `OCP_DATA_REGISTRY_URL` (see `.env.example`, `config/settings/base.py`, `apps/ingestion/services/`) |
| **Ingestion** | `python manage.py import_data [--url …] [--skip-download]` or web **Import Dataset** (Administrator) |
| **Format** | CSV staged as OCDS-shaped JSON per row (`RawRecord.ocds_release`) |
| **Licence / terms** | Governed by the upstream OCP publication; this project does not relicense the data |

The system does **not** scrape private or confidential award systems; it operates on the published export.

---

## 2. Record counts (development database, verified)

| Stage / table | Count | Notes |
|---|---|---|
| `raw_records` (staging) | **17,417** | Every row staged from source files |
| Invalid / rejected staging rows | **780** | Failed validation; remain in staging with `validation_errors` |
| `contracts` (valid, usable) | **16,637** | 17,417 − 780 |
| `features` | **16,637** | 1:1 with contracts |
| `procuring_entities` | **257** | Distinct MDAs |
| `vendors` | **10,499** | Distinct bidders/winners |
| `anomaly_flags` | **33,274** | 16,637 × 2 models |
| … of which anomalous (`is_anomaly=true`) | **1,664** | 832 IF + 832 LOF |
| `explanations` | **1,664** | 832 IF + 832 LOF |
| `investigation_reports` | **1** | Example/manual report present |

Data files on disk (`data/raw/`, `data/processed/`, `data/synthetic/`) are largely gitignored; tracked files are README placeholders describing expected contents.

---

## 3. Schema (conceptual)

Staging → fact path:

```
RawRecord (staging)
  source_file, ocds_release (JSON), is_validated, validation_errors, is_imported
        │  map_ocds_row() + validation
        ▼
ProcuringEntity (entity_id, name, type, state)
Vendor         (vendor_id, name, cac_number, state)
Contract       (contract_id, entity_id, vendor_id, title, amount, currency,
                award_date, bidding_window_days, num_bidders, method,
                category, description, nocopo_id UNIQUE, created_at, updated_at)
Feature        (feature_id, contract_id UNIQUE,
                price_deviation,           -- schema only, not populated
                single_bidder_flag, vendor_win_frequency,
                vendor_win_concentration, splitting_flag,
                splitting_count, log_contract_value)
```

### Core contract fields used by the product

| Field | Used for |
|---|---|
| `title`, `description` | Display, search |
| `entity` / `vendor` FKs | Attribution, Top MDA charts, vendor features |
| `amount` | `log_contract_value`, display |
| `award_date` | Sorting, splitting windows, date filters |
| `num_bidders` | `single_bidder_flag`, display |
| `method`, `category` | Filters (method); category exists but lacks usable price reference |
| `nocopo_id` | External identifier, de-duplication |

---

## 4. Validation rules (ingestion)

Implemented in `apps/ingestion/services/` (`ocds_mapping.py`, `csv_importer.py` and related validators):

- Required identifying fields present (contract identifier, title or equivalent).
- `award_date` parseable / castable to date.
- `amount` castable to numeric (non-positive or non-numeric handled per validator rules).
- Entity/vendor names resolvable (create-if-missing with `get_or_create`).
- Duplicate `nocopo_id` / release id handling prevents double-inserting the same award.

Failures write structured `validation_errors` on the staging row; valid rows proceed to `contracts` in batches inside a transaction per batch.

---

## 5. Preprocessing / cleaning

`apps/preprocessing/` (`cleaners.py`, `quality_report.py`, `pipeline.py`):

| Step | Description |
|---|---|
| Award-date cleaning | Parse/coerce dates; unusable dates surfaced in quality report |
| Missing values | Detected and reported; downstream matrix fills NaN → 0 |
| De-duplication | Redundant releases collapsed where identifiers match |
| Type casting | Numeric/date casting for amount and dates |
| Categorical encoding | Quality-report oriented; model features use engineered numerics, not raw one-hot categories |
| Quality report | Summary of issues retained for inspection |
| Optional export | Cleaned DataFrame can be written to `data/processed/cleaned_contracts.csv` |

Note: the authoritative training input is the **`features` table**, not the optional cleaned CSV.

---

## 6. Feature dataset (model input)

Six active features (full definitions: [ML_METHODOLOGY.md](ML_METHODOLOGY.md)):

1. `single_bidder_flag`
2. `vendor_win_frequency`
3. `vendor_win_concentration`
4. `splitting_flag`
5. `splitting_count`
6. `log_contract_value`

`price_deviation` exists in schema but is **excluded** (no usable unit-price basis).

Matrix properties:

- Shape: **16,637 × 6**
- NaN policy: fill 0 at load
- No feature scaling applied (tree models)

---

## 7. Synthetic data (evaluation only)

| Property | Value |
|---|---|
| Purpose | Controlled evaluation with known labels |
| Generator | `apps/detection/synthetic.py` |
| Default injection rate | 5% of records (seed 42) |
| Label timing | Injection mask **before** training (independent of model output) |
| On disk | `data/synthetic/` (gitignored; README tracked) |
| Production use | **Never** mixed into the screening UI; evaluation scripts only |

With 16,637 records and 5% injection: **831** injected anomalies in the default final evaluation (see EVALUATION.md).

---

## 8. Data quality observations (verified)

- Valid conversion rate: 16,637 / 17,417 ≈ **95.5%** accepted; 780 rejected with recorded errors.
- Entity concentration: 257 MDAs across 16,637 contracts (top entities dominate flag counts — expected).
- Vendor long-tail: 10,499 vendors; many with a single award (affects `vendor_win_frequency` and concentration features).
- `num_bidders`: present on records; drives `single_bidder_flag` where ≤ 1.
- Amounts: positive values required for meaningful `log_contract_value`; zeros/missing become 0 after log1p or fill.
- No ground-truth fraud labels exist in the dataset.

---

## 9. Privacy, ethics, and handling

- The dataset is **published** procurement data (OCDS), not personal data in the special-category sense; vendor/entity names are organisational.
- Still treat account credentials and any future personal fields as sensitive: `.env` is gitignored; no secrets are committed.
- System outputs (flags, explanations, reports) must be handled as **preliminary analytical results**, not accusations.
- Reports store reviewer text — reviewers should avoid defamatory or unproven claims (see [LIMITATIONS.md](LIMITATIONS.md)).

---

## 10. Access and reproduction

```bash
# 1. Configure .env (DB_* and OCP URLs)
# 2. Stage + import
python manage.py import_data
# 3. Features
python manage.py generate_features
# 4. Screening
python manage.py run_detection --model isolation_forest
python manage.py run_detection --model local_outlier_factor
# 5. Explanations (if not auto-generated)
python manage.py generate_explanations --model isolation_forest
python manage.py generate_explanations --model local_outlier_factor
```

Tracked data docs: `data/raw/README.md`, `data/processed/README.md`, `data/synthetic/README.md`.

> Documentation fix applied in this pass: `data/processed/README.md` previously named the feature table `features_feature`; the actual `db_table` is `features` (corrected in that README only — application code untouched).

---

## 11. Known dataset limitations

- Single-source data (one OCP publication family); not a longitudinal multi-year panel unless the export itself spans years.
- No bid amounts from losing bidders → no true price competition features.
- No structured commodity/category price references → `price_deviation` unusable.
- No outcome labels (investigations, sanctions) → evaluation relies on synthetic injection only.
- Entity/vendor identity depends on name matching quality in the export.

Full impact discussion: [LIMITATIONS.md](LIMITATIONS.md).

---

## Related documents

- [ML_METHODOLOGY.md](ML_METHODOLOGY.md) — features derived from this dataset
- [EVALUATION.md](EVALUATION.md) — metrics from synthetic evaluation
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — ingestion and storage design
