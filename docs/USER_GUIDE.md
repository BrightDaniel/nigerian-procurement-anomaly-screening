# User Guide

**Project:** Design and Implementation of an Explainable Anomaly-Screening System for Nigerian Public Procurement Records

This guide assumes you have **never used the application before**. It explains every important screen in plain language and walks through a complete investigation from login to report.

---

## What is this system?

This system screens Nigerian public procurement records for **unusual patterns** and helps a human reviewer decide which records **may deserve further investigation**.

It does **not** detect fraud. It does **not** decide that anyone is guilty or that anything illegal happened. It calculates statistical anomaly scores, flags records that look unusual compared with the rest of the data, explains *why* using feature contributions, and leaves the judgment to you.

A “High priority” badge means: *this record received a high normalised anomaly score according to the configured screening model*. It does **not** mean fraud.

---

## Words you will see in this guide

| Term | Plain-language meaning |
|---|---|
| **Procurement record / contract** | One published award: a government entity awarded a contract to a vendor for a stated amount on a date. |
| **Feature** | A calculated number derived from the record (for example, “was there only one bidder?”). The system uses six active features. |
| **Anomaly flag** | The stored result of running a model on one contract: whether the model marked it anomalous (`is_anomaly`) and its score. One flag exists per contract **per model**. |
| **Anomaly score / risk score** | A number between 0 and 1. Higher means the model considers the record more unusual. It is a **statistical** measure, not a legal judgement. |
| **Model** | The screening algorithm. This system uses two: Isolation Forest (`isolation_forest`) and Local Outlier Factor (`local_outlier_factor`). |
| **Explanation** | Stored SHAP-based information for a flagged record: feature contributions, a simplified chart, and a plain-English paragraph. |
| **Investigation report** | A written record made **by you** (finding, recommendation, status) after reviewing a flagged record. |
| **Priority** | A badge derived from the score: High (≥ 0.80), Medium (≥ 0.60 and < 0.80), Normal (< 0.60). |

---

## A. Who uses the system?

Two roles:

| | Administrator | Auditor/Reviewer |
|---|---|---|
| Log in, dashboard, anomaly queue, anomaly detail | Yes | Yes |
| Records and record detail | Yes | Yes |
| Analysis Runs, Model Performance | Yes | Yes |
| Create/view investigation reports | Yes | Yes |
| Profile, logout | Yes | Yes |
| **Import Dataset** | Yes | No (menu hidden; URL redirects) |
| **Users** (create/activate auditors) | Yes | No |
| **Settings** | Yes | No |

Role values in the database: `ADMIN` and `AUDITOR`.

---

## B. Administrator vs Auditor permissions

- **Administrator** manages data and people: imports datasets, creates Auditor accounts, deactivates accounts, views system Settings.
- **Auditor** performs review work: reads flagged records, writes investigation reports.
- Both roles can see all screening results. Nothing in the queue is role-restricted beyond the admin-only pages above.
- If an Auditor tries to open an admin URL directly, the server redirects them to the dashboard with an “Administrator access required” message.

---

## C. Logging in

1. Open the application in your browser (for a local install: `http://127.0.0.1:8000/accounts/login/`).
2. Enter your **username** and **password**.
3. Select **Log in**.

Notes:

- There is **no public registration**. Administrators are created with `python manage.py createsuperuser`; Auditors are created by an Administrator on the Users screen.
- If you are already logged in, visiting the login page sends you to the Dashboard.
- Unauthenticated visitors to any application page are redirected to the login page.

---

## D. Dashboard

**URL:** `/`  
**Purpose:** One-screen overview of the dataset and the current screening results.

What you see:

1. **Stat cards**
   - **Total Contracts** — number of valid procurement records imported (with entity/vendor counts underneath).
   - **Records Flagged** — total number of anomaly-flag records stored (one per contract per model; both models’ rows are counted).
   - **High Priority** — flagged records with score ≥ 0.80 that the model marked anomalous.
   - **Average Score** — mean anomaly score across stored flags.
2. **Score Distribution** — histogram of flags by score range (0.0–0.2, …, 0.8–1.0).
3. **Top MDAs chart** — procuring entities with the most flagged contracts.
4. **Priority Queue** — the top 10 anomalous records by score, each linking to Anomaly Detail.

If no data has been imported, an empty state appears (Administrators get an **Import Dataset** button).

What to do: scan the cards, then click a Priority Queue row or open **Anomaly Queue** in the sidebar.

