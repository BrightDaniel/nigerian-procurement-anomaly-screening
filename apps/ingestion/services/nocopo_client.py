"""
NOCOPO direct client — thin skeleton.

Placeholder for future integration with the live NOCOPO OpenData export.
This should NOT block Sprint 1. The primary data source is the OCP
Data Registry CSV mirror.
"""
import logging

import requests

logger = logging.getLogger(__name__)

NOCOPO_BASE_URL = 'https://nocopo.npc.gov.ng'


def check_nocopo_availability():
    """Check if the live NOCOPO endpoint is reachable.
    
    Returns:
        dict with status and optional error message
    """
    try:
        response = requests.get(
            f'{NOCOPO_BASE_URL}/api/health',
            timeout=10,
        )
        return {
            'available': response.status_code == 200,
            'status_code': response.status_code,
        }
    except requests.RequestException as e:
        logger.warning(f'NOCOPO endpoint not reachable: {e}')
        return {
            'available': False,
            'error': str(e),
        }


def fetch_latest_releases(limit=100):
    """Skeleton: fetch latest releases from live NOCOPO.
    
    TODO: Implement when comparing freshness against OCP mirror.
    """
    logger.info('NOCOPO direct fetch not yet implemented — use OCP CSV mirror.')
    raise NotImplementedError(
        'NOCOPO direct API client is a skeleton. '
        'Use csv_importer with the OCP Data Registry bundle.'
    )
