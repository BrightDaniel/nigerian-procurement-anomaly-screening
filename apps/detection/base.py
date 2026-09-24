"""
Base class for anomaly detection models.
"""
import logging
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BaseDetector(ABC):
    """Abstract base class for anomaly detection models.
    
    All detectors must implement fit() and predict().
    """
    
    def __init__(self, contamination=0.05, random_state=42):
        self.contamination = contamination
        self.random_state = random_state
        self.model = None
        self.is_fitted = False
        self.feature_names = None
    
    @abstractmethod
    def fit(self, X):
        """Fit the model on training data.
        
        Args:
            X: DataFrame or array of features
        """
        pass
    
    @abstractmethod
    def predict(self, X):
        """Predict anomalies on new data.
        
        Args:
            X: DataFrame or array of features
            
        Returns:
            numpy array of -1 (anomaly) or 1 (normal)
        """
        pass
    
    def score_samples(self, X):
        """Get anomaly scores for samples.
        
        Returns:
            numpy array of scores (lower = more anomalous)
        """
        if not self.is_fitted:
            raise RuntimeError('Model must be fitted before scoring.')
        return self.model.score_samples(X)
    
    def get_anomaly_scores(self, X):
        """Get normalized anomaly scores between 0 and 1.
        
        Score of 1 = most anomalous, 0 = most normal.
        """
        raw_scores = self.score_samples(X)
        # Invert so higher = more anomalous
        inverted = -raw_scores
        # Normalize to [0, 1]
        min_val = inverted.min()
        max_val = inverted.max()
        if max_val > min_val:
            normalized = (inverted - min_val) / (max_val - min_val)
        else:
            normalized = np.zeros_like(inverted)
        return normalized
    
    def get_feature_names(self):
        """Return feature names used during fitting."""
        return self.feature_names
    
    def get_params(self):
        """Return model parameters for logging."""
        return {
            'model_type': self.__class__.__name__,
            'contamination': self.contamination,
            'random_state': self.random_state,
            'is_fitted': self.is_fitted,
            'n_features': len(self.feature_names) if self.feature_names is not None else 0,
        }
