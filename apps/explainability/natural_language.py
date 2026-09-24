"""
Natural language explanation generator.

Converts SHAP feature attributions into plain-English explanations
that explicitly distinguish "feature contribution" from any implication of fraud.
"""
import logging

from decimal import Decimal

logger = logging.getLogger(__name__)

# Feature display names for human-readable output
FEATURE_DISPLAY_NAMES = {
    'price_deviation': 'price deviation from category average',
    'single_bidder_flag': 'single-bidder procurement',
    'vendor_win_frequency': 'vendor win frequency',
    'vendor_win_concentration': 'vendor win concentration per MDA',
    'splitting_flag': 'contract splitting pattern',
    'splitting_count': 'number of similar contracts',
    'log_contract_value': 'contract value',
    'num_bidders': 'number of bidders',
    'bidding_window_days': 'bidding window duration',
    'method_encoded': 'procurement method',
    'category_encoded': 'procurement category',
}


def generate_natural_language(explanation, contract_data=None):
    """Generate a natural-language explanation from SHAP values.
    
    Language rules:
    - Always says "contributed to the anomaly score" — never "indicates fraud"
    - Always says "flagged for review" — never "suspicious"
    - Always says "may warrant further investigation" — never "requires investigation"
    
    Args:
        explanation: dict from SHAPExplainer.explain_single()
        contract_data: Optional dict with contract metadata for context
        
    Returns:
        str: Natural-language explanation (2-4 sentences)
    """
    if not explanation or not explanation.get('feature_importance'):
        return 'Explanation not available for this record.'
    
    features = explanation['feature_importance']
    
    # Get top contributing features
    top_features = [f for f in features if f['abs_value'] > 0.01][:3]
    
    if not top_features:
        return (
            'This record has an anomaly score that places it within normal parameters. '
            'No single feature significantly contributed to its score.'
        )
    
    # Build explanation sentences
    sentences = []
    
    # Opening sentence
    sentences.append(_build_opening_sentence(features, contract_data))
    
    # Feature contribution sentences
    for feat in top_features[:2]:  # Limit to top 2 for brevity
        sentence = _build_feature_sentence(feat)
        sentences.append(sentence)
    
    # Closing sentence
    sentences.append(_build_closing_sentence())
    
    return ' '.join(sentences)


def _build_opening_sentence(features, contract_data):
    """Build the opening sentence of the explanation."""
    # Find the strongest contributor
    top = features[0]
    feature_name = FEATURE_DISPLAY_NAMES.get(top['feature'], top['feature'])
    
    if top['direction'] == 'positive':
        return (
            f'This record was flagged primarily because of its {feature_name}, '
            f'which contributed positively to the anomaly score.'
        )
    else:
        return (
            f'This record was flagged, though its {feature_name} '
            f'actually contributed negatively to the anomaly score (counteracting other factors).'
        )


def _build_feature_sentence(feature):
    """Build a sentence describing a feature's contribution."""
    feature_name = FEATURE_DISPLAY_NAMES.get(feature['feature'], feature['feature'])
    value = feature['feature_value']
    direction = feature['direction']
    
    # Format value based on feature type
    formatted_value = _format_feature_value(feature['feature'], value)
    
    if direction == 'positive':
        return (
            f'The {feature_name} of {formatted_value} '
            f'pushed the anomaly score higher.'
        )
    else:
        return (
            f'The {feature_name} of {formatted_value} '
            f'pushed the anomaly score lower.'
        )


def _build_closing_sentence():
    """Build the closing sentence with appropriate disclaimer."""
    return (
        'These feature contributions indicate records that may warrant '
        'further review. This system flags records for investigation — '
        'it does not detect fraud or wrongdoing.'
    )


def _format_feature_value(feature_name, value):
    """Format a feature value for display."""
    if feature_name in ('single_bidder_flag', 'splitting_flag'):
        return 'True' if value > 0.5 else 'False'
    elif feature_name == 'log_contract_value':
        # Convert back from log scale
        import math
        actual_value = math.exp(value) - 1
        if actual_value >= 1_000_000:
            return f'₦{actual_value/1_000_000:,.1f}M'
        elif actual_value >= 1_000:
            return f'₦{actual_value/1_000:,.1f}K'
        else:
            return f'₦{actual_value:,.2f}'
    elif feature_name == 'splitting_count':
        return str(int(value))
    elif feature_name in ('vendor_win_frequency', 'vendor_win_concentration'):
        return f'{value:.4f}'
    elif feature_name == 'price_deviation':
        return f'{value:.2f} standard deviations'
    else:
        return str(value)


def generate_batch_explanations(explanations, contract_data_list=None):
    """Generate natural-language explanations for multiple records.
    
    Args:
        explanations: List of dicts from SHAPExplainer.explain()
        contract_data_list: Optional list of contract metadata dicts
        
    Returns:
        list of str: Natural-language explanations
    """
    results = []
    for i, explanation in enumerate(explanations):
        contract_data = contract_data_list[i] if contract_data_list else None
        nl = generate_natural_language(explanation, contract_data)
        results.append(nl)
    
    return results
