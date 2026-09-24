"""
Synthetic anomaly injection for evaluation.

Injects known anomalies into the feature space to create
ground-truth evaluation sets for P/R/F1 metrics.

Injection targets the six active model features directly:
- log_contract_value: unusually large contract values
- single_bidder_flag: forced single-bidder procurement
- splitting_flag / splitting_count: unusual splitting patterns
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def inject_synthetic_anomalies(df, anomaly_fraction=0.05, strategy='mixed', random_state=42):
    """Inject synthetic anomalies directly into the feature space.

    Strategies:
    - 'value_extreme': Increase log_contract_value by 2.0–4.0
      (equivalent to 10x–50x increase in raw contract amount)
    - 'single_bidder': Set single_bidder_flag to 1
    - 'feature_perturbation': Combine single_bidder, splitting, and value changes

    Args:
        df: DataFrame of feature records (must contain FEATURE_COLUMNS)
        anomaly_fraction: Fraction of records to inject as anomalies
        strategy: Injection strategy
        random_state: Random seed

    Returns:
        tuple: (df_with_anomalies, anomaly_labels)
    """
    np.random.seed(random_state)

    df = df.copy()
    n_records = len(df)
    n_anomalies = max(1, int(n_records * anomaly_fraction))

    anomaly_indices = np.random.choice(n_records, size=n_anomalies, replace=False)
    labels = np.zeros(n_records, dtype=int)
    labels[anomaly_indices] = 1

    logger.info(f'Injecting {n_anomalies} synthetic anomalies ({anomaly_fraction*100:.1f}%)')

    if strategy == 'mixed':
        n_value = n_anomalies // 3
        n_bidder = n_anomalies // 3
        n_perturb = n_anomalies - n_value - n_bidder

        value_indices = anomaly_indices[:n_value]
        bidder_indices = anomaly_indices[n_value:n_value + n_bidder]
        perturb_indices = anomaly_indices[n_value + n_bidder:]

        df = _inject_value_extremes(df, value_indices)
        df = _inject_single_bidder(df, bidder_indices)
        df = _inject_feature_perturbation(df, perturb_indices)

    elif strategy == 'value_extreme':
        df = _inject_value_extremes(df, anomaly_indices)

    elif strategy == 'single_bidder':
        df = _inject_single_bidder(df, anomaly_indices)

    elif strategy == 'feature_perturbation':
        df = _inject_feature_perturbation(df, anomaly_indices)

    logger.info(f'Injected {labels.sum()} anomalies with strategy={strategy}')
    return df, labels


def _inject_value_extremes(df, indices):
    """Increase log_contract_value by 2.0–4.0 (≈10x–50x raw amount)."""
    if 'log_contract_value' in df.columns:
        for idx in indices:
            boost = np.random.uniform(2.0, 4.0)
            df.at[idx, 'log_contract_value'] = df.at[idx, 'log_contract_value'] + boost
    return df


def _inject_single_bidder(df, indices):
    """Set single_bidder_flag to 1 (single bidder)."""
    if 'single_bidder_flag' in df.columns:
        df.loc[indices, 'single_bidder_flag'] = 1
    return df


def _inject_feature_perturbation(df, indices):
    """Perturb multiple features simultaneously for realistic anomalies."""
    for idx in indices:
        if 'single_bidder_flag' in df.columns:
            df.at[idx, 'single_bidder_flag'] = 1
        if 'log_contract_value' in df.columns:
            boost = np.random.uniform(1.5, 3.5)
            df.at[idx, 'log_contract_value'] = df.at[idx, 'log_contract_value'] + boost
        if 'splitting_flag' in df.columns:
            df.at[idx, 'splitting_flag'] = 1
        if 'splitting_count' in df.columns:
            df.at[idx, 'splitting_count'] = df.at[idx, 'splitting_count'] + np.random.randint(4, 10)
    return df


def create_evaluation_dataset(contracts_df, anomaly_fraction=0.05, random_state=42):
    """Create a complete evaluation dataset with synthetic anomalies.

    Args:
        contracts_df: DataFrame of cleaned contracts
        anomaly_fraction: Fraction to inject
        random_state: Random seed

    Returns:
        dict with evaluation data
    """
    df_anomalous, labels = inject_synthetic_anomalies(
        contracts_df,
        anomaly_fraction=anomaly_fraction,
        strategy='mixed',
        random_state=random_state,
    )

    return {
        'data': df_anomalous,
        'labels': labels,
        'n_total': len(labels),
        'n_anomalies': int(labels.sum()),
        'anomaly_fraction': anomaly_fraction,
        'strategy': 'mixed',
        'random_state': random_state,
    }
