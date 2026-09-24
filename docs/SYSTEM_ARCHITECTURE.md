# System Architecture

**Project:** Design and Implementation of an Explainable Anomaly-Screening System for Nigerian Public Procurement Records

This document describes the **current implemented architecture** as found in the repository. Where an earlier design document (`docs/plan/DESIGN.md`) differs, the implementation described here is the source of truth and the difference is noted.

---

## 1. High-level architecture

```
┌─────────────┐     HTTPS      ┌──────────────────────────────────────────┐
│   Browser   │ ─────────────► │  Django 6.1 application (config/)        │
│  (templates │                │                                          │
│   + Chart.js│ ◄───────────── │  URL router → view functions → templates │
│   + custom  │     HTML/JSON  │  decorators: login / administrator       │
│   CSS)      │                └───────────────┬──────────────────────────┘
└─────────────┘                                │ ORM
                                               ▼
                                    ┌─────────────────────┐
                                    │     PostgreSQL      │
                                    │ contracts, features │
                                    │ anomaly_flags, …    │
                                    └─────────────────────┘

Background / CLI path (management commands + standalone scripts):
  import_data → generate_features → run_detection → generate_explanations
  run_final_evaluation.py (synthetic eval)   run_explainability_eval.py (audit)
```

Two execution paths share the same codebase:

1. **Web request path** — authenticated views read the database and render templates.
2. **Pipeline path** — management commands and evaluation scripts train models, write flags/explanations, or compute metrics.

---

## 2. Django project structure

```
week-9-implementation/
├── manage.py                     # DJANGO_SETTINGS_MODULE=config.settings.dev
├── requirements.txt
├── .env.example                  # placeholders only
├── test_sprint1.py               # 30 end-to-end checks
├── run_final_evaluation.py       # synthetic evaluation script
├── run_explainability_eval.py    # read-only explainability audit
├── scripts/authz_audit.py        # read-only authorization audit
├── config/
│   ├── settings/base.py          # shared settings, DB via os.getenv, logging
│   ├── settings/dev.py           # DEBUG=True, optional debug_toolbar
│   ├── settings/prod.py          # secure cookies, DENY framing
│   ├── urls.py                   # root URL configuration
│   ├── wsgi.py / asgi.py
├── apps/
│   ├── core/         TimeStampedModel abstract base
│   ├── accounts/     User model, login/logout/profile, admin user mgmt
│   ├── ingestion/    models + CSV/OCP import services
│   ├── preprocessing/ cleaners, quality report, pipeline
│   ├── features/     Feature model, registry, engineering, commands
│   ├── detection/    detectors, trainer, evaluator, synthetic, models, command
│   ├── explainability/ SHAP/LIME/nl/force-plot, Explanation model, command
│   ├── dashboard/    main UI views + URLs
│   └── reporting/    InvestigationReport + report views
├── templates/        project-level templates (base, dashboard, reports, accounts)
├── static/           css/ (design-system, custom), js/ (app, force_plot)
├── data/             raw/, processed/, synthetic/, snapshots/ (mostly gitignored)
├── ml/
│   ├── pipelines/run_pipeline.py
│   └── artifacts/.gitkeep
└── docs/             USER_GUIDE, SYSTEM_ARCHITECTURE, ML_METHODOLOGY, …
```

Installed apps (from `config/settings/base.py`): Django contrib apps + `apps.core`, `apps.accounts`, `apps.ingestion`, `apps.preprocessing`, `apps.features`, `apps.detection`, `apps.explainability`, `apps.dashboard`, `apps.reporting`.

---

## 3. Application / module responsibilities

