# Product Audit, UX Architecture & Design System

**Project:** Design and Implementation of an Explainable Anomaly-Screening System for Nigerian Public Procurement Records
**Date:** 2026-09-08
**Status:** Audit + IA + Design System (no screens yet)

---

## Part 1: Product Audit

### 1.1 What Exists

| Layer | Component | Status |
|-------|-----------|--------|
| **Models** | User (with Administrator/Auditor roles) | Complete |
| | ProcuringEntity, Vendor, Contract | Complete |
| | RawRecord (staging table) | Complete |
| | Feature (7 fields, 1:1 with Contract) | Complete |
| | AnomalyFlag (risk_score, model_used, is_anomaly) | Model only — no detection logic |
| | Explanation (shap_values, feature_importance, force_plot_data, natural_language) | Model only — no SHAP logic |
| **Auth** | Login, Register, Profile, Logout | Complete — functional |
| **Ingestion** | OCP CSV download, staging import, validation, Contract creation | Complete — functional |
| **Preprocessing** | Date cleaning (outlier years 1949/2919), missing values, dedup, quality report | Complete — functional |
| **Features** | All 7 features computed (log_value, single_bidder, win_frequency, win_concentration, price_deviation, splitting_flag, splitting_count) | Complete — functional |
| **Detection** | Isolation Forest, LOF | Empty — Sprint 2 |
| **Explainability** | SHAP, LIME, NL explanations, force plots | Empty — Sprint 2 |
| **Dashboard** | Index, Anomaly Queue, Anomaly Detail | Stubs — hardcoded `--`, no queries |
| **Reporting** | Investigation Report | Stub — no generation logic |
| **Static** | custom.css (12 lines), no JS files | Minimal |

### 1.2 Bugs Found

| # | Location | Issue |
|---|----------|-------|
| 1 | `apps/preprocessing/pipeline.py:49,66` | Calls `generate_quality_report` and `save_processed_data` — neither is imported. `NameError` at runtime. |
| 2 | `apps/ingestion/services/validators.py` | Dead code. `validate_ocds_release()` expects OCDS JSON but `csv_importer.py` uses `_validate_mapped_record()` on flat dicts instead. Never called. |
| 3 | `apps/accounts/forms.py` + `apps/accounts/views.py` | **Public self-registration with role selection is a security vulnerability.** The RegistrationForm exposes the `role` field, allowing any visitor to create an Administrator account. The `register_view` has no authentication check and auto-logs in the new user. Fix: remove public self-registration entirely. Administrator accounts are created via Django admin or `createsuperuser`/`create_user` management commands. Auditor accounts are created by Administrators through the Users management screen. The `/accounts/register/` URL is removed from the nav and the view is restricted to Administrators. |

### 1.3 Design-Relevant Gaps

| Gap | Impact |
|-----|--------|
| No design system | Templates use raw Bootstrap 5 defaults — no visual identity |
| No navigation system | Base template has a basic dark navbar — no sidebar, no section hierarchy |
| All page templates are stubs | No data tables, no charts, no filters, no empty/loading states |
| No data visualization | Chart.js is loaded via CDN but never used |
| No static JS | charts.js, force_plot.js, filters.js don't exist |
| No component architecture | No reusable template components (stats cards, filter bars, table rows, etc.) |
| No page states | No empty states, loading states, error states, or success states defined |
| No role-aware UI | Admin-only items are hidden via `{% if %}` but no visual differentiation between role experiences |

---

## Part 2: UX Architecture

### 2.1 Registration Policy (Security)

**Public self-registration is removed.** The proposal defines two roles (Administrator, Auditor) and requires role-based access control. Allowing any visitor to self-register with role selection violates this model.

- **Administrator accounts:** Created via Django management command (`createsuperuser`) or Django admin. No web form for self-registration.
- **Auditor accounts:** Created by Administrators through the Users management screen (`/admin/users/`).
- **`/accounts/register/` URL:** The view is restricted to Administrators only. The template is retained for potential future use but is not linked from any navigation.
- **`RegistrationForm`:** The `role` field is removed from the form. If the register view is ever re-exposed, it must default to Auditor and not accept role as input.

This matches the proposal's Role Permissions matrix (Section 10): "Manage users" is Administrator-only.

### 2.2 Information Architecture (Final)

```
Procurement Intelligence System
│
├── Authentication
│   ├── Login                          /accounts/login/
│   └── Profile                        /accounts/profile/
│
├── Overview
│   └── Dashboard                      /
│
├── Investigation
│   ├── Anomaly Queue                  /anomalies/
│   ├── Anomaly Detail                 /anomalies/<id>/
│   └── Investigation Reports          /reports/
│       └── Report Detail              /reports/<id>/
│
├── Procurement Data
│   ├── Records                        /records/
│   ├── Record Detail                  /records/<id>/
│   └── Import Dataset                 /ingestion/import/    [Admin only]
│
├── Analytics
│   ├── Analysis Runs                  /analytics/runs/
│   └── Model Performance              /analytics/performance/
│
└── Administration                     [Admin only]
    ├── Users                          /admin/users/
    └── Settings                       /admin/settings/
```

**14 screens.** No public registration. Admin-only sections are visually tagged in the sidebar and enforced server-side.

### 2.2 Page Hierarchy & Navigation Relationships

```
                    ┌─────────────┐
                    │   Login     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌─────┤  Dashboard  ├─────┐
              │     └──────┬──────┘     │
              │            │            │
       ┌──────▼──────┐    │    ┌───────▼───────┐
       │   Anomaly   │    │    │    Records    │
       │   Queue     │    │    │    List       │
       └──────┬──────┘    │    └───────┬───────┘
              │            │            │
       ┌──────▼──────┐    │    ┌───────▼───────┐
       │   Anomaly   │    │    │ Record Detail │
       │   Detail    │◄───┘    └───────────────┘
       └──────┬──────┘
              │
       ┌──────▼──────┐
       │ Investigation│
       │ Report       │
       └─────────────┘

  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ Analysis     │    │    Model     │    │    Import    │
  │ Runs         │    │  Performance │    │   Dataset    │
  └──────────────┘    └──────────────┘    └──────────────┘

  ┌──────────────┐    ┌──────────────┐
  │    Users     │    │   Settings   │
  └──────────────┘    └──────────────┘
```

### 2.3 User Journeys

**Auditor/Reviewer — Investigation Flow:**
1. Login → Dashboard (sees overview stats: total records, flagged count, high-risk count)
2. Click "Anomaly Queue" → ranked list sorted by risk_score DESC, with priority badges, filters (date range, MDA, priority level, search)
3. Click row → Anomaly Detail (contract metadata, SHAP force plot, natural-language explanation, feature contributions table, action buttons: "Generate Report", "Back to Queue")
4. Click "Generate Report" → Investigation Report (formatted summary with all evidence, download as PDF/CSV)
5. Can also browse Records list, search/filter, click into Record Detail

