# Explainable Anomaly-Screening System for Nigerian Public Procurement Records

A web-based system that screens Nigerian public procurement records for anomalies
using unsupervised machine learning (Isolation Forest and Local Outlier Factor)
with SHAP-based explainability. Built with Django, PostgreSQL, and scikit-learn.

> **Important:** This system performs *anomaly screening*, not fraud detection.
> It does not determine that fraud has occurred. A flag means a record *may
> warrant further investigation* by a qualified auditor. All model outputs are
> decision-support information only.

## Features

- **Anomaly Detection**: Isolation Forest and LOF models flag unusual procurement patterns
- **SHAP Explanations**: Every flagged record includes a plain-English explanation of why it was flagged
- **Investigation Workflow**: Auditors review flagged records and write investigation reports
- **Two-role System**: Administrators manage data and users; Auditors investigate anomalies
- **Contamination Sensitivity Analysis**: Evaluate model behaviour across contamination parameters

## Quick Start

### Prerequisites

- Python 3.14+
- PostgreSQL
- pip

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd week-9-implementation

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env with your database credentials and secret key

# Create database
createdb procurement_anomaly

# Run migrations
python manage.py migrate

# Create administrator account
python manage.py createsuperuser

# Import data (download from OCP first — see data/raw/README.md)
python manage.py import_data data/raw/full.csv

# Generate features
python manage.py generate_features

# Run anomaly detection
python manage.py run_detection --model isolation_forest
python manage.py run_detection --model lof

# Start the server
python manage.py runserver
```

### Usage

1. Log in as Administrator
2. Import procurement data via the Import Dataset page
3. The system automatically runs preprocessing, feature engineering, and detection
4. Navigate to the Anomaly Queue to review flagged records
5. Each record shows a plain-English explanation of why it was flagged
6. Write investigation reports for records under review

## Project Structure

```
week-9-implementation/
├── config/                 # Django project settings
├── apps/
│   ├── accounts/           # User management (Admin/Auditor roles)
│   ├── ingestion/          # Data import (CSV upload, OCP download)
│   ├── preprocessing/      # Data cleaning and validation
│   ├── features/           # Feature engineering (6 active features)
│   ├── detection/          # ML models (IF + LOF)
│   ├── explainability/     # SHAP explanations
│   ├── dashboard/          # Main UI views
│   └── reporting/          # Investigation reports
├── templates/              # HTML templates
├── static/                 # CSS, JavaScript
├── data/                   # Dataset files (not version-controlled)
├── ml/                     # ML utilities
├── docs/                   # Documentation
└── manage.py
```

## Active Model Features

| Feature | Type | Description |
|---------|------|-------------|
| `log_contract_value` | Continuous | Log-transformed contract amount |
| `single_bidder_flag` | Binary | Whether only one bidder participated |
| `vendor_win_frequency` | Continuous | How often the vendor has won contracts |
| `vendor_win_concentration` | Continuous | Vendor dominance within a procuring entity |
| `splitting_flag` | Binary | Whether contract splitting pattern detected |
| `splitting_count` | Discrete | Number of similar contracts from same entity |

## Model Parameters

- **Isolation Forest**: contamination=0.05, n_estimators=100
- **LOF**: contamination=0.05, n_neighbors=20

## Running Tests

```bash
python test_sprint1.py
```

Expected result: 30/30 tests pass.

## Evaluation Scripts

Reproducibility scripts used for the project's experimental evaluation:

```bash
# Synthetic anomaly evaluation (Precision / Recall / F1 + contamination sensitivity)
python run_final_evaluation.py

# Explainability evaluation (SHAP coverage, feature integrity, banned-language check)
python run_explainability_eval.py

# Authorization audit (read-only)
python scripts/authz_audit.py
```

Evaluation uses synthetically injected anomalies because the dataset has no
real-world fraud ground truth. Results are therefore indicative of model
behaviour, not proof of detection accuracy on actual fraud cases.

## Limitations

- No labelled fraud ground truth: evaluation relies on synthetic anomalies.
- The source dataset lacks a usable contract-category field, so the
  `price_deviation` feature is excluded.
- Results are dataset- and period-specific (OCP Publication 64, Nigeria BPP).
- Flags require human review; the system does not make determinations.

## Ethical Interpretation

Flagged records must be described as *anomalies* or *records warranting
review*. They must never be presented as confirmed fraud, corruption, or
criminal activity. Findings are advisory inputs to a human investigation
process.

## Data Source

Procurement data from the [Open Contracting Partnership Data Registry](https://data.open-contracting.org),
Publication 64 (Nigeria Bureau of Public Procurement).

## License

Academic project — SEN 497 Final Year Project, Covenant University, 2026.
