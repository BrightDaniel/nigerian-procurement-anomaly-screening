"""
Validators for raw OCDS records before import into main tables.
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def validate_ocds_release(release_dict):
    """Validate an OCDS release dictionary.
    
    Returns:
        tuple: (is_valid: bool, errors: list[str])
    """
    errors = []

    # Required fields check
    awards = release_dict.get('awards', [])
    if not awards:
        errors.append('No awards found in release')
    else:
        award = awards[0] if isinstance(awards, list) else awards
        if not award.get('id'):
            errors.append('Award missing ID')
        if not award.get('title'):
            errors.append('Award missing title')
        value = award.get('value', {})
        if not value or not value.get('amount'):
            errors.append('Award missing value/amount')

    # Date sanity check
    award_date = release_dict.get('awards', [{}])[0].get('date', '') if release_dict.get('awards') else ''
    if award_date:
        try:
            from apps.ingestion.services.ocds_mapping import parse_date, KNOWN_YEAR_OUTLIERS
            dt = parse_date(award_date)
            if dt and dt.year in KNOWN_YEAR_OUTLIERS:
                errors.append(f'Outlier year in award date: {dt.year}')
        except Exception:
            pass

    # OCID prefix check
    ocid = release_dict.get('ocid', '')
    if ocid:
        from apps.ingestion.services.ocds_mapping import KNOWN_BAD_OCID_PREFIX
        if ocid.startswith(KNOWN_BAD_OCID_PREFIX):
            errors.append(f'Known incorrect OCID prefix: {ocid}')

    return len(errors) == 0, errors
