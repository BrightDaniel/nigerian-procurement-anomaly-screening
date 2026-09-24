# Limitations and Responsible Use

**Project:** Design and Implementation of an Explainable Anomaly-Screening System for Nigerian Public Procurement Records

This document defines what the system **can** support, what it **cannot** establish, and the obligations of anyone operating or reading its outputs. It consolidates technical, data, methodological, and ethical limitations verified against the implementation.

---

## 1. Non-negotiable interpretation rules

1. A flag, score, priority badge, rank, chart, or explanation is **never** proof of fraud, corruption, crime, or misconduct.
2. Preferred language: “flagged record”, “anomaly score”, “feature contribution”, “may warrant further investigation”.
3. Banned language: “fraud detected”, “guilty”, “corrupt”, “illegal”, “offender”, “criminal”, “stolen”, etc.
4. **Anomaly screening ≠ fraud detection.** The system has no fraud labels and none are used.
5. Absence of a flag does **not** certify a record as clean, compliant, or optimal.
6. Outputs are **decision-support for qualified humans**, not automated decisions about people or organisations.

Violating these rules in a report, presentation, or deployment undermines both the project’s ethics stance and its academic claims.

---

## 2. Technical limitations (implemented system)

| # | Limitation | Detail |
|---|---|---|
| T1 | **Unsupervised by design** | No ground-truth outcomes; quality of flags is bounded by feature design and contamination choice. |
| T2 | **Low synthetic P/R/F1** | IF F1 ≈ 0.166, LOF F1 ≈ 0.084 at 5% injection (see EVALUATION.md). Not a production fraud classifier. |
| T3 | **Two incompatible score scales** | IF min-max inverted scores vs LOF rank-based flagged-only scores; do not compare across models numerically. |
| T4 | **Dual priority schemes** | UI uses fixed 0.80/0.60; trainer logs percentile thresholds — inconsistency documented, not reconciled. |
| T5 | **Contamination-driven recall** | ~5% flag rate is a parameter default, not an estimated crime prevalence. |
| T6 | **Low model agreement** | Persisted IF∩LOF Jaccard ≈ 0.0897 (137 both / 1,527 union); algorithms see different geometry. |
| T7 | **SHAP explainer always Isolation Forest** | LOF-attached explanations use TreeExplainer on an IF estimator fitted to the same matrix (documented in ML_METHODOLOGY.md §7.2). |
| T8 | **`price_deviation` unused** | Schema column exists; not computed, not in `FEATURE_COLUMNS`; no usable price basis in data. Residual UI helper rows mentioning it are display artefacts. |
| T9 | **Transductive vendor/entity features** | Win frequency/concentration computed over full corpus; not strictly point-in-time — leakage-style caution for temporal analysis. |
| T10 | **No scaling / calibration** | Scores are not probabilistic; 0.9 does not mean “90% chance of wrongdoing”. |
| T11 | **Batch-oriented** | No streaming/real-time guarantee; detection is a management-command workload. |
| T12 | **Dependency gap** | `shap` is imported by the application but **missing from `requirements.txt`** (reported); fresh installs can fail until pinned. |
| T13 | **Settings module mismatch in scripts** | Standalone eval scripts reference `config.settings` while `manage.py` uses `config.settings.dev` and `config/settings/__init__.py` is empty — environment-dependent runnability. |
| T14 | **LIME not production-wired** | Optional module only; not used by commands or views. |
| T15 | **No API / no multi-tenant isolation** | Single shared result set for all authenticated users. |
| T16 | **Security posture for dev defaults** | Dev settings exist for local use; production requires `config.settings.prod`, real secret key, `ALLOWED_HOSTS` — not configured here. |
| T17 | **No automated tests for every view edge** | Sprint suite covers 30 core behaviours; broader matrix not exhaustive. |

---

## 3. Data limitations

| # | Limitation | Detail |
|---|---|---|
| D1 | **Published data only** | OCDS/OCP export; missing confidential annexes, bid documents, payment trails. |
| D2 | **No losing-bid prices** | Cannot measure bid spread, collusion patterns in pricing, or abnormally low/high tenders reliably. |
| D3 | **No outcome labels** | No investigations, sanctions, or court results linked → real accuracy unknowable. |
| D4 | **Category/price references absent** | Blocks defensible unit-price deviation features. |
| D5 | **Identity resolution by name** | Entity/vendor matching quality depends on export hygiene; CAC numbers often missing. |
| D6 | **Snapshot, not panel** | Treated as one corpus; limited temporal generalisation claims. |
| D7 | **780 rejected staging rows** | ~4.5% failed validation — coverage gap if rejections cluster in meaningful ways. |
| D8 | **Nigerian context specificity** | Splitting windows, single-bidder norms, method categories reflect this corpus; not automatically valid elsewhere. |

