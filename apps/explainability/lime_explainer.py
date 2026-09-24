"""
LIME explainer for anomaly detection models.

LIME (Local Interpretable Model-agnostic Explanations) provides
an alternative explanation method to SHAP.
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LIMEExplainer:
    """LIME-based explainer for anomaly detection models.
    
    Provides local explanations by approximating the model
    with an interpretable model in the neighbourhood of each prediction.
    """
    
    def __init__(self, model, feature_names=None, class_names=None):
        """Initialize LIME explainer.
        
        Args:
            model: Fitted sklearn model
            feature_names: List of feature names
            class_names: Class names for display
        """
        self.model = model
        self.feature_names = feature_names or []
        self.class_names = class_names or ['Normal', 'Anomaly']
        self.explainer = None
        self._initialize_explainer()
    
    def _initialize_explainer(self):
        """Create the LIME explainer."""
        try:
            from lime.lime_tabular import LimeTabularExplainer
            self.lime_class = LimeTabularExplainer
            logger.info('LIME explainer class loaded successfully')
        except ImportError:
            logger.warning('LIME not installed. LIME explanations unavailable.')
            self.lime_class = None
    
    def explain(self, X, num_features=5):
        """Compute LIME explanations for a set of samples.
        
        Args:
            X: DataFrame or array of features
            num_features: Number of features in explanation
            
        Returns:
            list of explanation dicts
        """
        if self.lime_class is None:
            logger.warning('LIME not available, returning empty explanations')
            return [{'error': 'LIME not installed'}] * len(X)
        
        if isinstance(X, pd.DataFrame):
            X_array = X.values
            feature_names = X.columns.tolist()
        else:
            X_array = np.array(X)
            feature_names = self.feature_names
        
        explainer = self.lime_class(
            training_data=X_array,
            feature_names=feature_names,
            class_names=self.class_names,
            mode='classification',
        )
        
        explanations = []
        for i in range(len(X_array)):
            try:
                exp = explainer.explain_instance(
                    X_array[i],
                    self._predict_proba,
                    num_features=num_features,
                )
                
                # Convert LIME explanation to our format
                feature_importance = []
                for feat_idx, weight in exp.as_list():
                    if isinstance(feat_idx, str):
                        feature_name = feat_idx
                    else:
                        feature_name = feature_names[feat_idx] if feat_idx < len(feature_names) else f'feature_{feat_idx}'
                    
                    feature_importance.append({
                        'feature': feature_name,
                        'lime_weight': float(weight),
                        'abs_weight': abs(float(weight)),
                        'direction': 'positive' if weight > 0 else 'negative',
                    })
                
                explanations.append({
                    'feature_importance': feature_importance,
                    'intercept': float(exp.intercept[1]) if hasattr(exp, 'intercept') else 0,
                    'local_pred_score': float(exp.local_pred[1]) if hasattr(exp, 'local_pred') else 0,
                })
                
            except Exception as e:
                logger.warning(f'LIME explanation failed for sample {i}: {e}')
                explanations.append({'error': str(e)})
        
        return explanations
    
    def _predict_proba(self, X):
        """Predict class probabilities for LIME.
        
        LIME requires probability predictions. For models that don't
        support predict_proba, we convert decision_function scores.
        """
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X)
        else:
            # Convert decision_function to pseudo-probabilities
            scores = self.model.decision_function(X)
            # Sigmoid transformation
            probs = 1 / (1 + np.exp(-scores))
            return np.column_stack([1 - probs, probs])
