"""
Data cleaning functions for preprocessing pipeline.
"""
import logging
from datetime import datetime

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Known dataset quality issues from OCP Data Registry
KNOWN_YEAR_OUTLIERS = {1949, 2919}


def clean_award_dates(df):
    """Clean award_date column by flagging/handling known outliers.
    
    Known issues in the OCP dataset:
    - Outlier years (1949, 2919) are flagged as NaN
    - Dates are cast to proper datetime
    """
    if 'award_date' not in df.columns:
        return df

    df = df.copy()
    original_count = len(df)

    # Convert to datetime
    df['award_date'] = pd.to_datetime(df['award_date'], errors='coerce')

    # Flag outlier years
    outlier_mask = df['award_date'].dt.year.isin(KNOWN_YEAR_OUTLIERS)
    outlier_count = outlier_mask.sum()
    if outlier_count > 0:
        logger.warning(
            f'Flagging {outlier_count} records with outlier award date years '
            f'(1949/2919) as NaT'
        )
        df.loc[outlier_mask, 'award_date'] = pd.NaT

    # Extract useful date features
    df['award_year'] = df['award_date'].dt.year
    df['award_month'] = df['award_date'].dt.month
    df['award_day_of_week'] = df['award_date'].dt.dayofweek

    logger.info(f'Award date cleaning: {original_count} -> {len(df)} records')
    return df


def handle_missing_values(df):
    """Handle missing values based on field-specific rules."""
    df = df.copy()

    # Numeric fields: fill with median
    numeric_cols = ['amount', 'bidding_window_days', 'num_bidders']
    for col in numeric_cols:
        if col in df.columns:
            missing = df[col].isna().sum()
            if missing > 0:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                logger.info(f'{col}: filled {missing} missing with median {median_val}')

    # Categorical fields: fill with mode or 'Unknown'
    categorical_cols = ['method', 'category', 'currency']
    for col in categorical_cols:
        if col in df.columns:
            missing = df[col].isna().sum()
            if missing > 0:
                mode_val = df[col].mode()
                fill_val = mode_val.iloc[0] if not mode_val.empty else 'Unknown'
                df[col] = df[col].fillna(fill_val)
                logger.info(f'{col}: filled {missing} missing with {fill_val}')

    # Text fields: fill with placeholder
    text_cols = ['title', 'entity_name', 'vendor_name']
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna('Unknown')

    # Date fields: leave as NaT (already handled)
    return df


def deduplicate_records(df):
    """Remove duplicate records based on nocopo_id."""
    df = df.copy()
    original_count = len(df)

    if 'nocopo_id' in df.columns:
        df = df.drop_duplicates(subset=['nocopo_id'], keep='first')

    dropped = original_count - len(df)
    if dropped > 0:
        logger.info(f'Deduplication: removed {dropped} duplicate records')

    return df


def cast_types(df):
    """Ensure correct data types for each column."""
    df = df.copy()

    type_map = {
        'amount': 'float64',
        'num_bidders': 'Int64',
        'bidding_window_days': 'Int64',
        'contract_id': 'Int64',
    }

    for col, dtype in type_map.items():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(dtype)

    return df


def encode_categoricals(df):
    """Label-encode categorical columns for ML readiness."""
    df = df.copy()

    encode_cols = ['method', 'category', 'currency']
    for col in encode_cols:
        if col in df.columns:
            df[f'{col}_encoded'] = pd.Categorical(df[col]).codes

    return df