| Module | Responsibility | Key files |
|---|---|---|
| `apps.core` | Abstract `TimeStampedModel` (`created_at`, `updated_at`) | `models.py` |
| `apps.accounts` | Custom `User` with roles; login/logout/profile; admin-only user list/create/edit; settings screen; `administrator_required` decorator | `models.py`, `views.py`, `decorators.py`, `forms.py` |
| `apps.ingestion` | `ProcuringEntity`, `Vendor`, `Contract`, `RawRecord`; OCP download, CSV staging, validation, mapping into main tables; Import screen | `models.py`, `services/csv_importer.py`, `services/ocds_mapping.py`, `views.py` |
| `apps.preprocessing` | Award-date cleaning, missing values, de-duplication, type casting, categorical encoding, quality report, optional processed CSV export | `cleaners.py`, `quality_report.py`, `pipeline.py` |
| `apps.features` | `Feature` model (1:1 contract), feature registry metadata, engineering computation, `generate_features` command | `models.py`, `engineering.py`, `registry.py` |
| `apps.detection` | `BaseDetector`, `IsolationForestDetector`, `LOFDetector`, trainer/persistence, `AnalysisRun` + `AnomalyFlag`, evaluator, synthetic injection, `run_detection` command | `base.py`, `isolation_forest.py`, `local_outlier.py`, `trainer.py`, `models.py`, `synthetic.py`, `evaluator.py` |
| `apps.explainability` | `Explanation` model, SHAP explainer, natural-language generator, force-plot helpers, LIME placeholder, `generate_explanations` command | `shap_explainer.py`, `natural_language.py`, `force_plot.py`, `lime_explainer.py`, `models.py` |
| `apps.dashboard` | Dashboard, Anomaly Queue, Anomaly Detail, Records, Record Detail, Analysis Runs, Model Performance | `views.py`, `urls.py` |
| `apps.reporting` | Investigation report list/detail/create | `models.py`, `views.py` |

---

## 4. URL / routing structure

Root router: `config/urls.py`.

| URL | View | Name | Access |
|---|---|---|---|
| `/admin/` | Django admin | — | Django staff |
| `/` | `dashboard.index_view` | `dashboard:index` | Login required |
| `/anomalies/` | `dashboard.anomalies_view` | `dashboard:anomalies` | Login required |
| `/anomalies/<int:contract_id>/` | `dashboard.anomaly_detail_view` | `dashboard:anomaly_detail` | Login required |
| `/records/` | `dashboard.records_view` | `dashboard:records` | Login required |
| `/records/<int:contract_id>/` | `dashboard.record_detail_view` | `dashboard:record_detail` | Login required |
| `/analysis-runs/` | `dashboard.analysis_runs_view` | `dashboard:analysis_runs` | Login required |
| `/model-performance/` | `dashboard.model_performance_view` | `dashboard:model_performance` | Login required |
| `/analytics/runs/` | same view as analysis runs | `analytics_runs` | Login required |
| `/analytics/performance/` | same view as model performance | `analytics_performance` | Login required |
| `/accounts/login/` | `accounts.login_view` | `accounts:login` | Public |
| `/accounts/logout/` | `accounts.logout_view` | `accounts:logout` | Public (ends session) |
| `/accounts/profile/` | `accounts.profile_view` | `accounts:profile` | Login required |
| `/ingestion/import/` | `ingestion.import_data_view` | `ingestion:import_data` | **Administrator** |
| `/reports/` | `reporting.report_list_view` | `reporting:report_list` | Login required |
| `/reports/<int:contract_id>/` | `reporting.report_detail_view` | `reporting:report_detail` | Login required |
| `/reports/<int:contract_id>/create/` | `reporting.report_create_view` | `reporting:report_create` | Login required (POST creates) |
| `/system/users/` | `accounts.user_list_view` | `admin_users` | **Administrator** |
| `/system/users/create/` | `accounts.user_create_view` | `admin_user_create` | **Administrator** |
| `/system/users/<int:user_id>/edit/` | `accounts.user_edit_view` | `admin_user_edit` | **Administrator** |
| `/system/settings/` | `accounts.settings_view` | `admin_settings` | **Administrator** |