What **not** to conclude: a high average score or a long queue does not mean widespread wrongdoing — it means the configured models flagged many records at the chosen contamination rate (5%).

---

## E. Understanding dashboard metrics

| Metric | How it is computed | Correct interpretation |
|---|---|---|
| Total Contracts | `COUNT(contracts)` | Size of the valid dataset |
| Records Flagged | `COUNT(anomaly_flags)` — every stored flag row (IF + LOF, anomalous or not) | How much screening output exists, not how many “bad” records |
| High Priority | Flags with `is_anomaly = true` AND score ≥ 0.80 | Highest-scoring anomalous records under the UI threshold |
| Average Score | Mean of all stored `risk_score` values | Central tendency of scores; not a “guilt rate” |
| Score Distribution buckets | Count of flags in each 0.2-wide bucket | Shape of the score spread |
| Top Flagged MDAs | Entities with most contracts having an anomalous flag | Where flags concentrate — may reflect entity size |

---

## F. Anomaly Queue

**URL:** `/anomalies/`  
**Purpose:** The working list of all records the models marked anomalous.

What you see:

- A **filter bar**: free-text search (title, ID, entity, vendor), Priority (High/Medium/Normal), Entity, Vendor, Method, award-date range.
- A **sortable table**: Priority badge, Contract, Entity, Vendor, Amount (₦), Award date, Score, Model, and an open button.
- **Pagination** (25 rows per page) and a result count in the page title.
- Default sort: highest score first.

What to do: filter to your area of interest (for example High priority + your entity), then click a row to open **Anomaly Detail**.

What **not** to conclude: presence in the queue only means a model flagged the record. Absence from the queue does not certify a record as clean.

---

## G. How to read an anomaly

For each row you should hold four facts together:

1. **Score** — how extreme the record looks to the model (0–1).
2. **Priority badge** — a display convenience derived from the score thresholds above.
3. **Model** — which algorithm produced this flag (`isolation_forest` or `local_outlier_factor`). The same contract can appear once per model.
4. **Explanation** — *why* the score is high, in feature-contribution terms.

A record can be flagged by one model and not the other; that disagreement is normal (see [EVALUATION.md](EVALUATION.md) overlap section).

---

## H. Anomaly Detail page

**URL:** `/anomalies/<contract_id>/`  
**Purpose:** The investigation workspace for a single flagged record.

Layout:

