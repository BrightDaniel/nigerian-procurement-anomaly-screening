"""
Feature registry — each feature has category, source fields, computation formula, and data type.
"""
FEATURE_REGISTRY = {
    'log_contract_value': {
        'category': 'transaction',
        'source_fields': ['amount'],
        'computation': 'log(1 + amount)',
        'data_type': 'continuous',
    },
    'procurement_method_encoded': {
        'category': 'transaction',
        'source_fields': ['method'],
        'computation': 'label_encoded',
        'data_type': 'categorical',
    },
    'procurement_category_encoded': {
        'category': 'transaction',
        'source_fields': ['category'],
        'computation': 'label_encoded',
        'data_type': 'categorical',
    },
    'num_bidders': {
        'category': 'competition',
        'source_fields': ['num_bidders'],
        'computation': 'raw_count',
        'data_type': 'discrete',
    },
    'bidding_window_days': {
        'category': 'competition',
        'source_fields': ['bidding_window_days'],
        'computation': 'raw_days',
        'data_type': 'discrete',
    },
    'single_bidder_flag': {
        'category': 'competition',
        'source_fields': ['num_bidders'],
        'computation': '1 if num_bidders == 1 else 0',
        'data_type': 'binary',
    },
    'vendor_win_frequency': {
        'category': 'supplier',
        'source_fields': ['vendor_id', 'contract_id'],
        'computation': 'vendor_wins / total_contracts',
        'data_type': 'continuous',
    },
    'vendor_win_concentration': {
        'category': 'supplier',
        'source_fields': ['vendor_id', 'entity_id'],
        'computation': 'hhi_of_vendor_wins_per_mda',
        'data_type': 'continuous',
    },
    'price_deviation': {
        'category': 'price',
        'source_fields': ['amount', 'category'],
        'computation': '(amount - mean_category) / std_category',
        'data_type': 'continuous',
    },
    'splitting_flag': {
        'category': 'splitting',
        'source_fields': ['vendor_id', 'entity_id', 'award_date'],
        'computation': '1 if >3 similar contracts same vendor+MDA in 12 months',
        'data_type': 'binary',
    },
    'splitting_count': {
        'category': 'splitting',
        'source_fields': ['vendor_id', 'entity_id', 'award_date'],
        'computation': 'count_of_similar_contracts',
        'data_type': 'discrete',
    },
}
