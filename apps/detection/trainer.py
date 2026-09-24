"""
Model trainer — orchestrates fitting, prediction, and persistence.
"""
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from django.db import transaction

from apps.detection.isolation_forest import IsolationForestDetector
from apps.detection.local_outlier import LOFDetector
from apps.detection.models import AnomalyFlag
from apps.features.models import Feature
from apps.ingestion.models import Contract

logger = logging.getLogger(__name__)

# Feature columns used for detection (must match Feature model fields)
# price_deviation excluded: OCP dataset has no usable category field
FEATURE_COLUMNS = [
    'single_bidder_flag',
    'vendor_win_frequency',
    'vendor_win_concentration',
    'splitting_flag',
    'splitting_count',
    'log_contract_value',
]

# Priority thresholds (from DESIGN.md Section 3.8)
PRIORITY_THRESHOLDS = {
    'high_percentile': 0.95,    # Top 5% → High
    'medium_percentile': 0.80,  # Next 15% (80th–95th) → Medium
}


def load_feature_matrix():
    """Load features from DB into a DataFrame for model training.
    
    Returns:
        tuple: (DataFrame of features, list of contract_ids)
    """
    features = Feature.objects.all().values(
        'contract_id',
        'single_bidder_flag',
        'vendor_win_frequency',
        'vendor_win_concentration',
        'splitting_flag',
        'splitting_count',
        'log_contract_value',
    )
    
    df = pd.DataFrame(list(features))
    
    if df.empty:
        logger.warning('No features found in database.')
        return df, []
    
    # Fill NaN values with 0 for model training
    for col in FEATURE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    contract_ids = df['contract_id'].tolist()
    X = df[FEATURE_COLUMNS]
    
    logger.info(f'Loaded feature matrix: {X.shape[0]} samples, {X.shape[1]} features')
    return X, contract_ids


def train_isolation_forest(contamination=0.05, save=True):
    """Train Isolation Forest and optionally save results to DB.
    
    Args:
        contamination: Expected anomaly proportion
        save: Whether to save AnomalyFlag records to DB
        
    Returns:
        dict with training results
    """
    logger.info(f'Training Isolation Forest with contamination={contamination}')
    
    X, contract_ids = load_feature_matrix()
    if X.empty:
        return {'error': 'No features available for training'}
    
    # Train model
    detector = IsolationForestDetector(contamination=contamination)
    detector.fit(X)
    
    # Get predictions and scores
    predictions = detector.predict(X)
    scores = detector.get_anomaly_scores(X)
    
    # Assign priority labels
    high_threshold = np.percentile(scores, PRIORITY_THRESHOLDS['high_percentile'] * 100)
    medium_threshold = np.percentile(scores, PRIORITY_THRESHOLDS['medium_percentile'] * 100)
    
    results = {
        'model_name': 'Isolation Forest',
        'contamination': contamination,
        'n_samples': len(contract_ids),
        'n_features': X.shape[1],
        'n_anomalies': int((predictions == -1).sum()),
        'n_normal': int((predictions == 1).sum()),
        'score_mean': float(scores.mean()),
        'score_std': float(scores.std()),
        'score_min': float(scores.min()),
        'score_max': float(scores.max()),
        'high_threshold': float(high_threshold),
        'medium_threshold': float(medium_threshold),
        'params': detector.get_params(),
        'feature_names': FEATURE_COLUMNS,
        'timestamp': datetime.now().isoformat(),
    }
    
    logger.info(
        f'Results: {results["n_anomalies"]} anomalies, '
        f'score range [{results["score_min"]:.4f}, {results["score_max"]:.4f}]'
    )
    
    if save:
        _save_anomaly_flags(
            contract_ids=contract_ids,
            predictions=predictions,
            scores=scores,
            model_name='isolation_forest',
        )
    
    return results


def train_lof(contamination=0.05, n_neighbors=20, save=True):
    """Train LOF and optionally save results to DB.
    
    Args:
        contamination: Expected anomaly proportion
        n_neighbors: Number of neighbours to consider
        save: Whether to save AnomalyFlag records to DB
        
    Returns:
        dict with training results
    """
    logger.info(f'Training LOF with contamination={contamination}, n_neighbors={n_neighbors}')
    
    X, contract_ids = load_feature_matrix()
    if X.empty:
        return {'error': 'No features available for training'}
    
    # Train model
    detector = LOFDetector(contamination=contamination, n_neighbors=n_neighbors)
    detector.fit(X)
    
    # Get predictions and scores
    predictions = detector.predict(X)
    scores = detector.get_anomaly_scores(X)
    
    high_threshold = np.percentile(scores, PRIORITY_THRESHOLDS['high_percentile'] * 100)
    medium_threshold = np.percentile(scores, PRIORITY_THRESHOLDS['medium_percentile'] * 100)
    
    results = {
        'model_name': 'Local Outlier Factor',
        'contamination': contamination,
        'n_neighbors': n_neighbors,
        'n_samples': len(contract_ids),
        'n_features': X.shape[1],
        'n_anomalies': int((predictions == -1).sum()),
        'n_normal': int((predictions == 1).sum()),
        'score_mean': float(scores.mean()),
        'score_std': float(scores.std()),
        'score_min': float(scores.min()),
        'score_max': float(scores.max()),
        'high_threshold': float(high_threshold),
        'medium_threshold': float(medium_threshold),
        'params': detector.get_params(),
        'feature_names': FEATURE_COLUMNS,
        'timestamp': datetime.now().isoformat(),
    }
    
    logger.info(
        f'LOF results: {results["n_anomalies"]} anomalies, '
        f'score range [{results["score_min"]:.4f}, {results["score_max"]:.4f}]'
    )
    
    if save:
        _save_anomaly_flags(
            contract_ids=contract_ids,
            predictions=predictions,
            scores=scores,
            model_name='local_outlier_factor',
        )
    
    return results


@transaction.atomic
def _save_anomaly_flags(contract_ids, predictions, scores, model_name):
    """Save anomaly detection results to the database.
    
    Creates or updates AnomalyFlag records for each contract.
    Only clears flags for the specific model being run, preserving
    other models' results for the same contracts.
    """
    # Clear only flags for this specific model (unique_together on contract+model)
    deleted_count, _ = AnomalyFlag.objects.filter(
        contract_id__in=contract_ids,
        model_used=model_name,
    ).delete()
    if deleted_count > 0:
        logger.info(f'Cleared {deleted_count} existing {model_name} flags')
    
    flags = []
    for i, contract_id in enumerate(contract_ids):
        is_anomaly = bool(predictions[i] == -1)
        flags.append(AnomalyFlag(
            contract_id=contract_id,
            risk_score=float(scores[i]),
            model_used=model_name,
            is_anomaly=is_anomaly,
        ))
    
    AnomalyFlag.objects.bulk_create(flags)
    logger.info(f'Saved {len(flags)} anomaly flags for {model_name}')


def run_sensitivity_analysis(contamination_values=None):
    """Run contamination parameter sensitivity analysis.
    
    Tests contamination values: 0.01, 0.03, 0.05, 0.1
    
    Returns:
        dict mapping contamination value to results
    """
    if contamination_values is None:
        contamination_values = [0.01, 0.03, 0.05, 0.1]
    
    results = {}
    for c in contamination_values:
        logger.info(f'Sensitivity analysis: contamination={c}')
        result = train_isolation_forest(contamination=c, save=False)
        results[c] = {
            'n_anomalies': result.get('n_anomalies', 0),
            'n_normal': result.get('n_normal', 0),
            'score_mean': result.get('score_mean', 0),
            'score_std': result.get('score_std', 0),
        }
    
    return results
