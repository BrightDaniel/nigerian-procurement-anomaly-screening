"""
Local Outlier Factor anomaly detector.
"""
import logging

import numpy as np
import pandas as pd
from sklearn.neighbors import LocalOutlierFactor

from apps.detection.base import BaseDetector

logger = logging.getLogger(__name__)


class LOFDetector(BaseDetector):
    """Local Outlier Factor for anomaly detection.
    
    Density-based detector that compares local density of a point
    to its neighbours. Points with significantly lower density
    are considered anomalies.
    
    Parameters:
        n_neighbors: Number of neighbours to consider (default 20)
        contamination: Expected proportion of anomalies (default 0.05)
        metric: Distance metric (default 'minkowski')
        novelty: If True, use for prediction on new data (default False)
    """
    
    def __init__(
        self,
        n_neighbors=20,
        contamination=0.05,
        metric='minkowski',
        novelty=False,
        random_state=42,
    ):
        super().__init__(contamination=contamination, random_state=random_state)
        self.n_neighbors = n_neighbors
        self.metric = metric
        self.novelty = novelty
    
    def fit(self, X):
        """Fit LOF on training data.
        
        When novelty=False (default), fit_predict is used internally
        since sklearn LOF only supports predict() with novelty=True.
        
        Args:
            X: DataFrame or array of features
        """
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
            X_array = X.values
        else:
            X_array = np.array(X)
            self.feature_names = [f'feature_{i}' for i in range(X_array.shape[1])]
        
        logger.info(
            f'Fitting LOF: n_neighbors={self.n_neighbors}, '
            f'contamination={self.contamination}, novelty={self.novelty}, '
            f'{X_array.shape[0]} samples, {X_array.shape[1]} features'
        )
        
        self.model = LocalOutlierFactor(
            n_neighbors=self.n_neighbors,
            contamination=self.contamination,
            metric=self.metric,
            novelty=self.novelty,
        )
        
        if self.novelty:
            self.model.fit(X_array)
        else:
            self._predictions = self.model.fit_predict(X_array)
        
        self._X_array = X_array
        self.is_fitted = True
        
        logger.info('LOF fitted successfully.')
        return self
    
    def predict(self, X):
        """Predict anomalies: -1 = anomaly, 1 = normal."""
        if not self.is_fitted:
            raise RuntimeError('Model must be fitted before prediction.')
        
        if self.novelty:
            if isinstance(X, pd.DataFrame):
                X_array = X.values
            else:
                X_array = np.array(X)
            predictions = self.model.predict(X_array)
        else:
            predictions = self._predictions
        
        n_anomalies = (predictions == -1).sum()
        logger.info(f'LOF predicted {n_anomalies} anomalies out of {len(predictions)} samples')
        return predictions
    
    def get_anomaly_scores(self, X):
        """Get LOF anomaly scores normalized to [0, 1] where 1 = most anomalous.
        
        Uses rank-based normalization among flagged records only, so flagged
        scores are uniformly distributed across [0, 1] and priority thresholds
        (0.95 High, 0.80 Medium) create meaningful separation.
        
        Normal (non-flagged) records receive score 0.0.
        Preserves the original LOF anomaly ordering within flagged records.
        """
        if not self.is_fitted:
            raise RuntimeError('Model must be fitted before scoring.')
        
        raw_scores = self.model.negative_outlier_factor_
        predictions = self._predictions
        inverted = -raw_scores
        
        flagged_mask = predictions == -1
        flagged_scores = inverted[flagged_mask]
        
        if len(flagged_scores) > 0:
            # Rank-based: rank 0 = least anomalous among flagged, rank n-1 = most
            order = np.argsort(flagged_scores)
            ranks = np.empty_like(order, dtype=float)
            ranks[order] = np.arange(len(flagged_scores), dtype=float)
            normalized_flagged = ranks / (len(flagged_scores) - 1) if len(flagged_scores) > 1 else np.ones(1)
        else:
            normalized_flagged = np.array([])
        
        result = np.zeros_like(inverted)
        result[flagged_mask] = normalized_flagged
        return result
    
    def get_params(self):
        """Return model parameters for logging."""
        params = super().get_params()
        params.update({
            'n_neighbors': self.n_neighbors,
            'metric': self.metric,
            'novelty': self.novelty,
        })
        return params