**Administrator — System Management Flow:**
1. Login → Dashboard (same overview + additional system health indicators)
2. Click "Import Dataset" → upload/download OCP data, view import stats, validation results
3. Click "Users" → user list, create/edit/deactivate accounts, assign roles
4. Click "Settings" → model parameters, contamination threshold, notification preferences
5. All Auditor journeys also available

### 2.4 Navigation Design

**Sidebar navigation** (not top navbar). Rationale: 14 screens across 5 sections need persistent, scannable navigation. A top navbar cannot accommodate this without overflow/hamburger menus on every screen.

```
┌─────────────────────────────────────────────────────┐
│  PROCUREMENT INTELLIGENCE              [collapse]    │
│  ─────────────────────────────────────────────────  │
│                                                      │
│  OVERVIEW                                            │
│  ┌────────────────────────────────────────────────┐ │
│  │ ◉ Dashboard                                    │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  INVESTIGATION                                       │
│  ┌────────────────────────────────────────────────┐ │
│  │ ○ Anomaly Queue                               │ │
│  │ ○ Investigation Reports                        │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  PROCUREMENT DATA                                    │
│  ┌────────────────────────────────────────────────┐ │
│  │ ○ Records                                      │ │
│  │ ○ Import Dataset          [ADMIN]              │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ANALYTICS                                           │
│  ┌────────────────────────────────────────────────┐ │
│  │ ○ Analysis Runs                                │ │
│  │ ○ Model Performance                            │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ADMINISTRATION              [ADMIN ONLY]            │
│  ┌────────────────────────────────────────────────┐ │
│  │ ○ Users                                        │ │
│  │ ○ Settings                                     │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ─────────────────────────────────────────────────  │
│  ○ Bright Oghor          Administrator              │
│    bright@university.edu  ● Online                  │
│                          [Logout]                    │
└─────────────────────────────────────────────────────┘
```

**Sidebar states:**
- **Expanded** (default on desktop): Icons + labels, 240px wide
- **Collapsed** (toggle or mobile): Icons only, 64px wide, tooltips on hover
- **Mobile** (<768px): Off-canvas drawer, triggered by hamburger in top bar

**Top bar** (thin, secondary): Contains page title/breadcrumb, global search (future), notifications bell (future), user avatar dropdown. 48px height.

### 2.5 Screen Specifications (14 Screens)

Each screen is defined by: purpose, primary user, primary goal, the question it answers, actions, information displayed, navigation relationships, permissions, and important states.

---

#### Screen 1: Login

| Attribute | Value |
|-----------|-------|
| **Purpose** | Authenticate a user and establish a session |
| **Primary user** | All users (Administrator, Auditor) |
| **Primary user goal** | Access the system |
| **Primary question** | "Who am I and am I allowed in?" |
| **Primary action** | Submit credentials (username + password) |
| **Secondary actions** | None — no public registration link |
| **Information displayed** | System name + brief description, username field, password field, login button, error message on failure |
| **Navigation relationships** | Entry point. After login → Dashboard. No other destination. |
| **Permissions** | Public (unauthenticated). Redirects to Dashboard if already authenticated. |
| **Important states** | Empty form, invalid credentials (error alert), successful login (redirect), already authenticated (auto-redirect to Dashboard) |

---

#### Screen 2: Profile

| Attribute | Value |
|-----------|-------|
| **Purpose** | Display the current user's account information |
| **Primary user** | All authenticated users |
| **Primary user goal** | Verify my account details |
| **Primary question** | "What account am I logged in as?" |
| **Primary action** | None (read-only) |
| **Secondary actions** | Navigate to Dashboard, navigate to Logout |
| **Information displayed** | Username, email, role (Administrator/Auditor), account creation date, last login |
| **Navigation relationships** | Accessible from sidebar user footer or topbar avatar. Links back to Dashboard. |
| **Permissions** | Any authenticated user. Only sees own profile. |
| **Important states** | Profile loaded, profile with minimal data (e.g., no email set) |

---

#### Screen 3: Dashboard

| Attribute | Value |
|-----------|-------|
| **Purpose** | Provide an immediate overview of system state and priority items |
| **Primary user** | All authenticated users |
| **Primary user goal** | Understand the current state of procurement data and anomalies at a glance |
| **Primary question** | "What is the current state and what needs my attention?" |
| **Primary action** | Click into Anomaly Queue to begin investigation |
| **Secondary actions** | Click into Records list, view Analysis Runs |
| **Information displayed** | **Summary statistics:** total contracts in system, total flagged for review, high-priority count, last import date. **Visual context:** chart showing anomaly score distribution (histogram or density plot), chart showing flagging rate over time or by MDA. **Priority queue preview:** top 5 highest-risk anomalies as a compact table with link to full Anomaly Queue. |
| **Navigation relationships** | Central hub. Links to Anomaly Queue, Records, Analysis Runs. Sidebar provides access to all sections. |
| **Permissions** | All authenticated users see the same dashboard. Admin may see additional system health indicators (future). |
| **Important states** | Data present (charts + stats populated), no data imported yet (empty state with link to Import Dataset), partial data (quality warnings displayed) |

**Chart guidance:** The dashboard uses 2–3 charts maximum. Charts must answer specific analytical questions: "What does the distribution of anomaly scores look like?" (histogram), "Which MDAs have the most flagged records?" (horizontal bar chart). No decorative charts. See Anti-Dashboard-Theatre Rule (Section 3.1).

---

#### Screen 4: Anomaly Queue

| Attribute | Value |
|-----------|-------|
| **Purpose** | Present all flagged procurement records ranked by anomaly score for investigation prioritisation |
| **Primary user** | Auditor/Reviewer (primary), Administrator |
| **Primary user goal** | Identify which records to investigate first |
| **Primary question** | "Which records are most anomalous and which should I investigate first?" |
| **Primary action** | Click a row to view Anomaly Detail |
| **Secondary actions** | Filter by priority level, date range, MDA, search by title/vendor/ID, sort by score/date/amount, export filtered list (CSV) |
| **Information displayed** | **Data table columns:** priority badge (High/Medium/Normal), contract title, procuring entity (MDA), vendor name, amount (₦), award date, anomaly risk score (numeric, monospace), model used. **Filter bar:** search input, priority dropdown, date range, MDA dropdown. **Pagination:** page X of Y, total records count. |
| **Navigation relationships** | From Dashboard (click "View all anomalies" or priority queue). Each row → Anomaly Detail. Back button returns to Queue. |
| **Permissions** | All authenticated users. No role restriction. |
| **Important states** | Records present (table populated), no anomalies flagged yet (empty state: "No anomalies have been flagged. Run detection first."), no results matching filters (empty state: "No records match your filters."), loading (skeleton rows) |