> Difference from `DESIGN.md`: the design document uses `/admin/users/` style paths; the implementation uses `/system/users/…`. Implementation is authoritative.

Public registration (`/accounts/register/`) was removed (test expects 404).

---

## 5. Database architecture

PostgreSQL database name from `DB_NAME` (default `procurement_anomaly`), credentials from `.env` via `python-dotenv`.

```
users  (custom auth)
  │
  ├── investigation_reports.reviewer_id
  │
procuring_entities ──┐
                     ├── contracts ◄── features (OneToOne)
vendors ─────────────┘       │
                             ├── anomaly_flags   (unique: contract + model_used)
                             ├── explanations    (unique: contract + model_used)
                             └── investigation_reports

raw_records   (staging; not joined to contracts)
analysis_runs (standalone run log)
```

Table names are explicit via `db_table`: `users`, `procuring_entities`, `vendors`, `contracts`, `raw_records`, `features`, `anomaly_flags`, `analysis_runs`, `explanations`, `investigation_reports`.

Verified row counts (development database at documentation time):

| Table | Rows |
|---|---|
| raw_records | 17,417 |
| contracts | 16,637 |
| features | 16,637 |
| procuring_entities | 257 |
| vendors | 10,499 |
| anomaly_flags | 33,274 (16,637 IF + 16,637 LOF) |
| explanations | 1,664 (832 IF + 832 LOF) |
| analysis_runs | 6 |
| investigation_reports | 1 |

---

## 6. Main models and relationships

### `accounts.User` (extends `AbstractUser`)
- `role`: `ADMIN` | `AUDITOR` (default `AUDITOR`)
- Properties: `is_administrator`, `is_auditor`
- `db_table = 'users'`; `AUTH_USER_MODEL = 'accounts.User'`

### `ingestion.ProcuringEntity`
- `entity_id` PK, `name`, `type`, `state`
- Reverse: `contracts`

### `ingestion.Vendor`
- `vendor_id` PK, `name`, `cac_number` (unique, nullable), `state`
- Reverse: `contracts`

### `ingestion.Contract` (fact table)
- `contract_id` PK
- `entity` FK → ProcuringEntity (`SET_NULL`, related `contracts`)
- `vendor` FK → Vendor (`SET_NULL`, related `contracts`)
- `title`, `amount`, `currency`, `award_date`, `bidding_window_days`, `num_bidders`, `method`, `category`, `description`, `nocopo_id` (unique)
- Inherits timestamps

### `ingestion.RawRecord` (staging)
- `source_file`, `ocds_release` (JSON), `is_validated`, `validation_errors`, `is_imported`
- Nothing reaches `contracts` without validation

### `features.Feature`
- `OneToOneField(Contract, related_name='features')`
- Columns: `price_deviation` (present in schema, **not populated** by engineering), `single_bidder_flag`, `vendor_win_frequency`, `vendor_win_concentration`, `splitting_flag`, `splitting_count`, `log_contract_value`
- `bulk_create(..., ignore_conflicts=True)` — re-running generation does not overwrite existing rows unless old rows are deleted first

### `detection.AnalysisRun`
- `model_name`, `contamination`, `n_samples`, `n_features`, `n_anomalies`, score stats (`score_mean/std/min/max`), `duration_seconds`, `status`, `params` (JSON)
- Created by `run_detection` after a saved run; ordering `-created_at`

### `detection.AnomalyFlag`
- `contract` FK (related `anomaly_flags`), `risk_score`, `model_used`, `is_anomaly`, `explanation_text`
- **`unique_together = [['contract', 'model_used']]`** — Isolation Forest and LOF flags coexist for the same contract
- Trainer deletes only rows for the model being re-run before inserting (`_save_anomaly_flags`)
- One row is written for **every** contract per model (anomalous or not)

