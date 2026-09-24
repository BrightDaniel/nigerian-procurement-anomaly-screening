"""
Data transformation functions for feature preparation.
"""
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def log_transform_amount(df):
    """Apply log(1 + amount) transformation to reduce skewness."""
    df = df.copy()
    if 'amount' in df.columns:
        df['log_contract_value'] = np.log1p(df['amount'].clip(lower=0))
        logger.info('Applied log transformation to contract amounts')
    return df


def normalize_numerics(df, columns=None):
    """Min-max normalize numeric columns to [0, 1] range."""
    df = df.copy()
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    for col in columns:
        if col in df.columns:
            min_val = df[col].min()
            max_val = df[col].max()
            if max_val > min_val:
                df[f'{col}_norm'] = (df[col] - min_val) / (max_val - min_val)
            else:
                df[f'{col}_norm'] = 0.0

    return df


def compute_rolling_features(df, date_col='award_date', value_col='amount', windows=[30, 90, 365]):
    """Compute rolling window statistics for temporal patterns."""
    df = df.copy()
    if date_col not in df.columns or value_col not in df.columns:
        return df

    df = df.sort_values(date_col)
    for window in windows:
        df[f'{value_col}_rolling_{window}d'] = (
            df[value_col]
            .rolling(window=f'{window}D', on=df[date_col], min_periods=1)
            .mean()
        )

    return df
