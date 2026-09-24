"""
Risk indicator definitions — human-readable descriptions of each risk feature.
"""
RISK_INDICATORS = {
    'price_deviation': {
        'name': 'Price Deviation',
        'description': 'How far the contract amount deviates from the category average (z-score)',
        'high_threshold': 2.0,
        'medium_threshold': 1.0,
        'interpretation': 'A high positive value means the contract is significantly more expensive than similar procurements.',
    },
    'single_bidder_flag': {
        'name': 'Single Bidder',
        'description': 'Whether only one bidder participated in the procurement',
        'high_threshold': 1,
        'medium_threshold': 1,
        'interpretation': 'Single-bidder procurements lack competitive pressure and may warrant review.',
    },
    'vendor_win_frequency': {
        'name': 'Vendor Win Frequency',
        'description': 'Proportion of all contracts won by this vendor',
        'high_threshold': 0.1,
        'medium_threshold': 0.05,
        'interpretation': 'A vendor winning a large share of all contracts may indicate concentration of awards.',
    },
    'vendor_win_concentration': {
        'name': 'Vendor Win Concentration (HHI)',
        'description': 'Herfindahl-Hirschman Index of vendor wins within the same MDA',
        'high_threshold': 0.5,
        'medium_threshold': 0.25,
        'interpretation': 'High HHI within an MDA means one vendor dominates its procurement awards.',
    },
    'splitting_flag': {
        'name': 'Contract Splitting',
        'description': 'Whether the vendor has >3 similar contracts with the same MDA in 12 months',
        'high_threshold': 1,
        'medium_threshold': 1,
        'interpretation': 'Frequent similar contracts to the same vendor may indicate deliberate splitting to avoid thresholds.',
    },
    'splitting_count': {
        'name': 'Splitting Count',
        'description': 'Number of similar contracts in the 12-month window',
        'high_threshold': 5,
        'medium_threshold': 3,
        'interpretation': 'More similar contracts increases the likelihood of intentional splitting.',
    },
    'log_contract_value': {
        'name': 'Log Contract Value',
        'description': 'Log-transformed contract value to reduce skewness',
        'high_threshold': None,
        'medium_threshold': None,
        'interpretation': 'Used as a normalized input; extreme values may flag unusually large procurements.',
    },
}
