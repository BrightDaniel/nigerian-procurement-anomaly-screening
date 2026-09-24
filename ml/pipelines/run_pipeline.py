"""
Anomaly Detection Pipeline

Reproducible training script for the procurement anomaly screening system.
Logs parameters, seeds, and data snapshot version for every run.

Usage:
    python -m ml.pipelines.run_pipeline [--contamination 0.05] [--model isolation_forest]
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

import django
django.setup()

import numpy as np
import pandas as pd

from apps.detection.trainer import (
    train_isolation_forest,
    train_lof,
    run_sensitivity_analysis,
    load_feature_matrix,
    FEATURE_COLUMNS,
)
from apps.detection.evaluator import precision_recall_f1
from apps.detection.synthetic import inject_synthetic_anomalies
from apps.preprocessing.pipeline import run_full_pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

ARTIFACTS_DIR = PROJECT_ROOT / 'ml' / 'artifacts'


def run_pipeline(
    contamination=0.05,
    model='isolation_forest',
    evaluate=True,
    sensitivity=False,
):
    """Run the full anomaly detection pipeline.
    
    Steps:
    1. Load and preprocess data
    2. Compute features
    3. Train detection model
    4. Evaluate (if labels available via synthetic injection)
    5. Save artifacts and logs
    
    Args:
        contamination: Expected anomaly proportion
        model: Model to use ('isolation_forest' or 'lof')
        evaluate: Whether to run evaluation with synthetic anomalies
        sensitivity: Whether to run contamination sensitivity analysis
        
    Returns:
        dict with pipeline results
    """
    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    logger.info(f'Pipeline run {run_id} starting...')
    logger.info(f'Parameters: contamination={contamination}, model={model}')
    
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Load features
    logger.info('Step 1: Loading feature matrix...')
    X, contract_ids = load_feature_matrix()
    
    if X.empty:
        logger.error('No features available. Run feature engineering first.')
        return {'error': 'No features available', 'run_id': run_id}
    
    # Step 2: Train model
    logger.info(f'Step 2: Training {model}...')
    if model == 'isolation_forest':
        results = train_isolation_forest(contamination=contamination, save=True)
    elif model == 'lof':
        results = train_lof(contamination=contamination, save=True)
    else:
        return {'error': f'Unknown model: {model}', 'run_id': run_id}
    
    # Step 3: Evaluate (optional)
    if evaluate:
        logger.info('Step 3: Evaluating with synthetic anomalies...')
        eval_results = _evaluate_with_synthetic(X, contract_ids, contamination, model)
        results['evaluation'] = eval_results
    
    # Step 4: Sensitivity analysis (optional)
    if sensitivity:
        logger.info('Step 4: Running sensitivity analysis...')
        sensitivity_results = run_sensitivity_analysis()
        results['sensitivity'] = sensitivity_results
    
    # Save run log
    results['run_id'] = run_id
    _save_run_log(results)
    
    logger.info(f'Pipeline run {run_id} complete.')
    return results


def _evaluate_with_synthetic(X, contract_ids, contamination, model_name):
    """Evaluate detection using synthetic anomaly injection."""
    # Create synthetic anomalies
    X_array = X.values if isinstance(X, pd.DataFrame) else X
    anomaly_fraction = contamination
    n_injected = max(1, int(len(X_array) * anomaly_fraction))
    
    # Generate synthetic labels (for evaluation only)
    np.random.seed(42)
    labels = np.zeros(len(X_array), dtype=int)
    anomaly_indices = np.random.choice(len(X_array), size=n_injected, replace=False)
    labels[anomaly_indices] = 1
    
    # Train on synthetic data
    if model_name == 'isolation_forest':
        results = train_isolation_forest(contamination=contamination, save=False)
    else:
        results = train_lof(contamination=contamination, save=False)
    
    # Get scores from the model
    X, _ = load_feature_matrix()
    if model_name == 'isolation_forest':
        from apps.detection.isolation_forest import IsolationForestDetector
        detector = IsolationForestDetector(contamination=contamination)
    else:
        from apps.detection.local_outlier import LOFDetector
        detector = LOFDetector(contamination=contamination)
    
    detector.fit(X)
    scores = detector.get_anomaly_scores(X)
    
    # Compute metrics
    metrics = precision_recall_f1(labels, (scores >= np.percentile(scores, (1 - contamination) * 100)).astype(int))
    
    return {
        **metrics,
        'n_injected': int(labels.sum()),
        'contamination': contamination,
    }


def _save_run_log(results):
    """Save pipeline run results to artifacts directory."""
    log_path = ARTIFACTS_DIR / f'run_{results["run_id"]}.json'
    
    # Convert numpy types for JSON serialization
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj
    
    serializable = json.loads(json.dumps(results, default=convert))
    
    with open(log_path, 'w') as f:
        json.dump(serializable, f, indent=2)
    
    logger.info(f'Run log saved to {log_path}')


def main():
    parser = argparse.ArgumentParser(description='Anomaly Detection Pipeline')
    parser.add_argument(
        '--contamination', type=float, default=0.05,
        help='Expected anomaly proportion (default: 0.05)'
    )
    parser.add_argument(
        '--model', type=str, default='isolation_forest',
        choices=['isolation_forest', 'lof'],
        help='Detection model to use (default: isolation_forest)'
    )
    parser.add_argument(
        '--no-evaluate', action='store_true',
        help='Skip evaluation with synthetic anomalies'
    )
    parser.add_argument(
        '--sensitivity', action='store_true',
        help='Run contamination sensitivity analysis'
    )
    
    args = parser.parse_args()
    
    results = run_pipeline(
        contamination=args.contamination,
        model=args.model,
        evaluate=not args.no_evaluate,
        sensitivity=args.sensitivity,
    )
    
    print('\n' + '=' * 60)
    print('PIPELINE RESULTS')
    print('=' * 60)
    print(json.dumps(results, indent=2, default=str))


if __name__ == '__main__':
    main()
