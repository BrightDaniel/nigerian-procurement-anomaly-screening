# Design and Implementation of an Explainable Anomaly-Screening System for Nigerian Public Procurement Records

A web-based decision-support system that screens Nigerian public procurement records for unusual statistical patterns using unsupervised machine learning (Isolation Forest and Local Outlier Factor), explains each flag with SHAP-based feature attributions in plain language, and supports a human investigation workflow. Built with Django, PostgreSQL, and scikit-learn.

## Problem

Public procurement datasets are large, heterogeneous, and difficult for human reviewers to inspect record-by-record. Unusual patterns — such as single-bidder awards, repeated awards to the same vendor, or possible contract-splitting sequences — can be present without being visible in a raw spreadsheet. Auditors need a way to **prioritise which records to look at first**, together with an explanation of *why* a record was prioritised.

## Purpose

This system ingests published Nigerian procurement data, engineers risk-oriented features, runs two unsupervised anomaly-screening models, stores model-specific anomaly flags and scores, generates SHAP explanations for every flagged record, and presents the results in an investigation interface where authorised reviewers can record findings.

## Scope statement (important)

- This is an **anomaly-screening** system.
- It does **not** detect fraud.
- It does **not** establish guilt or wrongdoing.
- It **prioritises records for human investigation**.
- A flag means a record *may warrant further investigation* by a qualified reviewer — nothing more.
- All evaluation is based on **synthetically injected anomalies**, not real-world fraud labels.

## Key capabilities

| Capability | Description |
|---|---|
| Data ingestion | CSV upload or OCP Data Registry download → staging (`RawRecord`) → validated contracts |
| Preprocessing | Date cleaning, missing-value handling, de-duplication, type casting, data-quality report |
| Feature engineering | Six active features computed per contract and stored in PostgreSQL |
| Anomaly screening | Isolation Forest and Local Outlier Factor, persisted per model |
| Explainability | SHAP values, top-5 feature importance, force-plot data, natural-language explanations |
| Anomaly Queue | Filterable, sortable, paginated list of flagged records |
| Investigation workflow | Create and review investigation reports against flagged records |
| Analytics | Analysis-run history and a live model-performance screen |
| Role-based access | Administrator and Auditor/Reviewer roles |

## User roles

| Role | Value in `User.role` | Capabilities |
|---|---|---|
| **Administrator** | `ADMIN` | Everything below, plus Import Dataset, Users management, Settings |
| **Auditor/Reviewer** | `AUDITOR` | Dashboard, Anomaly Queue, Anomaly Detail, Records, Analysis Runs, Model Performance, Investigation Reports, Profile |

Administrator accounts are created via `python manage.py createsuperuser` or Django admin. Auditor accounts are created by Administrators on the Users screen. There is no public self-registration.

## Main workflow

```
Procurement data (OCP Publication 64 CSV)
        ↓
Validation / preprocessing  (17,417 raw → 16,637 valid; 780 rejected)
        ↓
Feature engineering         (6 active features per contract)
        ↓
Isolation Forest + LOF      (contamination = 0.05)
        ↓
Anomaly flags / scores      (model-specific, persisted)
        ↓
SHAP explanations           (per contract, per model)
        ↓
Anomaly Queue               (prioritised for review)
        ↓
Human investigation         (Auditor judgment)
        ↓
Investigation Report        (finding, recommendation, status)
```

## Technology stack

| Layer | Technology |
|---|---|
| Web framework | Django 6.1.1 |
| Language | Python 3.14 |
| Database | PostgreSQL (via `psycopg2-binary`) |
| Data handling | pandas 3.0.5, NumPy 2.5.3 |
| ML | scikit-learn 1.9.1 (Isolation Forest, Local Outlier Factor) |
| Explainability | SHAP (`shap.TreeExplainer`) |
| Frontend | Django templates, custom CSS design system, Bootstrap Icons, Chart.js (CDN) |
| Settings | `config.settings.dev` (default), `config.settings.prod` |
| Environment | `python-dotenv` loading `.env` |