| Panel | What it shows |
|---|---|
| Header | Contract ID, title, Priority badge, back link |
| Disclaimer | Reminder that a flag is not a determination of wrongdoing |
| **Anomaly Score** | Score value, Rank (# among all anomalous flags), Model name, Flagged timestamp |
| **Why This Was Flagged** | Natural-language explanation generated from SHAP contributions |
| **Feature Contributions** | Rule-based contribution bars with High/Moderate/Lower levels derived from stored feature values |
| **Feature Impact Summary** | Simplified chart from stored force-plot data (which features pushed the score higher or lower). The table above it is authoritative. |
| **Contract Details** | NOCOPO ID, title, description, entity, vendor, amount, award date, number of bidders |
| **Feature Values** | Stored values for log contract value, single bidder, win frequency, splitting flag/count |
| **Investigation** | Buttons: Create Investigation Report / View Existing Reports |

Reading order we recommend: Disclaimer → Score/Rank → Why This Was Flagged → Feature Contributions → Contract Details → decide.

What **not** to conclude: “High” priority ≠ fraud. The rank tells you position among flagged scores, not severity of any offence.

---

## I. Risk / anomaly score

- Stored in `anomaly_flags.risk_score`, range **0 to 1**.
- **Isolation Forest scores** are min–max normalised inverted model scores across all records, so every record has a score; higher = more unusual.
- **LOF scores** are rank-based **among flagged records only** (uniformly spread across 0–1); non-flagged records store 0.0.
- The raw scikit-learn outputs are **not** what the UI displays; the UI shows the application’s normalised score.
- Scores from different models are not calibrated to each other — compare within a model when precision matters.

---

## J. Priority levels

Computed in the interface as:

| Priority | Condition on score | Meaning in the UI |
|---|---|---|
| **High** | score ≥ 0.80 (and record is flagged anomalous for display contexts that filter on it) | Top band of normalised scores — review first |
| **Medium** | 0.60 ≤ score < 0.80 | Middle band |
| **Normal** | score < 0.60 | Lower band among flagged records |

“High priority” must **never** be described as fraud. It means a high normalised anomaly score under this application’s thresholds.

*(The trainer also logs percentile-based reference thresholds — 95th/80th percentiles — for analysis runs; the on-screen badges use the fixed 0.80/0.60 cut-offs above.)*

---

## K. Natural-language explanation

Found under **Why This Was Flagged**.

- Generated automatically from the stored SHAP feature-importance list when explanations are produced (`run_detection` auto-generates, or `generate_explanations`).
- Always uses neutral wording: “flagged”, “contributed to the anomaly score”, “pushed the anomaly score higher/lower”.
- Always ends with: *“These feature contributions indicate records that may warrant further review. This system flags records for investigation — it does not detect fraud or wrongdoing.”*
- If no stored explanation exists, a short fallback sentence may be assembled from feature values; treat the stored SHAP-based text as the complete explanation.

---

## L. Feature contribution / SHAP display

Two complementary displays:

1. **Feature Contributions table (bars)** — built from the record’s stored feature values using fixed interpretation rules (High/Moderate/Lower). Useful quick context; **not** the SHAP attribution itself.
2. **Feature Impact Summary (chart)** — rendered from `force_plot_data`: each feature’s contribution direction (pushes higher / pushes lower). The contribution table remains the authoritative numeric view.

Under the hood each explanation also stores:

- `shap_values` — full six-feature SHAP vector,
- `feature_importance` — top-5 features by absolute SHAP value with direction and feature value.

---

## M. Contract details

The right-hand **Contract Details** panel is ordinary procurement metadata: who awarded, who received, how much, when, how many bidders, external NOCOPO/OCDS identifier. Use it to orient yourself before judging whether a deeper review is warranted.

---

## N. Human investigation process

The system’s job ends at prioritisation and explanation. Your job:

1. Open the record from the Anomaly Queue.
2. Read the explanation and feature contributions.
3. Check the contract metadata (amount, dates, bidders, vendor history if needed outside the system).
4. Decide: is further review warranted, or is there an innocuous explanation (for example, a genuinely single-source procurement under regulation)?
5. Record your conclusion in an **Investigation Report**.
6. Mark the report Draft or Reviewed.

Nothing in the system auto-escalates, auto-closes, or penalises a vendor.

---

## O. Creating an Investigation Report

From Anomaly Detail → **Create Investigation Report**  
**URL:** `/reports/<contract_id>/create/`

Form fields:

| Field | What to enter |
|---|---|
| **Finding** | Your observations from reviewing the record |
| **Recommendation** | Suggested next step (further review, close, refer, etc.) |
| **Status** | `Draft` (default) or `Reviewed` |

Select **Save Report**. You are returned to the report detail page and a success message shows the new report ID. The report stores your user account as reviewer and a timestamp.

A disclaimer on the form reminds you: an anomaly flag is not a determination of wrongdoing.

---

## P. Investigation Reports

**List URL:** `/reports/`  
**Detail URL:** `/reports/<contract_id>/`

- **List** shows flagged contracts with score, priority, and whether a report already exists; filter by search, priority, entity; paginate (25/page).
- **Detail** shows the contract’s anomaly context (score, priority, contributions, explanation) plus all investigation reports for that contract (latest highlighted), with links to create another report or jump to Anomaly/Record Detail.

---

## Q. Records

**URL:** `/records/`  
**Purpose:** Browse **all** imported contracts (flagged and not).

Filters: search (title, ID, description, NOCOPO ID, entity, vendor), entity, vendor, method, category, flagged yes/no, date range. Sorting by date, amount, ID, title. Pagination 25/page.

Use this when you need the full population, not only flagged rows.

---

## R. Record Detail

**URL:** `/records/<contract_id>/`  
Full contract view with whatever anomaly assessment exists: priority, rank, feature values, explanation, and links to Anomaly Detail and Investigation Reports. Records with no flag show that no anomaly flag exists — that is not a certificate of regularity.

---

## S. Analysis Runs

**URL:** `/analysis-runs/` (also `/analytics/runs/`)  
History of detection executions persisted in the `analysis_runs` table: date, model, records processed, anomalies found, contamination, average score, duration, status.

Runs are created when detection is executed with saving enabled (`python manage.py run_detection ...`). The page is read-only.

---

## T. Model Performance

**URL:** `/model-performance/` (also `/analytics/performance/`)  
Live analytics screen:

- Per-model cards: total flag rows, anomalies flagged, anomaly rate, average score, High/Medium/Normal breakdown.
- Score distribution comparison chart (IF vs LOF).
- **Synthetic Anomaly Evaluation** table: Precision/Recall/F1 and confusion counts computed **in the browser request** by injecting 5% synthetic anomalies into the current feature matrix.
- Contamination sensitivity table (0.01 / 0.03 / 0.05 / 0.10).

Important: the synthetic metrics on this page are **controlled evaluation figures**, not real-world fraud-detection accuracy. See [EVALUATION.md](EVALUATION.md).

---

## U. Import Dataset (Administrator only)

**URL:** `/ingestion/import/`

Two ways to load data:

1. **Upload CSV** — choose a CSV file → **Upload & Import**.
2. **Download from OCP** — **Download from OCP** button fetches the Publication 64 bundle.

The screen reports import statistics (raw rows staged) and validation statistics (valid vs invalid). Valid rows become `contracts`; invalid rows stay in staging with error details.

After import you (or an operator) must run feature generation and detection (see README quick commands) before new flags appear.

Auditors never see this menu item; direct access redirects them away.

---

## V. Users (Administrator only)

**URL:** `/system/users/`, `/system/users/create/`, `/system/users/<id>/edit/`

- **List** — all accounts with role and status; **New User** button.
- **Create** — username, email, password, confirm password. New accounts are always created as **Auditor**. Administrator accounts must be created via Django admin or management commands (stated on the screen).
- **Edit** — activate/deactivate an account (you cannot deactivate your own account).

---

## W. Settings (Administrator only)

**URL:** `/system/settings/`

Read-only panels:

- System information (application name, version label, environment).
- Dataset counts: contracts, feature records, anomaly flags (flagged vs total).
- Detection models: active models (Isolation Forest, Local Outlier Factor), the six feature names, default contamination 0.05.

---

## X. Profile and logging out

- **Profile** — `/accounts/profile/`: username, email, role badge, date joined, last login.
- **Logout** — sidebar/footer logout link (`/accounts/logout/`): ends the session and returns to the login page with a confirmation message.
- Sessions use Django’s standard session middleware; closing the browser does not log you out until the session expires or you log out explicitly.

---

## Complete end-to-end walkthrough

```
1.  Login                     /accounts/login/
2.  Dashboard                 /            — orient yourself with counts and queue
3.  Anomaly Queue             /anomalies/  — filter (e.g. Priority = High)
4.  Open an anomaly           click a row  — /anomalies/<id>/
5.  Read the explanation      “Why This Was Flagged” + contribution bars/chart
6.  Examine procurement info  Contract Details + Feature Values panels
7.  Decide                    Is further review warranted for a human?
8.  Create Investigation Report   /reports/<id>/create/ — finding, recommendation, status
9.  Review the report         /reports/<id>/ — confirm content; set Reviewed when done
10. Return to queue           /anomalies/ — continue with the next record
```

### Example session (illustrative)

1. You log in as an Auditor.
2. Dashboard shows the imported dataset and a Priority Queue of the top 10 scores.
3. You open **Anomaly Queue**, set Priority = High, and sort by score.
4. You open contract **#1234**. The score card shows e.g. `0.97`, rank #3, model `isolation_forest`.
5. The explanation says the record was flagged primarily because of single-bidder procurement, with vendor win frequency also pushing the score higher — and ends with the standard non-fraud disclaimer.
6. Contract details show one bidder, a large amount, and a familiar vendor for that entity.
7. You decide a brief desk review is warranted (or you decide it is explainable and close the thought — your judgment).
8. You create an Investigation Report: finding = what you observed; recommendation = e.g. “Request bidding documents for review”; status = Draft.
9. Later you set it to Reviewed when your check is complete.

---

## Empty and error states you may see

| Situation | What the system shows |
|---|---|
| No contracts imported | Dashboard empty state; Import button for Administrators |
| No flags yet | Anomaly Queue / Priority Queue empty states (“Run an analysis…”) |
| No analysis runs | Analysis Runs empty state with the `run_detection` hint |
| Auditor opens admin URL | Redirect to dashboard + error message |
| Wrong login credentials | Form validation error; no session created |
| Import failure | Error banner on the Import Dataset screen with the exception text |

---

## Where to go next

- Technical design: [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- How the scores and explanations are produced: [ML_METHODOLOGY.md](ML_METHODOLOGY.md)
- What the numbers in evaluation mean: [EVALUATION.md](EVALUATION.md)
- What you must never claim from this tool: [LIMITATIONS.md](LIMITATIONS.md)
