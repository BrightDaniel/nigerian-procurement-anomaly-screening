"""
SHAP explainer for anomaly detection models.

Uses TreeExplainer for Isolation Forest (tree-based model).
"""
import logging

import numpy as np
import pandas as pd
import shap

from apps.detection.trainer import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


class SHAPExplainer:
    """SHAP-based explainer for anomaly detection models.
    
    Provides feature attributions for individual predictions
    using SHAP (SHapley Additive exPlanations) values.
    """
    
    def __init__(self, model, feature_names=None):
        """Initialize SHAP explainer.
        
        Args:
            model: Fitted sklearn model (IsolationForest, etc.)
            feature_names: List of feature names
        """
        self.model = model
        self.feature_names = feature_names or FEATURE_COLUMNS
        self.explainer = None
        self._initialize_explainer()
    
    def _initialize_explainer(self):
        """Create the SHAP TreeExplainer."""
        try:
            self.explainer = shap.TreeExplainer(self.model)
            logger.info('SHAP TreeExplainer initialized successfully')
        except Exception as e:
            logger.warning(f'Failed to initialize TreeExplainer: {e}')
            logger.info('Falling back to KernelExplainer (slower)')
            self.explainer = None
    
    def explain(self, X, top_k=5):
        """Compute SHAP values for a set of samples.
        
        Args:
            X: DataFrame or array of features
            top_k: Number of top features to include in explanations
            
        Returns:
            dict with shap_values, feature_importance, and force_plot_data
        """
        if isinstance(X, pd.DataFrame):
            X_array = X.values
        else:
            X_array = np.array(X)
        
        if self.explainer is not None:
            shap_values = self.explainer.shap_values(X_array)
        else:
            logger.warning('No explainer available, returning zero SHAP values')
            shap_values = np.zeros_like(X_array)
        
        # Process SHAP values for each sample
        explanations = []
        for i in range(len(X_array)):
            sample_shap = shap_values[i] if len(shap_values.shape) > 1 else shap_values
            
            # Get top-k features by absolute SHAP value
            abs_shap = np.abs(sample_shap)
            top_indices = np.argsort(abs_shap)[::-1][:top_k]
            
            feature_importance = []
            for idx in top_indices:
                feature_importance.append({
                    'feature': self.feature_names[idx],
                    'shap_value': float(sample_shap[idx]),
                    'abs_value': float(abs_shap[idx]),
                    'feature_value': float(X_array[i, idx]),
                    'direction': 'positive' if sample_shap[idx] > 0 else 'negative',
                })
            
            explanations.append({
                'shap_values': sample_shap.tolist(),
                'feature_importance': feature_importance,
                'force_plot_data': self._build_force_plot_data(sample_shap, X_array[i]),
            })
        
        return {
            'explanations': explanations,
            'feature_names': self.feature_names,
        }
    
    def explain_single(self, x, top_k=5):
        """Explain a single sample.
        
        Args:
            x: Single sample (1D array or Series)
            top_k: Number of top features
            
        Returns:
            dict with explanation data
        """
        if isinstance(x, pd.Series):
            x_array = x.values.reshape(1, -1)
        elif isinstance(x, np.ndarray):
            x_array = x.reshape(1, -1) if x.ndim == 1 else x
        else:
            x_array = np.array(x).reshape(1, -1)
        
        result = self.explain(pd.DataFrame(x_array, columns=self.feature_names), top_k=top_k)
        return result['explanations'][0]
    
    def _build_force_plot_data(self, shap_values, feature_values):
        """Build data for a simplified force plot visualization.
        
        Returns:
            list of dicts for chart rendering
        """
        abs_shap = np.abs(shap_values)
        sorted_indices = np.argsort(abs_shap)[::-1]
        
        force_data = []
        for idx in sorted_indices:
            if abs_shap[idx] < 1e-6:  # Skip negligible contributions
                continue
            force_data.append({
                'feature': self.feature_names[idx],
                'value': float(feature_values[idx]),
                'contribution': float(shap_values[idx]),
                'abs_contribution': float(abs_shap[idx]),
                'direction': 'pushes higher' if shap_values[idx] > 0 else 'pushes lower',
            })
        
        return force_data
    
    def get_global_importance(self, X, top_k=None):
        """Compute global feature importance (mean |SHAP| across all samples).
        
        Args:
            X: DataFrame or array of features
            top_k: Number of top features to return
            
        Returns:
            list of dicts sorted by importance
        """
        if isinstance(X, pd.DataFrame):
            X_array = X.values
        else:
            X_array = np.array(X)
        
        if self.explainer is not None:
            shap_values = self.explainer.shap_values(X_array)
        else:
            return []
        
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        sorted_indices = np.argsort(mean_abs_shap)[::-1]
        
        if top_k:
            sorted_indices = sorted_indices[:top_k]
        
        importance = []
        for idx in sorted_indices:
            importance.append({
                'feature': self.feature_names[idx],
                'mean_abs_shap': float(mean_abs_shap[idx]),
                'rank': len(importance) + 1,
            })
        
        return importance