> Note: `shap` is required by the explainability module and is installed in the development environment, but it is currently **not listed in `requirements.txt`** (see [docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

## High-level architecture

```
Browser ──► Django URL router (config/urls.py)
              ├── apps/accounts      auth, roles, user admin
              ├── apps/ingestion     CSV/OCP import, staging, validation
              ├── apps/preprocessing cleaning + quality report
              ├── apps/features      6-feature engineering → features table
              ├── apps/detection     IF + LOF → anomaly_flags, analysis_runs
              ├── apps/explainability SHAP → explanations
              ├── apps/dashboard     UI views (queue, detail, records, analytics)
              └── apps/reporting     investigation reports
                        │
                        ▼
                   PostgreSQL
```

Deeper detail: [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md).

## Dataset summary

| Item | Value |
|---|---|
| Source | OCP Data Registry, Publication 64 (Nigeria Bureau of Public Procurement mirror) |
| Raw records | 17,417 |
| Valid contracts | 16,637 |
| Rejected at validation | 780 |
| Procuring entities | 257 |
| Vendors | 10,499 |
| Category field | Not usable for price benchmarking in this extract |

The dataset is **not** a complete representation of all Nigerian public procurement. Details: [docs/DATASET.md](docs/DATASET.md).

## Six active model features

| Feature | Type | Meaning |
|---|---|---|
| `log_contract_value` | Continuous | `log(1 + amount)` — contract value on a compressed scale |
| `single_bidder_flag` | Binary | 1 if only one tenderer participated |
| `vendor_win_frequency` | Continuous | Share of all contracts won by the vendor |
| `vendor_win_concentration` | Continuous | HHI of vendor wins within the procuring entity |
| `splitting_flag` | Binary | 1 if >3 similar contracts, same vendor + entity, within 12 months |
| `splitting_count` | Discrete | Count of those similar contracts (excluding self) |

`price_deviation` is **excluded** — the available OCP extract did not provide a sufficiently usable category field for the intended calculation.

## Models

| Model | Library | Contamination | Other parameters |
|---|---|---|---|
| Isolation Forest | `sklearn.ensemble.IsolationForest` | 0.05 | `n_estimators=100`, `random_state=42` |
| Local Outlier Factor | `sklearn.neighbors.LocalOutlierFactor` | 0.05 | `n_neighbors=20`, `novelty=False` (uses `fit_predict`) |

Both models produce a binary flag (`is_anomaly`) and a normalised `risk_score` in \[0, 1\] stored per contract per model. Score normalisation differs between the models — see [docs/ML_METHODOLOGY.md](docs/ML_METHODOLOGY.md).

## Explainability approach

- **SHAP** (`TreeExplainer` on the fitted Isolation Forest) produces a six-value SHAP vector per explained record.
- A **top-5** human-readable feature-importance list is stored (the full six-value vector is retained in `shap_values`).
- **Force-plot data** (simplified Chart.js rendering) is stored per explanation; the contribution table remains authoritative.
- A **natural-language explanation** is generated with fixed neutral language rules and always ends with a disclaimer that the system flags records for review and does not detect fraud.
- Explanations are stored **per contract and per model** (`unique_together(contract, model_used)`).

## Evaluation summary

Controlled **synthetic** evaluation (5% injection, `random_state=42`, labels chosen before training; not real-world ground truth):

| Model | Precision | Recall | F1 | Detected (of 16,637) | Runtime |
|---|---|---|---|---|---|
| Isolation Forest | 0.1659 | 0.1661 | 0.1660 | 832 | 0.55 s |
| LOF | 0.0841 | 0.0842 | 0.0842 | 832 | 0.39 s |

Persisted-database overlap (authoritative): IF 832, LOF 832, both 137, IF-only 695, LOF-only 695, Jaccard 0.0897.

Explainability: 1,664/1,664 flags explained (100% coverage), 0 model mismatches, 0 feature-integrity errors, 0 banned-language violations outside the disclaimer.

Full results and caveats: [docs/EVALUATION.md](docs/EVALUATION.md).

## Security and authorization

- Custom `User` model with `ADMIN` / `AUDITOR` roles; `@login_required` on all application views; `@administrator_required` on Import Dataset, Users, and Settings.
- Public registration removed (returns 404); Auditor accounts created by Administrators only.
- Credentials and database password live in `.env` (gitignored); `.env.example` contains placeholders only.
- Django CSRF protection, password validators, session middleware; production settings enable secure cookies and `X_FRAME_OPTIONS = DENY`.
- An authorization audit script exists: `scripts/authz_audit.py` (read-only).

## Ethical safeguards

- UI disclaimers on Anomaly Detail and report screens: an anomaly flag is **not** a determination of wrongdoing.
- Generated natural-language explanations use a fixed vocabulary: “flagged for review”, “may warrant further investigation”, “contributed to the anomaly score”; banned terms (fraud, corrupt, guilty, …) are checked outside the closing disclaimer (0 violations across 1,664 explanations).
- Evaluation never reports synthetic Precision/Recall/F1 as fraud-detection accuracy.

## Current limitations (summary)

- No real-world fraud ground truth; evaluation is in-sample synthetic only.
- LIME explainer is a placeholder (deferred); SHAP is the implemented method.
- `price_deviation` not active; no category-based price benchmarking.
- No independent human-auditor evaluation study.
- `shap` missing from `requirements.txt` (installed in the dev environment).

Full list: [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Local setup

```bash
# 1. Clone
git clone https://github.com/BrightDaniel/nigerian-procurement-anomaly-screening.git
cd nigerian-procurement-anomaly-screening

# 2. Virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt
pip install shap          # required by apps/explainability (not yet in requirements.txt)

# 4. Environment file
cp .env.example .env
# Edit .env: DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DJANGO_SECRET_KEY

# 5. Database (PostgreSQL must be running)
createdb procurement_anomaly     # or use an existing database name matching .env

# 6. Migrate + admin account
python manage.py migrate
python manage.py createsuperuser

# 7. Import data (see data/raw/README.md for the OCP download)
python manage.py import_data --skip-download   # if data/raw/full.csv already present
# or: python manage.py import_data             # downloads from OCP

# 8. Features, detection, explanations
python manage.py generate_features
python manage.py run_detection --model isolation_forest
python manage.py run_detection --model lof
python manage.py generate_explanations --model isolation_forest
python manage.py generate_explanations --model local_outlier_factor
```

## Running the application

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and log in with the administrator account.

## Testing and evaluation commands (as supported by the repository)

```bash
python manage.py check          # Django system check
python test_sprint1.py          # 30 end-to-end checks (expects admin/admin123 in dev DB)
python run_final_evaluation.py  # synthetic P/R/F1 + sensitivity (does not write DB flags)
python run_explainability_eval.py  # read-only explainability audit of the DB
python scripts/authz_audit.py   # read-only authorization audit (SQLite test settings)
```

## Documentation index

| Document | Audience | Contents |
|---|---|---|
| [README.md](README.md) | Everyone | Entry point (this file) |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | New users | Screen-by-screen walkthrough |
| [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) | Developers | Modules, models, routes, data flow |
| [docs/ML_METHODOLOGY.md](docs/ML_METHODOLOGY.md) | Students/researchers | Features, models, scoring, SHAP |
| [docs/DATASET.md](docs/DATASET.md) | Researchers | Datasheet-style dataset documentation |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Supervisors/examiners | Authoritative evaluation results |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Everyone | Responsible-use boundaries |
| [docs/plan/DESIGN.md](docs/plan/DESIGN.md) | Developers | Original UI/UX design specification |
| [docs/plan/STATUS.md](docs/plan/STATUS.md) | Project owner | Build status checklist |

## Project status

| Phase | Status |
|---|---|
| Sprint 1 (scaffold, auth, ingestion, preprocessing, features, UI) | Complete |
| Sprint 2 (IF, LOF, evaluator, synthetic injection, run_detection) | Complete |
| Batch B (Import screen, Analysis Runs, Model Performance) | Complete |
| Batch C (Profile, Users, Settings, Investigation workflow) | Complete |
| QA fixes (model-specific flags/explanations, LOF scoring, SHAP persistence) | Complete |
| Final synthetic + explainability evaluation | Complete |
| Academic write-up (Chapters 1–5) | Not started |

**Academic project** — SEN 497 Final Year Project, Covenant University, 2026.
