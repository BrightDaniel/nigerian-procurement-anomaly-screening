"""
OCDS field mapping for the OCP Data Registry CSV bundle.

Maps NOCOPO/OCP CSV column names to internal Contract model fields.
The OCP mirror publishes the same BPP/NOCOPO data in OCDS format.
"""
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# OCP CSV column → internal field mapping
OCDS_FIELD_MAP = {
    'awards/id': 'nocopo_id',
    'awards/title': 'title',
    'awards/value/amount': 'amount',
    'awards/value/currency': 'currency',
    'awards/date': 'award_date',
    'tender/numberOfTenderers': 'num_bidders',
    'tender/period/durationInDays': 'bidding_window_days',
    'tender/procurementMethod': 'method',
    'awards/suppliers/0/name': 'vendor_name',
    'buyer/name': 'entity_name',
    'awards/items/0/classification/scheme': 'category',
    'awards/items/0/description': 'description',
    'awards/items/0/classification/id': 'category_id',
}

# Known dataset quality issues from the OCP Data Registry flags:
# - Inconsistent award dates (outliers: 1949, 2919)
# - Release dates clustering on a single day in 2021
# - 93 contracting processes with incorrect OCID prefix
KNOWN_YEAR_OUTLIERS = {1949, 2919}
KNOWN_BAD_OCID_PREFIX = 'ocds-b5d162-'  # incorrect prefix subset


def parse_amount(value):
    """Parse amount from string/float to Decimal."""
    from decimal import Decimal, InvalidOperation
    if not value:
        return Decimal('0')
    try:
        cleaned = str(value).replace(',', '').strip()
        return Decimal(cleaned)
    except InvalidOperation:
        logger.warning(f'Could not parse amount: {value}')
        return Decimal('0')


def parse_date(value):
    """Parse date string, flagging known outlier years."""
    if not value:
        return None
    try:
        dt = datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
        if dt.year in KNOWN_YEAR_OUTLIERS:
            logger.warning(f'Outlier award date year detected: {dt.year} (value: {value})')
        return dt
    except (ValueError, TypeError):
        try:
            dt = datetime.strptime(str(value)[:10], '%d/%m/%Y').date()
            if dt.year in KNOWN_YEAR_OUTLIERS:
                logger.warning(f'Outlier award date year detected: {dt.year} (value: {value})')
            return dt
        except (ValueError, TypeError):
            logger.warning(f'Could not parse date: {value}')
            return None


def parse_int(value):
    """Parse integer value, returning None on failure."""
    if not value:
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def map_ocds_row(row):
    """Map a single OCP CSV row dict to internal model fields.
    
    Returns a dict suitable for creating Contract/ProcuringEntity/Vendor objects.
    """
    mapped = {}

    # Direct field mappings
    for ocds_field, internal_field in OCDS_FIELD_MAP.items():
        if ocds_field in row and row[ocds_field]:
            mapped[internal_field] = row[ocds_field]

    # Type conversions
    if 'amount' in mapped:
        mapped['amount'] = parse_amount(mapped['amount'])
    if 'award_date' in mapped:
        mapped['award_date'] = parse_date(mapped['award_date'])
    if 'num_bidders' in mapped:
        mapped['num_bidders'] = parse_int(mapped['num_bidders'])
    if 'bidding_window_days' in mapped:
        mapped['bidding_window_days'] = parse_int(mapped['bidding_window_days'])

    return mapped