**Table guidance:** This is the primary investigative interface. The table must be dense, sortable, and filterable. Priority badges use the muted colour scheme — never alarming. The risk score is displayed as a number (e.g., 0.87), not as a percentage or probability.

---

#### Screen 5: Anomaly Detail

| Attribute | Value |
|-----------|-------|
| **Purpose** | Present all information about a single flagged record for investigation |
| **Primary user** | Auditor/Reviewer (primary), Administrator |
| **Primary user goal** | Understand why this specific record was flagged and decide on next steps |
| **Primary question** | "Why was this record flagged and what does the evidence show?" |
| **Primary action** | Read the explanation, review the evidence |
| **Secondary actions** | Generate Investigation Report, navigate to Record Detail, navigate to Vendor history, return to Anomaly Queue (previous/next navigation) |
| **Information displayed** | **Contract metadata panel:** title, amount (₦), award date, procuring entity, vendor, bidding window, number of bidders, procurement method, category. **SHAP force plot:** Chart.js visualization showing which features pushed the score higher or lower, with feature names and contribution values. **Natural-language explanation:** 2–3 sentences in plain English explaining the key contributing factors. Language must say "contributed to the anomaly score" — never "indicates fraud." **Feature contributions table:** each feature name, raw value, contribution to score, direction (positive/negative). **Investigation actions:** button to generate report, link to related records. |
| **Navigation relationships** | From Anomaly Queue (click row). Previous/Next anomaly buttons. Links to Record Detail, Investigation Report, vendor history. |
| **Permissions** | All authenticated users. |
| **Important states** | Full data present (explanation + chart + metadata), record has no explanation yet (partial state: metadata only, "Explanation pending"), record not found (404) |

**Language rule:** Every explanation must pass this test: if you replace "anomaly score" with "fraud score," the sentence becomes inappropriate. The system flags for review. It does not detect fraud.

---

#### Screen 6: Investigation Reports (List)

| Attribute | Value |
|-----------|-------|
| **Purpose** | List all generated investigation reports for review and management |
| **Primary user** | Auditor/Reviewer (primary), Administrator |
| **Primary user goal** | Find and access previously generated reports |
| **Primary question** | "What reports have been generated and can I access them?" |
| **Primary action** | Click a report to view Report Detail |
| **Secondary actions** | Filter by date range, status, MDA. Sort by date generated, contract title. |
| **Information displayed** | **Data table columns:** report date, contract title, MDA, vendor, risk score, priority badge, report status (Draft/Final), generated by (user). **Filter bar:** date range, status dropdown, search. |
| **Navigation relationships** | From sidebar. Each row → Report Detail. From Anomaly Detail → "Generate Report" creates a new report and navigates here. |
| **Permissions** | All authenticated users can view. Only the generating user or Admin can delete. |
| **Important states** | Reports exist (table populated), no reports generated yet (empty state: "No investigation reports have been generated. Visit the Anomaly Queue to begin."), no results matching filters |

---

#### Screen 7: Report Detail

| Attribute | Value |
|-----------|-------|
| **Purpose** | Display a complete investigation report for a single anomaly |
| **Primary user** | Auditor/Reviewer (primary), Administrator |
| **Primary user goal** | Review all evidence and findings for a specific flagged record in a structured format |
| **Primary question** | "What is the complete picture for this flagged record?" |
| **Primary action** | Read the report, download as PDF or CSV |
| **Secondary actions** | Print report, navigate to Anomaly Detail, navigate to Record Detail, share/link report |
| **Information displayed** | **Report header:** report ID, generation date, generated by, status. **Contract summary:** all metadata fields. **Risk assessment:** anomaly score, priority level, model used. **SHAP explanation:** force plot + natural-language summary. **Feature analysis table:** all features with values and contributions. **Investigation notes:** free-text area for auditor notes (future). **Footer:** disclaimer — "This report is generated by an anomaly screening system. Anomaly scores indicate records flagged for review and do not constitute evidence of fraud or wrongdoing." |
| **Navigation relationships** | From Investigation Reports list. Links to Anomaly Detail, Record Detail. Back to Reports list. |
| **Permissions** | All authenticated users can view. Admin can manage (delete/archive). |
| **Important states** | Report fully generated, report partially generated (pending explanation), report not found (404) |

---

#### Screen 8: Records (List)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Browse all procurement records in the system regardless of anomaly status |
| **Primary user** | Auditor/Reviewer, Administrator |
| **Primary user goal** | Find and examine specific procurement contracts |
| **Primary question** | "What procurement records exist in the system?" |
| **Primary action** | Click a row to view Record Detail |
| **Secondary actions** | Search by title/vendor/ID/MDA, filter by date range/method/category/MDA, sort by any column, export filtered list (CSV) |
| **Information displayed** | **Data table columns:** contract title, procuring entity, vendor, amount (₦), award date, method, category, num bidders, anomaly status (flagged/not flagged, with badge if flagged). **Filter bar:** search input, method dropdown, category dropdown, date range, anomaly status filter. **Pagination.** |
| **Navigation relationships** | From sidebar. Each row → Record Detail. From Dashboard. |
| **Permissions** | All authenticated users. |
| **Important states** | Records present, no records imported yet (empty state: "No procurement records have been imported. Use Import Dataset to begin."), no results matching filters |

---

#### Screen 9: Record Detail

| Attribute | Value |
|-----------|-------|
| **Purpose** | Display complete information about a single procurement contract |
| **Primary user** | Auditor/Reviewer, Administrator |
| **Primary user goal** | Examine all details of a specific contract |
| **Primary question** | "What are the complete details of this contract?" |
| **Primary action** | Review contract metadata |
| **Secondary actions** | View anomaly status (link to Anomaly Detail if flagged), view vendor history, view entity history, navigate to previous/next record |
| **Information displayed** | **Contract metadata:** title, amount (₦), award date, procurement method, category, description. **Parties:** procuring entity (name, type, state), vendor (name, CAC number, state). **Competition:** bidding window days, number of bidders. **System data:** NOCOPO ID, anomaly status, anomaly score (if flagged), feature values (if computed), import date. |
| **Navigation relationships** | From Records list (click row), from Anomaly Detail (link to source record). Links to vendor history, entity history. Previous/Next navigation. |
| **Permissions** | All authenticated users. |
| **Important states** | Full record present, record with missing optional fields, record not found (404), record not yet scored (anomaly status pending) |

---

#### Screen 10: Import Dataset

