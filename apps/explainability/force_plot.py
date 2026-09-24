"""
Force plot data preparation for Chart.js rendering.

NOT a technically accurate SHAP force plot.
Authoritative values are in the contribution table above.
"""
import logging

import numpy as np

logger = logging.getLogger(__name__)


def prepare_force_plot_data(shap_values, feature_names, top_k=10):
    """Prepare data for the simplified force plot visualization.
    
    The force plot shows which features pushed the anomaly score higher
    (red) or lower (blue). This is a simplified visualization —
    see the contribution table for authoritative values.
    
    Args:
        shap_values: Array of SHAP values
        feature_names: List of feature names
        top_k: Number of top features to show
        
    Returns:
        list of dicts for Chart.js rendering
    """
    abs_shap = np.abs(shap_values)
    sorted_indices = np.argsort(abs_shap)[::-1][:top_k]
    
    plot_data = []
    for idx in sorted_indices:
        if abs_shap[idx] < 1e-6:
            continue
        
        plot_data.append({
            'feature': feature_names[idx],
            'value': float(shap_values[idx]),
            'abs_value': float(abs_shap[idx]),
            'direction': 'higher' if shap_values[idx] > 0 else 'lower',
            'color': '#c4421a' if shap_values[idx] > 0 else '#486581',  # Brick red vs muted blue
        })
    
    return plot_data


def prepare_contribution_table(explanation):
    """Prepare data for the feature contribution table.
    
    Returns:
        list of dicts with feature name, raw value, contribution, direction
    """
    if not explanation or not explanation.get('feature_importance'):
        return []
    
    table_data = []
    for feat in explanation['feature_importance']:
        table_data.append({
            'feature': feat['feature'],
            'display_name': _get_display_name(feat['feature']),
            'raw_value': feat['feature_value'],
            'contribution': feat['shap_value'],
            'abs_contribution': feat['abs_value'],
            'direction': feat['direction'],
            'direction_label': '↑ Higher' if feat['direction'] == 'positive' else '↓ Lower',
        })
    
    return table_data


def _get_display_name(feature_name):
    """Get human-readable feature name."""
    display_names = {
        'price_deviation': 'Price Deviation',
        'single_bidder_flag': 'Single Bidder',
        'vendor_win_frequency': 'Win Frequency',
        'vendor_win_concentration': 'Win Concentration',
        'splitting_flag': 'Splitting Flag',
        'splitting_count': 'Splitting Count',
        'log_contract_value': 'Contract Value',
        'num_bidders': 'Number of Bidders',
        'bidding_window_days': 'Bidding Window',
        'method_encoded': 'Procurement Method',
        'category_encoded': 'Category',
    }
    return display_names.get(feature_name, feature_name)
