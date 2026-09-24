"""
Isolation Forest anomaly detector.
"""
import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from apps.detection.base import BaseDetector

logger = logging.getLogger(__name__)


class IsolationForestDetector(BaseDetector):
    """Isolation Forest for anomaly detection.
    
    Isolates anomalies by random recursive partitioning.
    Anomalies are isolated in fewer partitions than normal points.
    
    Parameters:
        contamination: Expected proportion of anomalies (default 0.05)
        n_estimators: Number of isolation trees (default 100)
        max_samples: Samples to draw for each tree ('auto' or int)
        max_features: Features to draw for each tree (1.0 = all)
        bootstrap: Whether to use bootstrap sampling
        random_state: Random seed for reproducibility
    """
    
    def __init__(
        self,
        contamination=0.05,
        n_estimators=100,
        max_samples='auto',
        max_features=1.0,
        bootstrap=False,
        random_state=42,
    ):
        super().__init__(contamination=contamination, random_state=random_state)
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.max_features = max_features
        self.bootstrap = bootstrap
    
    def fit(self, X):
        """Fit Isolation Forest on training data.
        
        Args:
            X: DataFrame or array of features. If DataFrame, feature names are stored.
        """
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
            X_array = X.values
        else:
            X_array = np.array(X)
            self.feature_names = [f'feature_{i}' for i in range(X_array.shape[1])]
        
        logger.info(
            f'Fitting Isolation Forest: {self.n_estimators} estimators, '
            f'contamination={self.contamination}, '
            f'{X_array.shape[0]} samples, {X_array.shape[1]} features'
        )
        
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            contamination=self.contamination,
            max_features=self.max_features,
            bootstrap=self.bootstrap,
            random_state=self.random_state,
            n_jobs=-1,
        )
        
        self.model.fit(X_array)
        self.is_fitted = True
        
        logger.info('Isolation Forest fitted successfully.')
        return self
    
    def predict(self, X):
        """Predict anomalies: -1 = anomaly, 1 = normal."""
        if not self.is_fitted:
            raise RuntimeError('Model must be fitted before prediction.')
        
        if isinstance(X, pd.DataFrame):
            X_array = X.values
        else:
            X_array = np.array(X)
        
        predictions = self.model.predict(X_array)
        n_anomalies = (predictions == -1).sum()
        logger.info(f'Predicted {n_anomalies} anomalies out of {len(predictions)} samples')
        return predictions
    
    def get_params(self):
        """Return model parameters for logging."""
        params = super().get_params()
        params.update({
            'n_estimators': self.n_estimators,
            'max_samples': self.max_samples,
            'max_features': self.max_features,
            'bootstrap': self.bootstrap,
        })
        return params