| Attribute | Value |
|-----------|-------|
| **Purpose** | Import procurement data from the OCP Data Registry into the system |
| **Primary user** | Administrator only |
| **Primary user goal** | Get new or updated procurement data into the system for analysis |
| **Primary question** | "How do I get procurement data into the system?" |
| **Primary action** | Click "Download & Import" to pull data from OCP |
| **Secondary actions** | View import history, view validation results, view data quality report |
| **Information displayed** | **Import action:** button to trigger download + import pipeline. **Data source info:** OCP Data Registry URL, file format, approximate size. **Import results (after run):** total rows downloaded, rows imported, rows skipped, rows with errors, validation results. **Known dataset properties:** callout box documenting the 1949/2919 date outliers, 2021 release-date clustering, 93 incorrect OCID prefixes. **Data quality report (after import):** missing values per field, duplicate count, outlier counts. |
| **Navigation relationships** | From sidebar (Admin-only section). Links to Records (to view imported data), to Analysis Runs (to track pipeline execution). |
| **Permissions** | Administrator only. Auditor sees 403 or redirect. |
| **Important states** | Ready to import (idle), import in progress (loading state with progress), import complete (results displayed), import failed (error with details), already imported (shows last import stats with option to re-import) |

---

#### Screen 11: Analysis Runs

| Attribute | Value |
|-----------|-------|
| **Purpose** | Track and review past detection model execution runs |
| **Primary user** | Administrator (primary), Auditor |
| **Primary user goal** | Understand when detection was last run, what parameters were used, and what the results were |
| **Primary question** | "When was detection last run and what happened?" |
| **Primary action** | Click a run to view its details |
| **Secondary actions** | Trigger a new detection run (Admin), compare runs, view model performance for a specific run |
| **Information displayed** | **Data table columns:** run date/time, model used (Isolation Forest / LOF), parameters (contamination, n_estimators), records processed, anomalies flagged, execution time, status (completed/failed/running). **Run detail (expandable or modal):** parameter snapshot, data snapshot used, output summary, any errors or warnings. |
| **Navigation relationships** | From sidebar. Each row → run detail (expanded inline or modal). Links to Model Performance for that run. |
| **Permissions** | All authenticated users can view. Only Admin can trigger new runs. |
| **Important states** | Runs exist (table populated), no runs yet (empty state: "No detection runs have been executed. Use the Analytics pipeline to run anomaly detection."), run in progress (live-updating row), run failed (error details) |

---

#### Screen 12: Model Performance

| Attribute | Value |
|-----------|-------|
| **Purpose** | Evaluate and compare the performance of anomaly detection models |
| **Primary user** | Administrator (primary), Auditor |
| **Primary user goal** | Understand how well the detection models are performing |
| **Primary question** | "How accurate and reliable are the detection results?" |
| **Primary action** | Review performance metrics and visualisations |
| **Secondary actions** | Compare Isolation Forest vs LOF, view per-model metrics, adjust contamination threshold (Admin), view explanation fidelity |
| **Information displayed** | **Model comparison table:** model name, precision@K, precision, recall, F1 score, AUC (if available), number of anomalies flagged, contamination parameter. **Charts:** precision-recall curve, ROC curve (if labelled data exists), anomaly score distribution histogram, feature importance ranking. **Explanation fidelity:** percentage of explanations that pass manual review, sample explanation quality. **Performance benchmarks:** processing time on 16GB RAM, memory usage. |
| **Navigation relationships** | From sidebar. Links to Analysis Runs (specific run performance). Links to Anomaly Queue (to see results). |
| **Permissions** | All authenticated users can view. Only Admin can adjust parameters. |
| **Important states** | Performance data available (charts + table), no models trained yet (empty state: "No model performance data. Run anomaly detection first."), partial metrics (some models not yet evaluated) |

---

#### Screen 13: Users

| Attribute | Value |
|-----------|-------|
| **Purpose** | Manage user accounts and roles |
| **Primary user** | Administrator only |
| **Primary user goal** | Create, modify, and deactivate user accounts |
| **Primary question** | "Who has access to the system and what can they do?" |
| **Primary action** | Create new user, edit existing user, deactivate user |
| **Secondary actions** | Search users, filter by role, view user activity (future), reset password |
| **Information displayed** | **Data table columns:** username, email, role (Administrator/Auditor badge), status (Active/Inactive), last login, date joined. **User create/edit form:** username, email, role (dropdown: Administrator/Auditor), password (for new users), is_active toggle. **User detail (modal or inline):** full account info, activity log (future). |
| **Navigation relationships** | From sidebar (Admin-only section). Create/Edit via modal or separate form page. |
| **Permissions** | Administrator only. Auditor sees 403 or redirect. |
| **Important states** | Users present (table populated), create user form, edit user form, confirm deactivation (modal), user not found (404) |

---

#### Screen 14: Settings

| Attribute | Value |
|-----------|-------|
| **Purpose** | Configure system-wide parameters for anomaly detection and application behaviour |
| **Primary user** | Administrator only |
| **Primary user goal** | Adjust detection parameters and system configuration |
| **Primary question** | "How should the system behave and what parameters should the models use?" |
| **Primary action** | Save configuration changes |
| **Secondary actions** | Reset to defaults, view configuration history (future) |
| **Information displayed** | **Detection parameters:** contamination threshold (slider/input, default 0.05), priority thresholds (high %, medium %), n_estimators, max_samples. **Data source configuration:** OCP Data Registry URL, auto-import schedule (future). **Display preferences:** items per page, default sort order. **System information:** version, database size, last backup. |
| **Navigation relationships** | From sidebar (Admin-only section). Save button commits changes. |
| **Permissions** | Administrator only. Auditor sees 403 or redirect. |
| **Important states** | Settings loaded (form populated with current values), saving (loading state), saved (success confirmation), validation error (invalid parameter values), reset to defaults (confirmation modal) |

---

### 2.6 Proposal Fidelity Cross-Check

| Proposal Requirement | Screen(s) | Status |
|---------------------|-----------|--------|
| FR1: Pull/upload raw procurement data | Screen 10 (Import Dataset) | Covered |
| FR2: Validate and clean raw records | Screen 10 (import results + quality report) | Covered |
| FR3: Risk-feature engineering | Backend (no dedicated screen needed) | Covered — feature values shown in Record Detail and Anomaly Detail |
| FR4: Anomaly detection (IF + LOF) | Screen 11 (Analysis Runs), Screen 12 (Model Performance) | Covered |
| FR5: SHAP explanation per flagged record | Screen 5 (Anomaly Detail) | Covered |
| FR6: Dashboard summary stats | Screen 3 (Dashboard) | Covered |
| FR7: Ranked anomaly list with filters | Screen 4 (Anomaly Queue) | Covered |
| FR8: Investigation report generation/download | Screen 6 (Reports list), Screen 7 (Report Detail) | Covered |
| FR9: Auth, Administrator/Auditor roles, permissions | Screen 1 (Login), Screen 2 (Profile), Screen 13 (Users) | Covered |
| Role: Import/upload data = Admin only | Screen 10 restricted to Admin | Covered |
| Role: Manage users = Admin only | Screen 13 restricted to Admin | Covered |
| Role: Configure model parameters = Admin only | Screen 14 restricted to Admin | Covered |
| Role: View dashboard/anomalies/reports = All | Screens 3, 4, 5, 6, 7, 8, 9 available to all | Covered |
| Data source: NOCOPO primary, OCP fallback | Screen 10 imports from OCP Data Registry | Covered (OCP is the confirmed primary per user clarification) |
| Ethics: never present scores as fraud | Language rules enforced in Screen 5 explanation templates | Covered |
| Evaluation: Precision@K, synthetic injection | Screen 12 (Model Performance) | Covered |
| SUS usability study | Not a screen — research methodology | Not applicable to UI |