---

## 4. Methodological limitations

- Synthetic injection is a **surrogate** for truth; injected anomalies may be easier or harder than real ones.
- Sensitivity tables show **operational** behaviour (counts), not optimal thresholds.
- No time-based cross-validation, no external validation set, no adversarial testing of explanations.
- Feature set is intentionally small (6) for transparency — richer behaviour may be missed.
- Business rules (`single_bidder_flag`, `splitting_*`) encode **suspicion patterns from literature**, not Nigerian legal tests for illegality (single-source awards can be lawful).

---

## 5. Ethical and legal limitations

1. **Stigmatisation risk** — vendors/MDAs with high flag counts may be wrongly perceived as corrupt; charts like “Top Flagged MDAs” measure **flag concentration**, often correlated with procurement volume.
2. **Defamation risk** — investigation free-text must stay factual and provisional.
3. **Due process** — the system is not a hearing; findings require human institutional channels.
4. **Privacy** — data is largely organisational, but reviewer accounts and report text are personal/workplace records; handle access accordingly.
5. **Automation bias** — UI priority badges can bias reviewers; mandatory disclaimer text must remain visible.
6. **Adversarial adaptation** — determined actors who know the features can reshape behaviour (split amounts differently, vary bidders) without any true change in risk.
7. **Secondary use ban** — do not repurpose scores for blacklisting, media shaming, or political messaging.

---

## 6. Intended users

| User | May | Must not |
|---|---|---|
| Trained auditor / reviewer | Prioritise review, document findings | Declare guilt from a score alone |
| Administrator | Manage data, accounts, settings | Alter scores/explanations to fit a narrative |
| Researcher / student | Reproduce evaluations, extend methods | Claim fraud-detection performance unsupported by EVALUATION.md |
| Developer | Improve features, tests, docs | Remove disclaimers or weaken role checks silently |
| Public / media | Read methodology docs | Present queue screenshots as evidence of crimes |

---

## 7. Safe operational practices

1. Always display the built-in disclaimers (queue, detail, report form) — do not theme them away.
2. Review **High** band first as a workload strategy only.
3. Corroborate with primary documents (tenders, approvals) before any escalation.
4. Prefer “flagged by Isolation Forest with score X because features Y/Z” over “high-risk vendor”.
5. When publishing aggregates, report **denominators** (e.g., 832/16,637 flagged, not “thousands of red flags”).
6. Keep IF and LOF results labelled by model; never merge scores.
7. Record analyst identity on reports (already enforced via `reviewer` FK).
8. Pin and test dependencies (`shap` missing from requirements is a known gap to fix in engineering hygiene work).

---

## 8. What would be required for stronger claims

To move beyond “screening support” toward stronger evidentiary or statistical claims, the project would need (future work, not implemented):

- Labelled outcomes from cooperating institutions (investigations, with consent and governance).
- Temporal train/test splits and external datasets.
- Explanation fidelity benchmarks (SHAP vs perturbation, human-judged plausibility).
- Calibration studies if probabilities are ever displayed (they should not be, today).
- Legal review of feature meanings against Nigerian procurement law.
- Fairness analysis across entity types/states.
- Hardened production deployment (secret management, CI, monitoring).

---

## 9. Honest project status (for reports/viva)

**Strengths to state:**

- End-to-end working system: import → features → dual-model screening → SHAP explanations → investigation reports.
- Role-based access, validation, idempotent persistence, audit scripts, 30-test suite green.
- Neutral NL generation with zero banned-language violations in the stored corpus.
- Transparent evaluation numbers including **weak** precision/recall — reported, not hidden.

**Weaknesses to state:**

- Unsupervised evaluation via synthetic injection only; low absolute F1.
- Model disagreement high (Jaccard ≈ 0.09).
- Known implementation discrepancies (requirements gap, script settings mismatch, dual threshold schemes, residual price-deviation display rows, LOF SHAP explainer detail).
- No production deployment hardening beyond provided settings modules.

Owning these points is part of responsible scholarship; concealing them is not.

---

## 10. Disclaimer (canonical)

> This system performs statistical anomaly screening on published procurement records. An anomaly flag indicates that a record received an unusual score under a configured model relative to other records in the dataset. It does **not** detect fraud, does **not** determine that any law was broken, and does **not** establish that any person or organisation acted improperly. Any further action requires qualified human investigation through appropriate institutional and legal channels.

---

## Related documents

- [USER_GUIDE.md](USER_GUIDE.md) — in-product disclaimer placements
- [ML_METHODOLOGY.md](ML_METHODOLOGY.md) — method boundaries
- [EVALUATION.md](EVALUATION.md) — what metrics do and do not show
- [README.md](../README.md) — project entry point
