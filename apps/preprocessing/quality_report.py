"""
Data quality report generator.

Documents known properties of the OCP Data Registry dataset:
- Inconsistent award dates (outliers as far off as 1949 and 2919)
- Release dates clustering almost entirely on a single day in 2021
- 93 contracting processes with incorrect OCID prefix
"""
import logging
from datetime import datetime
from collections import Counter

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Known dataset issues from OCP Data Registry flags
KNOWN_YEAR_OUTLIERS = {1949, 2919}
KNOWN_BAD_OCID_PREFIX = 'ocds-b5d162-'
EXPECTED_RELEASE_CLUSTER_DATE = '2021-01-01'


def generate_quality_report(df):
    """Generate a comprehensive data quality report.
    
    Known issues flagged:
    1. Award date outliers (1949, 2919)
    2. Release dates clustering on 2021-01-01
    3. Incorrect OCID prefixes (93 processes)
    4. Missing values per field
    5. Duplicate records
    6. Basic statistics
    
    Args:
        df: DataFrame of raw/loaded contracts
    
    Returns:
        dict with quality metrics and flagged issues
    """
    report = {
        'generated_at': datetime.now().isoformat(),
        'total_records': len(df),
        'total_columns': len(df.columns),
        'columns': list(df.columns),
        'issues': [],
    }

    # 1. Missing values
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    report['missing_values'] = {
        col: {'count': int(missing[col]), 'pct': float(missing_pct[col])}
        for col in missing.index if missing[col] > 0
    }

    # 2. Award date outliers
    if 'award_date' in df.columns:
        dates = pd.to_datetime(df['award_date'], errors='coerce')
        outlier_mask = dates.dt.year.isin(KNOWN_YEAR_OUTLIERS)
        outlier_count = outlier_mask.sum()
        if outlier_count > 0:
            report['issues'].append({
                'type': 'award_date_outliers',
                'severity': 'high',
                'count': int(outlier_count),
                'description': (
                    f'{outlier_count} records have award dates with outlier years '
                    f'(1949 or 2919). These are known data quality issues in the '
                    f'OCP Data Registry and have been flagged for exclusion from '
                    f'temporal analysis.'
                ),
                'affected_years': list(KNOWN_YEAR_OUTLIERS),
            })

        # Check for release date clustering
        if 'created_at' in df.columns:
            release_dates = pd.to_datetime(df['created_at'], errors='coerce')
            cluster_date = pd.to_datetime(EXPECTED_RELEASE_CLUSTER_DATE).date()
            cluster_mask = release_dates.dt.date == cluster_date
            cluster_count = cluster_mask.sum()
            if cluster_count > len(df) * 0.5:
                report['issues'].append({
                    'type': 'release_date_clustering',
                    'severity': 'medium',
                    'count': int(cluster_count),
                    'pct': round(cluster_count / len(df) * 100, 2),
                    'description': (
                        f'{cluster_count} release dates cluster on '
                        f'{EXPECTED_RELEASE_CLUSTER_DATE}. This indicates batch '
                        f'publication rather than actual award dates — documented '
                        f'property of this dataset.'
                    ),
                })

    # 3. OCID prefix check
    if 'nocopo_id' in df.columns:
        bad_prefix_mask = df['nocopo_id'].str.startswith(KNOWN_BAD_OCID_PREFIX, na=False)
        bad_prefix_count = bad_prefix_mask.sum()
        if bad_prefix_count > 0:
            report['issues'].append({
                'type': 'incorrect_ocid_prefix',
                'severity': 'medium',
                'count': int(bad_prefix_count),
                'description': (
                    f'{bad_prefix_count} contracting processes have the known '
                    f'incorrect OCID prefix "{KNOWN_BAD_OCID_PREFIX}". These are '
                    f'documented in the OCP Data Registry quality flags.'
                ),
            })

    # 4. Duplicates
    if 'nocopo_id' in df.columns:
        dup_count = df['nocopo_id'].duplicated().sum()
        if dup_count > 0:
            report['issues'].append({
                'type': 'duplicates',
                'severity': 'medium',
                'count': int(dup_count),
                'description': f'{dup_count} duplicate nocopo_id values found.',
            })

    # 5. Numeric statistics
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    report['numeric_stats'] = {}
    for col in numeric_cols:
        report['numeric_stats'][col] = {
            'mean': float(df[col].mean()) if not df[col].isna().all() else None,
            'std': float(df[col].std()) if not df[col].isna().all() else None,
            'min': float(df[col].min()) if not df[col].isna().all() else None,
            'max': float(df[col].max()) if not df[col].isna().all() else None,
        }

    # 6. Categorical distributions
    cat_cols = ['method', 'category', 'currency']
    report['categorical_distributions'] = {}
    for col in cat_cols:
        if col in df.columns:
            report['categorical_distributions'][col] = df[col].value_counts().to_dict()

    report['issues_summary'] = {
        'total_issues': len(report['issues']),
        'high_severity': sum(1 for i in report['issues'] if i['severity'] == 'high'),
        'medium_severity': sum(1 for i in report['issues'] if i['severity'] == 'medium'),
    }

    logger.info(
        f'Quality report: {report["total_records"]} records, '
        f'{len(report["issues"])} issues flagged'
    )
    return report


def format_quality_report(report):
    """Format a quality report dict as readable text."""
    lines = [
        '=' * 60,
        'DATA QUALITY REPORT',
        f'Generated: {report["generated_at"]}',
        f'Total Records: {report["total_records"]}',
        f'Total Columns: {report["total_columns"]}',
        '=' * 60,
        '',
        'ISSUES FLAGGED:',
    ]

    for issue in report.get('issues', []):
        lines.append(f'  [{issue["severity"].upper()}] {issue["type"]}')
        lines.append(f'    {issue["description"]}')
        lines.append('')

    if not report.get('issues'):
        lines.append('  No issues detected.')

    lines.append('')
    lines.append('MISSING VALUES:')
    for col, info in report.get('missing_values', {}).items():
        lines.append(f'  {col}: {info["count"]} ({info["pct"]}%)')

    if not report.get('missing_values'):
        lines.append('  No missing values.')

    return '\n'.join(lines)
