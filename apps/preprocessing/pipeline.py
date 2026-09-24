"""
Data cleaning and preprocessing pipeline.

Handles schema inspection, missing-value handling, de-duplication,
type casting, categorical encoding, and data-quality reporting.
"""
import logging
from pathlib import Path

import pandas as pd
import numpy as np
from django.conf import settings

from apps.ingestion.models import Contract, ProcuringEntity, Vendor
from apps.preprocessing.cleaners import (
    clean_award_dates, handle_missing_values, deduplicate_records,
    cast_types, encode_categoricals,
)
from apps.preprocessing.quality_report import generate_quality_report

logger = logging.getLogger(__name__)


def load_contracts_to_dataframe():
    """Load all contracts into a pandas DataFrame with joined fields."""
    contracts = Contract.objects.select_related('entity', 'vendor').all().values(
        'contract_id', 'title', 'amount', 'currency', 'award_date',
        'bidding_window_days', 'num_bidders', 'method', 'category',
        'nocopo_id', 'entity__name', 'entity__type', 'entity__state',
        'vendor__name', 'vendor__cac_number', 'vendor__state',
    )
    df = pd.DataFrame(list(contracts))
    if not df.empty:
        df.columns = [c.replace('__', '_') for c in df.columns]
    return df


def save_processed_data(df):
    """Save cleaned DataFrame to data/processed/ as CSV for reproducibility.
    
    Args:
        df: Cleaned DataFrame to save
    """
    processed_dir = Path(settings.BASE_DIR) / 'data' / 'processed'
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = processed_dir / 'cleaned_contracts.csv'
    df.to_csv(output_path, index=False)
    logger.info(f'Saved {len(df)} cleaned records to {output_path}')


def run_full_pipeline():
    """Execute the complete preprocessing pipeline.
    
    Returns:
        tuple: (cleaned_df, quality_report_dict)
    """
    logger.info('Loading contracts...')
    df = load_contracts_to_dataframe()

    if df.empty:
        logger.warning('No contracts found in database.')
        return df, {'status': 'empty', 'total_records': 0}

    logger.info(f'Loaded {len(df)} contracts.')

    # Step 1: Schema inspection
    quality = generate_quality_report(df)
    logger.info(f'Quality report generated: {quality["total_records"]} records')

    # Step 2: Clean data
    df = clean_award_dates(df)
    df = handle_missing_values(df)
    df = deduplicate_records(df)
    df = cast_types(df)
    df = encode_categoricals(df)

    # Step 3: Update quality report
    quality['after_cleaning'] = {
        'total_records': len(df),
        'columns': list(df.columns),
    }

    # Step 4: Save processed data
    save_processed_data(df)

    return df, quality
