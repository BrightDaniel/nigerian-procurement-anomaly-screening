"""
Feature engineering — computes all risk features from the registry.
"""
import logging
from datetime import timedelta

import numpy as np
import pandas as pd
from django.db import transaction
from django.utils import timezone

from apps.features.models import Feature
from apps.features.registry import FEATURE_REGISTRY
from apps.ingestion.models import Contract

logger = logging.getLogger(__name__)


def compute_all_features(df=None):
    """Compute all features for all contracts.
    
    Args:
        df: Optional pre-loaded DataFrame. If None, loads from DB.
    
    Returns:
        int: Number of features created/updated
    """
    if df is None:
        df = _load_contracts_df()

    if df.empty:
        logger.warning('No contracts to compute features for.')
        return 0

    logger.info(f'Computing features for {len(df)} contracts...')

    # Compute each feature
    df = _compute_log_contract_value(df)
    df = _compute_single_bidder_flag(df)
    df = _compute_vendor_win_frequency(df)
    df = _compute_vendor_win_concentration(df)
    # price_deviation excluded: OCP dataset has no usable category field
    df = _compute_splitting_features(df)

    # Save to database
    count = _save_features(df)
    logger.info(f'Saved {count} feature records.')
    return count


def _load_contracts_df():
    """Load contracts into a DataFrame."""
    contracts = Contract.objects.all().values(
        'contract_id', 'amount', 'num_bidders', 'method', 'category',
        'vendor_id', 'entity_id', 'award_date', 'nocopo_id',
    )
    df = pd.DataFrame(list(contracts))
    if not df.empty:
        # Ensure numeric columns are float (Django returns Decimal)
        for col in ['amount', 'num_bidders', 'vendor_id', 'entity_id']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


def _compute_log_contract_value(df):
    """Transaction feature: log(1 + amount)."""
    df['log_contract_value'] = np.log1p(df['amount'].clip(lower=0))
    return df


def _compute_single_bidder_flag(df):
    """Competition feature: 1 if only one bidder."""
    df['single_bidder_flag'] = (df['num_bidders'] == 1).astype(int)
    return df


def _compute_vendor_win_frequency(df):
    """Supplier feature: vendor_wins / total_contracts for each vendor.
    
    NULL vendors (vendor_id=0) receive 0 — missing vendor information
    must not be interpreted as evidence of a highly frequent vendor.
    """
    valid = df[df['vendor_id'] != 0]
    vendor_wins = valid.groupby('vendor_id').size()
    total_contracts = len(df)

    df['vendor_win_frequency'] = df['vendor_id'].map(
        lambda v: vendor_wins.get(v, 0) / total_contracts if v != 0 and total_contracts > 0 else 0
    )
    return df


def _compute_vendor_win_concentration(df):
    """Supplier feature: HHI of vendor wins per MDA.
    
    NULL vendors (vendor_id=0) receive 0 — missing vendor information
    must not be interpreted as evidence of vendor concentration.
    """
    valid = df[df['vendor_id'] != 0]
    entity_vendor_counts = valid.groupby(['entity_id', 'vendor_id']).size().reset_index(name='wins')
    entity_totals = entity_vendor_counts.groupby('entity_id')['wins'].sum()

    hhi_map = {}
    for entity_id, group in entity_vendor_counts.groupby('entity_id'):
        total = entity_totals[entity_id]
        shares = group['wins'] / total
        hhi = (shares ** 2).sum()
        hhi_map[entity_id] = hhi

    df['vendor_win_concentration'] = df.apply(
        lambda row: hhi_map.get(row['entity_id'], 0) if row['vendor_id'] != 0 else 0,
        axis=1,
    )
    return df


def _compute_price_deviation(df):
    """Price feature: (amount - mean_category) / std_category."""
    cat_stats = df.groupby('category')['amount'].agg(['mean', 'std']).to_dict('index')

    def calc_deviation(row):
        cat = row['category']
        if cat in cat_stats and cat_stats[cat]['std'] > 0:
            return (row['amount'] - cat_stats[cat]['mean']) / cat_stats[cat]['std']
        return 0.0

    df['price_deviation'] = df.apply(calc_deviation, axis=1)
    return df


def _compute_splitting_features(df):
    """Splitting features: flag and count similar contracts same vendor+MDA in 12 months."""
    df = df.sort_values(['vendor_id', 'entity_id', 'award_date'])

    splitting_flags = []
    splitting_counts = []

    for _, group in df.groupby(['vendor_id', 'entity_id']):
        if len(group) <= 1:
            splitting_flags.extend([0] * len(group))
            splitting_counts.extend([0] * len(group))
            continue

        dates = pd.to_datetime(group['award_date'], errors='coerce')
        flags = [0] * len(group)
        counts = [0] * len(group)

        for i, (idx, row) in enumerate(group.iterrows()):
            current_date = dates.loc[idx]
            if pd.isna(current_date):
                continue

            window_start = current_date - timedelta(days=365)
            window_mask = (dates >= window_start) & (dates <= current_date)
            window_count = window_mask.sum() - 1  # exclude self

            counts[i] = window_count
            if window_count > 3:
                flags[i] = 1

        splitting_flags.extend(flags)
        splitting_counts.extend(counts)

    df['splitting_flag'] = splitting_flags
    df['splitting_count'] = splitting_counts
    return df


@transaction.atomic
def _save_features(df):
    """Save computed features to the database."""
    features = []
    for _, row in df.iterrows():
        features.append(Feature(
            contract_id=row['contract_id'],
            # price_deviation excluded: OCP dataset has no usable category field
            single_bidder_flag=bool(row.get('single_bidder_flag', 0)),
            vendor_win_frequency=row.get('vendor_win_frequency'),
            vendor_win_concentration=row.get('vendor_win_concentration'),
            splitting_flag=bool(row.get('splitting_flag', 0)),
            splitting_count=int(row.get('splitting_count', 0)),
            log_contract_value=row.get('log_contract_value'),
        ))

    Feature.objects.bulk_create(features, ignore_conflicts=True)
    return len(features)