**No major functionality gaps found.** All proposal requirements map to existing or planned screens.

---

## Part 3: Design System

### 3.1 Design Rationale

This system processes sensitive procurement data where misinterpretation has real consequences. Every design choice must support accuracy, calm analysis, and ethical communication. The palette is deliberately muted — this is not a product that should feel "exciting" or "modern" in the consumer-app sense. It should feel trustworthy, precise, and institutional.

**Why these colours:** Slate-based neutrals provide enough contrast for long reading sessions without the harshness of pure black/white. The primary blue is desaturated to avoid competing with data visualisation colours. Priority colours are muted — a procurement record flagged as high-priority should feel serious, not alarming. No saturated reds or greens that might imply "guilty/innocent."

**Why this typography:** Inter is the most legible sans-serif at small sizes on screens. The type scale is tight — this is an information-dense product, not a marketing page. We need to fit tables, filters, charts, and explanations on screen without excessive scrolling.

**Why 8pt spacing:** Consistent rhythm across all components. 8px base means all spacing decisions are multiples of a single unit — eliminates "is this 13px or 15px?" debates.

#### Anti-Dashboard-Theatre Rule

Every visual element on every screen must pass this test: **"What decision does this help the user make, or what question does it answer?"**

If the answer is "it makes the page look more professional" or "it shows activity" or "it fills space," the element is removed. This applies to: KPI cards, charts, badges, colour usage, icons, animations, loading indicators, progress bars, decorative illustrations, and any other visual component.

Specific application:
- **Charts** must answer an analytical question. "What is the distribution of anomaly scores?" justifies a histogram. "How many records were imported this month?" justifies a time series. "System health" without specific metrics does not justify a chart.
- **KPI cards** on the Dashboard must show numbers the user needs to make decisions: total flagged (do I have work to do?), high-priority count (what needs attention now?), last import date (is the data current?). Do not show "total records" alone — it is not actionable without context.
- **Badges** must communicate status or priority that affects the user's next action. A badge that says "Active" on every row with no filtering capability is decorative.
- **Animations** are restricted to: loading skeletons (communicates "wait, data is coming"), focus transitions (communicates "your click was received"), and nothing else. No pulsing, no bouncing, no decorative motion.
- **Icons** must be accompanied by text labels in the sidebar. Icon-only navigation without tooltips is inaccessible.

#### Tables vs Visualisations

Data tables are the primary investigative interface for the Anomaly Queue, Records, Reports, Users, and Analysis Runs screens. However, **not every screen is table-driven.** The guiding principle:

- **Use a table** when the user needs to scan, compare, sort, filter, or take action on multiple items. Tables are for lists of records where each row is an entity the user might act on.
- **Use a chart** when the user needs to understand a distribution, trend, comparison, or relationship across the dataset. Charts answer analytical questions that a table cannot.
- **Use a combination** when the user needs both overview context and item-level detail. The Dashboard uses charts for overview context plus a compact table for the top-priority items.

Screen-by-screen guidance:
| Screen | Primary layout | Rationale |
|--------|---------------|-----------|
| Dashboard | Charts + compact table | Overview context requires visual summaries; top anomalies need a quick-access table |
| Anomaly Queue | Full data table | This is a ranked list — the user scans and selects rows |
| Anomaly Detail | Metadata panel + chart + table | SHAP force plot is a chart; feature contributions are a table; metadata is a panel |
| Investigation Reports | Data table | List of reports to access |
| Report Detail | Formatted document | Structured report, not a table or chart |
| Records | Full data table | Browsing a list of contracts |
| Record Detail | Metadata panels | Single-entity detail, no table needed |
| Import Dataset | Action + results | Button + status display, not a data view |
| Analysis Runs | Data table | List of run records |
| Model Performance | Charts + table | Metrics need visual comparison; raw numbers need a table |
| Users | Data table | List of user accounts |
| Settings | Form | Configuration form, not a data view |

### 3.2 CSS Custom Properties

Paste this entire block into `:root` in `base.html` or `custom.css`:

```css
:root {
  /* ═══════════════════════════════════════════════
     COLOUR PALETTE
     Muted, professional, trustworthy.
     No saturated reds/greens that imply guilt/innocence.
     ═══════════════════════════════════════════════ */

  /* Primary — muted navy blue. Trust, stability, authority. */
  --color-primary-50:  #f0f4f8;
  --color-primary-100: #d9e2ec;
  --color-primary-200: #bcccdc;
  --color-primary-300: #9fb3c8;
  --color-primary-400: #829ab1;
  --color-primary-500: #627d98;
  --color-primary-600: #486581;
  --color-primary-700: #334e68;
  --color-primary-800: #243b53;
  --color-primary-900: #102a43;

  /* Neutrals — slate-based, not pure grey. Warmer, easier on eyes. */
  --color-neutral-0:   #ffffff;
  --color-neutral-50:  #f7f9fc;
  --color-neutral-100: #f0f2f5;
  --color-neutral-200: #e1e5eb;
  --color-neutral-300: #cdd3dc;
  --color-neutral-400: #a0aab4;
  --color-neutral-500: #7b8794;
  --color-neutral-600: #626d79;
  --color-neutral-700: #4d5661;
  --color-neutral-800: #37414a;
  --color-neutral-900: #1f2933;

  /* Surfaces */
  --color-bg:          #f7f9fc;        /* Page background */
  --color-surface:     #ffffff;        /* Cards, panels, modals */
  --color-surface-alt: #f0f2f5;        /* Alternating rows, subtle sections */
  --color-border:      #e1e5eb;        /* Default borders */
  --color-border-light:#eef1f5;        /* Lighter dividers */

  /* Text */
  --color-text:        #1f2933;        /* Primary text — near-black */
  --color-text-secondary: #626d79;     /* Secondary text */
  --color-text-muted:  #a0aab4;        /* Captions, placeholders */

  /* Semantic — Priority (muted, not alarming) */
  --color-priority-high:   #c4421a;    /* Muted brick red — serious, not panicked */
  --color-priority-high-bg:#fdf0ec;    /* Very light warm tint */
  --color-priority-med:    #b7791f;    /* Muted amber — caution, not alarm */
  --color-priority-med-bg: #fefcf3;
  --color-priority-low:    #626d79;    /* Neutral slate — no positive/negative connotation */
  --color-priority-low-bg: #f0f2f5;

  /* Semantic — Status */
  --color-success:     #2f855a;
  --color-success-bg:  #f0fff4;
  --color-warning:     #b7791f;
  --color-warning-bg:  #fefcf3;
  --color-error:       #c4421a;
  --color-error-bg:    #fdf0ec;
  --color-info:        #486581;
  --color-info-bg:     #f0f4f8;

  /* ═══════════════════════════════════════════════
     TYPOGRAPHY
     Inter — highly legible at small sizes, professional.
     Three weights only: 400 (body), 500 (emphasis), 600 (headings).
     ═══════════════════════════════════════════════ */

  --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono:   'JetBrains Mono', 'Fira Code', 'Consolas', monospace;

  /* Type scale — tight, information-dense */
  --text-display: 2rem;       /* 32px — page hero titles only */
  --text-h1:      1.5rem;     /* 24px — page titles */
  --text-h2:      1.25rem;    /* 20px — section headings */
  --text-h3:      1.125rem;   /* 18px — card/panel titles */
  --text-h4:      1rem;       /* 16px — subsection headings */
  --text-body:    0.875rem;   /* 14px — default body text */
  --text-small:   0.8125rem;  /* 13px — secondary text, table cells */
  --text-caption: 0.75rem;    /* 12px — captions, timestamps, badges */

  --weight-regular: 400;
  --weight-medium:  500;
  --weight-semibold:600;

  --leading-tight:  1.25;
  --leading-normal: 1.5;
  --leading-relaxed:1.625;

  /* ═══════════════════════════════════════════════
     SPACING SCALE
     8pt base grid. Consistent rhythm everywhere.
     ═══════════════════════════════════════════════ */

  --space-1:  0.25rem;   /* 4px  — inline spacing, icon gaps */
  --space-2:  0.5rem;    /* 8px  — tight gaps, padding in compact elements */
  --space-3:  0.75rem;   /* 12px — input padding, small card padding */
  --space-4:  1rem;      /* 16px — standard padding, gap between related items */
  --space-5:  1.5rem;    /* 24px — section spacing, card padding */
  --space-6:  2rem;      /* 32px — major section breaks */
  --space-7:  3rem;      /* 48px — page-level vertical spacing */
  --space-8:  4rem;      /* 64px — rare, used for hero/empty states */

  /* ═══════════════════════════════════════════════
     BORDER RADIUS
     Restrained. No pill-shapes. Clean geometry.
     ═══════════════════════════════════════════════ */

  --radius-sm:  0.25rem;   /* 4px  — badges, tags, small elements */
  --radius-md:  0.375rem;  /* 6px  — buttons, inputs, cards */
  --radius-lg:  0.5rem;    /* 8px  — modals, large panels */
  --radius-xl:  0.75rem;   /* 12px — feature cards, dash panels */

  /* ═══════════════════════════════════════════════
     SHADOWS
     Two levels only. Subtle, not decorative.
     ═══════════════════════════════════════════════ */

  --shadow-sm:  0 1px 2px rgba(16, 42, 67, 0.06);
  --shadow-md:  0 2px 8px rgba(16, 42, 67, 0.08);
  --shadow-lg:  0 4px 16px rgba(16, 42, 67, 0.10);

  /* ═══════════════════════════════════════════════
     LAYOUT
     ═══════════════════════════════════════════════ */

  --sidebar-width:      240px;
  --sidebar-collapsed:  64px;
  --topbar-height:      48px;

  /* ═══════════════════════════════════════════════
     TRANSITIONS
     Minimal, purposeful. No flashy animations.
     ═══════════════════════════════════════════════ */

  --transition-fast:  150ms ease;
  --transition-base:  200ms ease;
  --transition-slow:  300ms ease;
}
```

### 3.3 Typography Rationale

| Choice | Rationale |
|--------|-----------|
| **Inter** | Designed for screens. Excellent x-height, legible at 12–14px. Used by GitHub, VS Code, Linear. Free via Google Fonts CDN. |
| **14px body** | Standard for information-dense interfaces (Bloomberg, Palantir). 16px is too large for tables with 10+ columns. |
| **3 font weights** | 400/500/600 only. More weights create visual noise without adding hierarchy. Weight alone does enough differentiation. |
| **Tight line-height** | 1.5 for body, 1.25 for headings. Dense text needs tighter leading to maintain grouping. |
| **JetBrains Mono** | Monospace for code blocks, risk scores, IDs. Distinct from Inter, still professional. |

### 3.4 Colour Rationale