### `explainability.Explanation`
- `contract` FK (related `explanations`), `model_used` (default `isolation_forest`)
- `shap_values` (JSON, length 6), `feature_importance` (JSON, top-5), `force_plot_data` (JSON list), `natural_language` (text)
- **`unique_together = [['contract', model_used']]`** — model-specific explanations; UI selects `Explanation.objects.filter(contract=…, model_used=flag.model_used)`
- Written via `update_or_create` (idempotent regeneration)

### `reporting.InvestigationReport`
- `contract` FK, `reviewer` FK → user (`SET_NULL`), `status` (`draft` | `reviewed`), `finding`, `recommendation`
- Ordered `-created_at`; created through the report form (POST)

### `core.TimeStampedModel`
- Abstract: `created_at` (auto now add), `updated_at` (auto now); default ordering `-created_at`

---

## 7. Authentication and authorization

| Mechanism | Implementation |
|---|---|
| Custom user | `AUTH_USER_MODEL = 'accounts.User'` with `role` |
| Login | `accounts.login_view` + Django `AuthenticationForm` subclass (`LoginForm`) |
| Session | Django session middleware; logout view calls `logout()` |
| View protection | `@login_required` on all authenticated views |
| Admin protection | `@administrator_required` (`apps/accounts/decorators.py`): unauthenticated → login redirect; non-admin → dashboard redirect + error message |
| UI hiding | `{% if user.is_administrator %}` gates Import Dataset, Users, Settings sidebar links |
| Passwords | Django password validators (similarity, length, common, numeric) |
| CSRF | `CsrfViewMiddleware`; forms include `{% csrf_token %}` |
| Registration | Removed (404) |

---

## 8. Administrator / Auditor permission boundaries

| Capability | Administrator | Auditor |
|---|---|---|
| Dashboard, Queue, Detail, Records, Analytics, Reports, Profile | ✓ | ✓ |
| Import Dataset (`/ingestion/import/`) | ✓ | ✗ (302 redirect) |
| Users list/create/edit (`/system/users/…`) | ✓ | ✗ |
| Settings (`/system/settings/`) | ✓ | ✗ |
| Create Auditor accounts via web form | ✓ (always role=AUDITOR) | ✗ |
| Create Administrator accounts | Via `createsuperuser` / Django admin only | — |
| Deactivate own account | Blocked by view logic | — |

Verified by `test_sprint1.py` (role permission tests) and `scripts/authz_audit.py`.

---

## 9. Data flow

```
OCP CSV / uploaded CSV
    │
    ▼ import_csv_to_raw()
raw_records (staging, JSON blob)
    │
    ▼ map_ocds_row() + _validate_mapped_record()
    │   invalid → raw.is_validated=True, validation_errors stored
    ▼ _import_validated_batch()
procuring_entities / vendors (get_or_create) + contracts
    │
    ▼ run_full_pipeline()  [preprocessing — DataFrame-level cleaning]
cleaned DataFrame (+ optional data/processed/cleaned_contracts.csv)
    │
    ▼ generate_features → compute_all_features()
features (6 active fields per contract)
    │
    ▼ run_detection --model isolation_forest|lof
load_feature_matrix() → detector.fit/predict → normalised scores
    │
    ▼ _save_anomaly_flags(model_used=…)
anomaly_flags (replace model’s rows, keep other model’s rows)
    │
    ▼ auto SHAP block in run_detection  OR  generate_explanations
explanations (update_or_create per contract+model)
    │
    ▼ Web UI reads
Dashboard / Queue / Detail / Reports
```

Management commands:

| Command | App | Effect |
|---|---|---|
| `import_data [--url …] [--skip-download]` | ingestion | Download/use CSV → stage → validate → contracts |
| `generate_features` | features | Compute + save 6 features (ignore_conflicts) |
| `run_detection [--model …] [--contamination …] [--sensitivity] [--no-save]` | detection | Train, persist flags + AnalysisRun, auto-generate SHAP |
| `generate_explanations [--model …] [--top N]` | explainability | (Re)generate SHAP explanations for a model’s flags |