| Choice | Rationale |
|--------|-----------|
| **Slate neutrals** | Warmer than pure grey (#6b7280). Reduces eye strain in long reading sessions. Feels institutional, not tech-startup. |
| **Muted primary blue** | Desaturated (#627d98 at 500). Doesn't compete with data viz colours. Communicates stability. Reserved for interactive elements (links, buttons, active states). |
| **Muted priority red** | #c4421a is brick red, not bright red (#ef4444). Says "this needs attention" not "this is dangerous/guilty." Critical for ethics. |
| **Muted priority amber** | #b7791f for Medium priority. Caution without alarm. Distinct from both High and Normal. |
| **Neutral priority slate** | #626d79 for Normal priority. Does NOT use primary blue. Blue is reserved for interactions/brand. Neutral slate avoids implying "safe/innocent" — Normal means "not elevated priority," not "cleared." |
| **Surface hierarchy** | Three levels: bg (#f7f9fc) → surface (#ffffff) → surface-alt (#f0f2f5). Creates depth without shadows. |

### 3.5 Component Specifications

#### Buttons

```css
/* Base button */
.btn {
  font-family: var(--font-family);
  font-size: var(--text-body);
  font-weight: var(--weight-medium);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  line-height: var(--leading-tight);
}

/* Primary — for main actions (Generate Report, Import, Save) */
.btn-primary {
  background: var(--color-primary-700);
  color: var(--color-neutral-0);
  border-color: var(--color-primary-700);
}
.btn-primary:hover {
  background: var(--color-primary-800);
}

/* Secondary — for alternative actions (Cancel, Back) */
.btn-secondary {
  background: var(--color-surface);
  color: var(--color-text);
  border-color: var(--color-border);
}
.btn-secondary:hover {
  background: var(--color-neutral-50);
}

/* Tertiary — for inline actions (View Details, Expand) */
.btn-tertiary {
  background: transparent;
  color: var(--color-primary-600);
  border-color: transparent;
  padding: var(--space-1) var(--space-2);
}
.btn-tertiary:hover {
  background: var(--color-primary-50);
}

/* Destructive — for irreversible actions (Delete, Deactivate) */
.btn-destructive {
  background: var(--color-error);
  color: var(--color-neutral-0);
}
.btn-destructive:hover {
  background: #a83516;
}

/* Disabled state */
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sizes */
.btn-sm { padding: var(--space-1) var(--space-3); font-size: var(--text-small); }
.btn-lg { padding: var(--space-3) var(--space-5); font-size: var(--text-h4); }
```

#### Inputs

```css
/* Text input */
.form-control {
  font-family: var(--font-family);
  font-size: var(--text-body);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
  transition: border-color var(--transition-fast);
  line-height: var(--leading-normal);
}
.form-control:focus {
  border-color: var(--color-primary-400);
  outline: none;
  box-shadow: 0 0 0 3px rgba(98, 125, 152, 0.15);
}
.form-control:disabled {
  background: var(--color-neutral-100);
  color: var(--color-text-muted);
}
.form-control::placeholder {
  color: var(--color-text-muted);
}

/* Select */
.form-select {
  /* Same as form-control + custom dropdown arrow */
}

/* Labels */
.form-label {
  font-size: var(--text-small);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-1);
}

/* Help text / validation */
.form-text {
  font-size: var(--text-caption);
  color: var(--color-text-muted);
}
.invalid-feedback {
  font-size: var(--text-caption);
  color: var(--color-error);
}
```

#### Tables

```css
/* Data table — the core of this product */
.table {
  font-size: var(--text-body);
  color: var(--color-text);
  width: 100%;
  border-collapse: collapse;
}
.table thead th {
  font-size: var(--text-caption);
  font-weight: var(--weight-semibold);
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: var(--space-2) var(--space-3);
  border-bottom: 2px solid var(--color-border);
  text-align: left;
  white-space: nowrap;
}
.table tbody td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border-light);
  vertical-align: middle;
}
.table tbody tr:hover {
  background: var(--color-neutral-50);
}
.table tbody tr.selected {
  background: var(--color-primary-50);
}

/* Compact table variant for dense data */
.table-compact thead th,
.table-compact tbody td {
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-small);
}

/* Numeric cells — right-aligned */
.table .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
  font-size: var(--text-small);
}
```

#### Badges (Priority)

```css
/* Priority badge — the most important visual element in the anomaly queue */
.badge {
  font-size: var(--text-caption);
  font-weight: var(--weight-medium);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  white-space: nowrap;
}
.badge::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* High priority — muted brick, not alarming */
.badge-high {
  background: var(--color-priority-high-bg);
  color: var(--color-priority-high);
}
.badge-high::before { background: var(--color-priority-high); }

/* Medium priority — muted amber */
.badge-medium {
  background: var(--color-priority-med-bg);
  color: var(--color-priority-med);
}
.badge-medium::before { background: var(--color-priority-med); }

/* Normal — neutral slate, no positive/negative connotation */
.badge-normal {
  background: var(--color-priority-low-bg);
  color: var(--color-priority-low);
}
.badge-normal::before { background: var(--color-priority-low); }

/* Status badges */
.badge-success { background: var(--color-success-bg); color: var(--color-success); }
.badge-warning { background: var(--color-warning-bg); color: var(--color-warning); }
.badge-error   { background: var(--color-error-bg);   color: var(--color-error); }
```

#### Cards

```css
/* Card — used sparingly. Data tables are the primary content container. */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

/* Stats card — dashboard only, max 4 per row */
.stat-card {
  padding: var(--space-5);
  border-left: 3px solid var(--color-primary-500);
}
.stat-card .stat-value {
  font-size: var(--text-h1);
  font-weight: var(--weight-semibold);
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}
.stat-card .stat-label {
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: var(--space-1);
}
.stat-card .stat-change {
  font-size: var(--text-caption);
  color: var(--color-text-muted);
  margin-top: var(--space-2);
}

/* Panel card — for containing sections within a page */
.panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border-light);
}
.panel-title {
  font-size: var(--text-h3);
  font-weight: var(--weight-semibold);
  color: var(--color-text);
}
```

#### Alerts

```css
.alert {
  font-size: var(--text-body);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
}
.alert-info {
  background: var(--color-info-bg);
  color: var(--color-info);
  border-color: var(--color-primary-100);
}
.alert-success {
  background: var(--color-success-bg);
  color: var(--color-success);
  border-color: #c6f6d5;
}
.alert-warning {
  background: var(--color-warning-bg);
  color: var(--color-warning);
  border-color: #fefcbf;
}
.alert-error {
  background: var(--color-error-bg);
  color: var(--color-error);
  border-color: #fed7d7;
}
```

#### Modals

```css
.modal-content {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}
.modal-header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border-light);
}
.modal-title {
  font-size: var(--text-h3);
  font-weight: var(--weight-semibold);
}
.modal-body {
  padding: var(--space-5);
  font-size: var(--text-body);
}
.modal-footer {
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-light);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}
```

#### Tabs

```css
.nav-tabs {
  border-bottom: 2px solid var(--color-border);
  gap: 0;
}
.nav-tabs .nav-link {
  font-size: var(--text-body);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
  padding: var(--space-2) var(--space-4);
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all var(--transition-fast);
}
.nav-tabs .nav-link:hover {
  color: var(--color-text);
  border-bottom-color: var(--color-neutral-300);
}
.nav-tabs .nav-link.active {
  color: var(--color-primary-700);
  border-bottom-color: var(--color-primary-700);
  font-weight: var(--weight-semibold);
}
```

#### Pagination

```css
.pagination {
  gap: var(--space-1);
}
.page-link {
  font-size: var(--text-small);
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  background: var(--color-surface);
}
.page-link:hover {
  background: var(--color-neutral-50);
  color: var(--color-text);
}
.page-item.active .page-link {
  background: var(--color-primary-700);
  border-color: var(--color-primary-700);
  color: var(--color-neutral-0);
}
```

#### Empty States

```css
.empty-state {
  text-align: center;
  padding: var(--space-8) var(--space-6);
  color: var(--color-text-muted);
}
.empty-state-icon {
  font-size: 3rem;
  margin-bottom: var(--space-4);
  opacity: 0.4;
}
.empty-state-title {
  font-size: var(--text-h3);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}
.empty-state-text {
  font-size: var(--text-body);
  max-width: 400px;
  margin: 0 auto;
}
```

#### Loading States

```css
/* Skeleton loader */
.skeleton {
  background: linear-gradient(90deg,
    var(--color-neutral-100) 25%,
    var(--color-neutral-200) 50%,
    var(--color-neutral-100) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease-in-out infinite;
  border-radius: var(--radius-md);
}
@keyframes skeleton-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.skeleton-text    { height: 1em; margin-bottom: var(--space-2); }
.skeleton-heading { height: 1.5em; width: 60%; margin-bottom: var(--space-3); }
.skeleton-row     { height: 2.5rem; margin-bottom: var(--space-2); }
```

#### Tooltips

```css
[data-tooltip] {
  position: relative;
}
[data-tooltip]::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  padding: var(--space-1) var(--space-2);
  background: var(--color-neutral-900);
  color: var(--color-neutral-0);
  font-size: var(--text-caption);
  border-radius: var(--radius-sm);
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--transition-fast);
}
[data-tooltip]:hover::after {
  opacity: 1;
}
```

#### Sidebar

```css
.sidebar {
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--color-neutral-900);
  color: var(--color-neutral-300);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-base);
  position: fixed;
  top: 0;
  left: 0;
  z-index: 100;
  overflow-y: auto;
}
.sidebar.collapsed {
  width: var(--sidebar-collapsed);
}
.sidebar-brand {
  padding: var(--space-4) var(--space-5);
  font-size: var(--text-h4);
  font-weight: var(--weight-semibold);
  color: var(--color-neutral-0);
  border-bottom: 1px solid var(--color-neutral-800);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.sidebar-section {
  padding: var(--space-4) var(--space-3) var(--space-1);
}
.sidebar-section-label {
  font-size: var(--text-caption);
  font-weight: var(--weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-neutral-500);
  padding: 0 var(--space-2);
  margin-bottom: var(--space-1);
}
.sidebar-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--color-neutral-400);
  text-decoration: none;
  font-size: var(--text-body);
  transition: all var(--transition-fast);
}
.sidebar-link:hover {
  background: var(--color-neutral-800);
  color: var(--color-neutral-200);
}
.sidebar-link.active {
  background: var(--color-primary-700);
  color: var(--color-neutral-0);
}
.sidebar-link i {
  font-size: 1.125rem;
  width: 1.25rem;
  text-align: center;
  flex-shrink: 0;
}
.sidebar-link .nav-badge {
  margin-left: auto;
  font-size: var(--text-caption);
  background: var(--color-priority-high);
  color: var(--color-neutral-0);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-weight: var(--weight-medium);
}

/* Sidebar footer — user info */
.sidebar-footer {
  margin-top: auto;
  padding: var(--space-4) var(--space-3);
  border-top: 1px solid var(--color-neutral-800);
}
.sidebar-user {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--color-neutral-300);
}
.sidebar-user-name {
  font-size: var(--text-small);
  font-weight: var(--weight-medium);
  color: var(--color-neutral-200);
}
.sidebar-user-role {
  font-size: var(--text-caption);
  color: var(--color-neutral-500);
}
```

#### Main Content Area

```css
.main-content {
  margin-left: var(--sidebar-width);
  min-height: 100vh;
  background: var(--color-bg);
  transition: margin-left var(--transition-base);
}
.sidebar.collapsed ~ .main-content {
  margin-left: var(--sidebar-collapsed);
}

/* Top bar */
.topbar {
  height: var(--topbar-height);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  padding: 0 var(--space-5);
  position: sticky;
  top: 0;
  z-index: 50;
}
.topbar-title {
  font-size: var(--text-h4);
  font-weight: var(--weight-semibold);
  color: var(--color-text);
}
.topbar-breadcrumb {
  font-size: var(--text-small);
  color: var(--color-text-muted);
  margin-left: var(--space-3);
}
.topbar-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

/* Page content */
.page-content {
  padding: var(--space-5);
  max-width: 1400px;
}
```

### 3.6 Bootstrap Icons

Add to `<head>` in `base.html`:

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
```

**Icon mapping for sidebar:**

| Section | Icon | Bootstrap Icons class |
|---------|------|-----------------------|
| Dashboard | Grid | `bi-grid-1x2` |
| Anomaly Queue | Exclamation triangle | `bi-exclamation-triangle` |
| Investigation Reports | File text | `bi-file-earmark-text` |
| Records | Table | `bi-table` |
| Import Dataset | Upload | `bi-cloud-upload` |
| Analysis Runs | Clock history | `bi-clock-history` |
| Model Performance | Bar chart | `bi-bar-chart-line` |
| Users | People | `bi-people` |
| Settings | Gear | `bi-gear` |
| Logout | Box arrow right | `bi-box-arrow-right` |
| Profile | Person | `bi-person` |

### 3.7 Page Layout Templates

Each page follows this structure:

```html
{% extends "base.html" %}
{% block title %}Page Title — System Name{% endblock %}

{% block content %}
<div class="page-content">
  <!-- Top bar is in base.html -->

  <!-- Page header: title + actions -->
  <div class="page-header">
    <div>
      <h1 class="page-title">Page Title</h1>
      <p class="page-subtitle">Brief description or context.</p>
    </div>
    <div class="page-actions">
      <!-- Primary action button -->
    </div>
  </div>

  <!-- Filters bar (if applicable) -->
  <div class="filter-bar">
    <!-- Search, dropdowns, date range -->
  </div>

  <!-- Main content: table, detail panel, chart, etc. -->
  <div class="panel">
    <!-- Content -->
  </div>
</div>
{% endblock %}
```

### 3.8 Priority Mapping (Configurable)

```python
# apps/detection/constants.py — the single source of truth for priority logic

PRIORITY_THRESHOLDS = {
    'high_percentile': 0.95,    # Top 5% of ranked scores → High
    'medium_percentile': 0.80,  # Next 15% (80th–95th) → Medium
    # Remaining 80% → Normal
}

PRIORITY_LABELS = {
    'high': 'High Priority',
    'medium': 'Medium',
    'normal': 'Normal',
}

# These are DISPLAY ONLY. Never interpret as probability or confidence.
```

---

## Part 4: Summary of Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Navigation | Sidebar (not top navbar) | 14 screens across 5 sections need persistent navigation |
| Registration | Removed from public nav. Admin-created only. | Security: self-registration with role selection is a vulnerability |
| Typography | Inter, 14px body | Legible at small sizes, professional, free |
| Colour base | Slate neutrals | Warmer than pure grey, easier on eyes for long sessions |
| Priority High | Muted brick red (#c4421a) | Serious, not alarming. Never implies guilt |
| Priority Medium | Muted amber (#b7791f) | Caution without alarm |
| Priority Normal | Neutral slate (#626d79) | No positive/negative connotation. Blue reserved for interactions |
| No bright green | Not used anywhere | Green would imply "safe/innocent" — we don't make that judgment |
| Anti-theatre rule | Every visual element must answer a question | No decorative KPIs, charts, badges, or animations |
| Tables vs charts | Tables for lists, charts for analysis | Each screen uses the layout that serves its primary user question |
| Spacing | 8pt grid | Consistent rhythm, eliminates guesswork |
| Border radius | Max 8px | Restrained, clean, institutional |
| Shadows | 2 levels only | Subtle, not decorative |
| Icons | Bootstrap Icons only | Single library, consistent, free, CDN |
| Card usage | Minimal, dashboard stats + panels only | Avoid "everything in a card" anti-pattern |

---

*This document defines the product audit, UX architecture, and design system. No screens have been built yet. The next step is to produce the HTML/CSS for each of the 14 screens using this system. All proposal requirements have been cross-checked and mapped to screens (Section 2.6). Registration has been secured (Section 2.1).*