---

## 10. ML pipeline integration

- Feature matrix source: `load_feature_matrix()` queries the `features` table and returns `(X[FEATURE_COLUMNS], contract_ids)` with NaN → 0 fill.
- `FEATURE_COLUMNS` (single source of truth in `apps/detection/trainer.py`):
  `single_bidder_flag`, `vendor_win_frequency`, `vendor_win_concentration`, `splitting_flag`, `splitting_count`, `log_contract_value`.
- Detectors share `BaseDetector` (fit/predict/score_samples/get_params). IF overrides nothing on scoring; LOF overrides `get_anomaly_scores` (rank-based among flagged).
- Persistence is model-scoped: flags and explanations keyed by `model_used` ∈ {`isolation_forest`, `local_outlier_factor`}.
- `run_detection` writes an `AnalysisRun` row (duration, score stats, params JSON) when saving is enabled.

---

## 11. Explainability integration

Pipeline:

1. After flags are saved, `run_detection` (or `generate_explanations`) fits an `IsolationForestDetector` on the current feature matrix.
2. `SHAPExplainer` wraps `shap.TreeExplainer(fitted_if_model)`.
3. For each flagged contract of the target `model_used`, the corresponding feature row is explained (`top_k=5` for the importance list; full 6-vector stored in `shap_values`).
4. `generate_natural_language()` renders neutral prose + mandatory closing disclaimer.
5. `Explanation.objects.update_or_create(contract_id=…, model_used=…, defaults={…})`.

Implementation note (documented, not altered): `TreeExplainer` requires a tree model, so explanations are always computed from the **Isolation Forest** estimator trained on the same matrix — including when `model_used='local_outlier_factor'`. The `model_used` field records which model’s flag the explanation is attached to; the UI loads the explanation matching the displayed flag’s model.

LIME (`lime_explainer.py`) is an optional placeholder: it imports `lime` lazily and degrades gracefully if the package is absent. It is **not** wired into commands or views (deferred).

---

## 12. Investigation workflow

```
Anomaly Queue ──click──► Anomaly Detail
                            │
                            ├─ Create Investigation Report ──POST──► InvestigationReport(draft|reviewed)
                            │                                              │
                            └─ View Existing Reports ──────────────► Report Detail
                                                                       │
Reports list (/reports/) ◄─────────────────────────────────────────────┘
```

- Report creation requires login; `reviewer` is set to `request.user`.
- Status constrained to `draft`/`reviewed` (invalid values coerced to `draft`).
- Report detail aggregates flag context, contributions, NL explanation, and all reports for the contract.

---

## 13. Persistence of anomaly flags

`_save_anomaly_flags(contract_ids, predictions, scores, model_name)` (atomic):

1. `DELETE` rows where `contract_id in …` AND `model_used = model_name` (other model’s rows untouched).
2. `bulk_create` a row for **every** contract: `risk_score=float(score)`, `is_anomaly=(prediction == -1)`, `model_used=model_name`.

Consequences:

- Re-running IF does not destroy LOF flags (and vice versa).
- Total flag rows = 2 × contracts when both models have been run (33,274 for 16,637 contracts).
- The Anomaly Queue filters `is_anomaly=True` (832 + 832 = 1,664 rows).

---

## 14. Persistence of model-specific explanations

- Uniqueness: `(contract, model_used)`.
- Write path: `update_or_create` → regeneration overwrites in place, never duplicates.
- Read path (Anomaly Detail): explanation filtered by `flag.model_used` of the highest-scoring flag displayed.
- Regeneration integrity (verified): re-running IF explanation generation preserves existing LOF explanations.

---

## 15. AnalysisRun

Created inside `run_detection` when `save` is true and no error occurred. Stores the operational metadata listed in §6. Consumed by:

- `/analysis-runs/` table view
- Score statistics for audit/history

The Model Performance screen computes synthetic metrics and sensitivity **live** rather than reading them from AnalysisRun (AnalysisRun only records the contamination level of the run that was executed).

---

## 16. InvestigationReport

See §6 and §12. This is the only place human findings are stored. The system never writes findings automatically.

---

## 17. Security mechanisms

- `.env` gitignored; `.env.example` placeholders; settings read via `os.getenv` with non-secret defaults.
- `SECRET_KEY` from environment (fallback string exists for dev only — see LIMITATIONS).
- CSRF on all POST forms; session cookies; clickjacking `XFrameOptionsMiddleware`.
- Production (`config.settings.prod`): `DEBUG=False`, `ALLOWED_HOSTS` from env, secure session/CSRF cookies, `X_FRAME_OPTIONS='DENY'`, XSS filter and content-type nosniff.
- Static files served via WhiteNoise (`CompressedManifestStaticFilesStorage`).
- Query-time filtering uses ORM parameterisation (no raw SQL concatenation of user input in views).
- Authorization audit script: `scripts/authz_audit.py` (read-only, uses SQLite test settings).

---

## 18. Error handling (as implemented)

| Area | Behaviour |
|---|---|
| CSV import | Exceptions captured and rendered in the Import screen error banner |
| OCP download | URL discovery failures logged; fallback patterns; errors surface to import view |
| Validation | Per-record errors stored on `RawRecord.validation_errors`; batch continues |
| Per-row contract insert | Failures logged; collected in import stats `errors` list |
| `run_detection` | Wraps execution; raises `CommandError` with message on failure |
| SHAP auto-generation in `run_detection` | Wrapped in try/except — prints warning, does not fail the detection command |
| SHAP TreeExplainer init | try/except → logs warning; `explainer=None` → zero SHAP values path |
| LIME import | ImportError → graceful “unavailable” |
| Sensitivity on Model Performance | try/except → section omitted if computation fails |
| View-level `get_object_or_404` | Standard 404 for missing contracts |

Not implemented: structured API error payloads (application is server-rendered), automated alerting, retry queues.

---

## 19. Configuration and environment

`.env` variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DJANGO_SETTINGS_MODULE` | Documented in example; `manage.py` defaults to `config.settings.dev` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection |
| `OCP_DATA_REGISTRY_URL`, `NOCOPO_CSV_URL` | Data source endpoints |

Other settings of note (`base.py`): `TIME_ZONE='Africa/Lagos'`, `USE_TZ=True`, static/media paths, data directory constants (`DATA_RAW_DIR`, …, `ML_ARTIFACTS_DIR`), console logging with `apps` logger at DEBUG.

Optional: `debug_toolbar` enabled in `dev.py` if installed (not in requirements.txt).

---

## 20. Deployment considerations (only as supported by the repository)

Supported by the codebase today:

- WSGI entry: `config.wsgi.application`; ASGI: `config.asgi`.
- `config.settings.prod` exists for hardened settings; requires `ALLOWED_HOSTS` and a real `DJANGO_SECRET_KEY` in the environment.
- WhiteNoise for static file serving in a single-process deployment.
- PostgreSQL required (no SQLite configuration for the main app; the authz audit script constructs its own SQLite test settings).

Not provided in the repository: Docker/compose files, CI pipelines, reverse-proxy config, production migration runbooks, hosting guides. Treat deployment as a conventional Django + PostgreSQL + WhiteNoise setup if needed later.

---

## Related documents

- [USER_GUIDE.md](USER_GUIDE.md) — how humans use each screen
- [ML_METHODOLOGY.md](ML_METHODOLOGY.md) — models, features, scoring, SHAP
- [EVALUATION.md](EVALUATION.md) — metrics and overlap figures
- [docs/plan/DESIGN.md](plan/DESIGN.md) — original design specification (historical)
