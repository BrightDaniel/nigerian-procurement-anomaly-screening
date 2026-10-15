"""
CSV importer for OCP Data Registry bulk files.

Downloads and imports the full.csv.tar.gz bundle from:
https://data.open-contracting.org/en/publication/64

This is the primary data source — the OCP mirror republishes the same
BPP/NOCOPO data as clean OCDS bulk files with no authentication required.
"""
import csv
import io
import tarfile
import logging
import hashlib
import re
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
from django.conf import settings
from django.db import transaction
from django.db.models.fields.json import KeyTextTransform

from apps.ingestion.models import RawRecord, ProcuringEntity, Vendor, Contract
from apps.ingestion.services.ocds_mapping import map_ocds_row

logger = logging.getLogger(__name__)

OCP_PUBLICATION_URL = 'https://data.open-contracting.org/en/publication/64'


def _discover_csv_url():
    """Scrape the OCP publication page for the current CSV download URL.
    
    Looks for the 'full.csv.tar.gz' download link in the page's
    JSON-LD structured data or HTML.
    
    Returns:
        str: The download URL, or None if not found
    """
    try:
        response = requests.get(OCP_PUBLICATION_URL, timeout=30)
        response.raise_for_status()

        # Try JSON-LD first (most reliable)
        jsonld_match = re.search(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            response.text,
            re.DOTALL,
        )
        if jsonld_match:
            import json
            data = json.loads(jsonld_match.group(1))
            for dist in data.get('distribution', []):
                url = dist.get('contentUrl', '')
                if 'full.csv.tar.gz' in url:
                    logger.info(f'Discovered CSV URL from JSON-LD: {url}')
                    return url

        # Fallback: look for href in HTML
        href_match = re.search(
            r'href="(/en/publication/64/download\?name=full\.csv\.tar\.gz)"',
            response.text,
        )
        if href_match:
            url = 'https://data.open-contracting.org' + href_match.group(1)
            logger.info(f'Discovered CSV URL from HTML: {url}')
            return url

    except Exception as e:
        logger.warning(f'URL discovery failed: {e}')

    return None


def download_csv_bundle(url=None, dest_dir=None, progress=None):
    """Download the OCP full.csv.tar.gz bundle and extract to data/raw/.
    
    If the configured URL fails with a 404, attempts to discover
    the current download URL from the OCP publication page.
    
    Args:
        url: Override URL (defaults to NOCOPO_CSV_URL from settings)
        dest_dir: Override destination directory
        progress: Optional callable(stage_text) invoked during the
            download so a background job can keep its heartbeat fresh
    
    Returns:
        Path to extracted CSV file
    """
    url = url or settings.NOCOPO_CSV_URL
    dest_dir = Path(dest_dir or settings.DATA_RAW_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)

    tar_path = dest_dir / 'full.csv.tar.gz'
    csv_path = dest_dir / 'full.csv'

    if csv_path.exists():
        logger.info(f'CSV already exists at {csv_path}, skipping download.')
        return csv_path

    # Try configured URL; on 404, discover current URL from publication page
    try:
        logger.info(f'Downloading OCP data bundle from {url}...')
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.warning(f'Configured URL returned 404, discovering current URL...')
            discovered = _discover_csv_url()
            if discovered and discovered != url:
                url = discovered
                logger.info(f'Retrying with discovered URL: {url}')
                response = requests.get(url, stream=True, timeout=300)
                response.raise_for_status()
            else:
                raise
        else:
            raise

    downloaded = 0
    total_size = int(response.headers.get('Content-Length', 0) or 0)
    with open(tar_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if progress and total_size:
                progress(
                    f'Downloading OCP bundle — {downloaded // (1024 * 1024)} MB '
                    f'of {total_size // (1024 * 1024)} MB'
                )
            elif progress and downloaded % (1024 * 1024 * 5) < 8192:
                progress(f'Downloading OCP bundle — {downloaded // (1024 * 1024)} MB')

    if progress:
        progress('Extracting OCP bundle...')

    logger.info(f'Extracting {tar_path}...')
    with tarfile.open(tar_path, 'r:gz') as tar:
        tar.extractall(path=dest_dir)

    # Find the extracted CSV — look for main.csv first (OCP archive pattern),
    # then any CSV at any depth, then top-level CSV
    csv_path = dest_dir / 'full.csv'
    
    main_csv = dest_dir.rglob('main.csv')
    for candidate in main_csv:
        if candidate != csv_path:
            candidate.rename(csv_path)
            break

    if not csv_path.exists():
        # Fallback: find any CSV file
        csv_files = list(dest_dir.rglob('*.csv'))
        # Filter out .gitkeep and pick the largest CSV
        csv_files = [f for f in csv_files if f.name != '.gitkeep']
        if not csv_files:
            raise FileNotFoundError('No CSV file found after extracting tar.gz')
        csv_files.sort(key=lambda f: f.stat().st_size, reverse=True)
        csv_file = csv_files[0]
        if csv_file != csv_path:
            csv_file.rename(csv_path)

    # Save snapshot for reproducibility
    _save_snapshot(csv_path, dest_dir)

    logger.info(f'CSV extracted to {csv_path}')
    return csv_path


def _save_snapshot(csv_path, dest_dir):
    """Save a frozen snapshot with hash and timestamp for reproducibility."""
    snapshot_dir = Path(settings.DATA_SNAPSHOTS_DIR)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    file_hash = hashlib.md5(open(csv_path, 'rb').read()).hexdigest()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    snapshot_name = f'ocp_snapshot_{timestamp}_{file_hash[:8]}.csv'
    snapshot_path = snapshot_dir / snapshot_name

    import shutil
    shutil.copy2(csv_path, snapshot_path)
    logger.info(f'Snapshot saved: {snapshot_path}')


def import_csv_to_raw(csv_path, batch_size=1000, progress=None):
    """Import OCP CSV bundle into RawRecord staging table.
    
    The OCP bundle contains multiple CSV files that need joining:
    - main.csv: contracting process metadata (buyer, tender info)
    - awards.csv: award details (title, value, date)
    - awards_suppliers.csv: supplier names linked to awards
    
    This function joins them into a single flat dict per award and
    stores it in the RawRecord.ocds_release JSONField.
    
    Args:
        csv_path: Path to the extracted bundle directory or main CSV
        batch_size: Number of records to insert per batch
        progress: Optional callable(stage_text) invoked periodically so a
            background job can persist progress heartbeats
    
    Returns:
        dict with staging statistics:
            rows_seen    — rows present in the joined CSV
            staged       — new rows written to the staging table
            duplicates   — rows skipped because the award id is already staged
            missing_id   — rows skipped because they have no award id
            failed       — rows lost to staging insert failures
    """
    stats = {'rows_seen': 0, 'staged': 0, 'duplicates': 0, 'missing_id': 0, 'failed': 0}
    
    # Resolve the bundle directory
    csv_path = Path(csv_path)
    if csv_path.is_file():
        bundle_dir = csv_path.parent
    else:
        bundle_dir = csv_path
    
    # If we have a full/ subdirectory (OCP archive pattern), use it
    full_dir = bundle_dir / 'full'
    if full_dir.is_dir():
        bundle_dir = full_dir
    
    # Also check if main.csv is at bundle_dir level (renamed from main.csv)
    main_csv = bundle_dir / 'main.csv'
    if not main_csv.exists():
        # Try parent level
        main_csv = bundle_dir.parent / 'full.csv'
        if not main_csv.exists():
            # Look for any main.csv
            candidates = list(bundle_dir.rglob('main.csv'))
            if candidates:
                main_csv = candidates[0]
            else:
                raise FileNotFoundError(f'No main.csv found in {bundle_dir}')
    
    source_file = main_csv.name
    logger.info(f'Importing OCP bundle from {bundle_dir}...')
    
    # Read all CSV files into DataFrames
    awards_csv = bundle_dir / 'awards.csv'
    suppliers_csv = bundle_dir / 'awards_suppliers.csv'
    
    if not awards_csv.exists():
        raise FileNotFoundError(f'awards.csv not found in {bundle_dir}')
    
    logger.info(f'Reading main.csv ({main_csv})...')
    main_df = pd.read_csv(main_csv, dtype=str, encoding='utf-8', on_bad_lines='skip')
    main_df = main_df.fillna('')
    
    logger.info(f'Reading awards.csv ({awards_csv})...')
    awards_df = pd.read_csv(awards_csv, dtype=str, encoding='utf-8', on_bad_lines='skip')
    awards_df = awards_df.fillna('')
    
    # Join awards with main on ocid/main_ocid
    if 'main_ocid' in awards_df.columns and 'ocid' in main_df.columns:
        joined = awards_df.merge(
            main_df[['ocid', 'buyer_name', 'buyer_id',
                      'tender_procurementMethod', 'tender_numberOfTenderers',
                      'tender_tenderPeriod_durationInDays',
                      'tender_procuringEntity_name']],
            left_on='main_ocid', right_on='ocid', how='left', suffixes=('', '_main'),
        )
    else:
        logger.warning('Cannot join awards with main: missing key columns')
        joined = awards_df
    
    # Join with suppliers if available
    if suppliers_csv.exists():
        logger.info(f'Reading awards_suppliers.csv ({suppliers_csv})...')
        suppliers_df = pd.read_csv(suppliers_csv, dtype=str, encoding='utf-8', on_bad_lines='skip')
        suppliers_df = suppliers_df.fillna('')
        
        if 'awards_id' in suppliers_df.columns and 'id' in joined.columns:
            # Get first supplier per award
            first_supplier = suppliers_df.groupby('awards_id').first().reset_index()
            joined = joined.merge(
                first_supplier[['awards_id', 'name']],
                left_on='id', right_on='awards_id', how='left', suffixes=('', '_supplier'),
            )
            joined['supplier_name'] = joined.get('name_supplier', joined.get('name', ''))
        else:
            joined['supplier_name'] = ''
    else:
        joined['supplier_name'] = ''
    
    logger.info(f'Joined {len(joined)} award records')

    # Existing award ids are loaded once: the stored JSON uses flat keys
    # ('awards/id'), so the old per-row nested-path lookup matched nothing
    # and re-imports duplicated the whole dataset.
    existing_award_ids = {
        aid for aid in RawRecord.objects.values_list(
            KeyTextTransform('awards/id', 'ocds_release'), flat=True
        ) if aid
    }

    # Convert to flat dicts matching expected OCDS-like structure
    records = []
    for _, row in joined.iterrows():
        stats['rows_seen'] += 1
        
        # Use award id as unique identifier
        award_id = str(row.get('id', '')).strip()
        if not award_id:
            stats['missing_id'] += 1
            continue
        
        # Check for duplicate (staged rows and earlier rows in this file)
        if award_id in existing_award_ids:
            stats['duplicates'] += 1
            continue
        existing_award_ids.add(award_id)
        
        # Build flat dict for ocds_release
        flat = {
            'awards/id': award_id,
            'awards/title': str(row.get('title', '')).strip(),
            'awards/value/amount': str(row.get('value_amount', '0')).strip(),
            'awards/value/currency': str(row.get('value_currency', 'NGN')).strip(),
            'awards/date': str(row.get('date', '')).strip(),
            'tender/numberOfTenderers': str(row.get('tender_numberOfTenderers', '')).strip(),
            'tender/period/durationInDays': str(row.get('tender_tenderPeriod_durationInDays', '')).strip(),
            'tender/procurementMethod': str(row.get('tender_procurementMethod', '')).strip(),
            'awards/suppliers/0/name': str(row.get('supplier_name', '')).strip(),
            'buyer/name': str(row.get('buyer_name', '')).strip(),
            'awards/items/0/description': str(row.get('description', '')).strip(),
        }
        
        records.append(RawRecord(
            source_file=source_file,
            ocds_release=flat,
        ))
        
        if len(records) >= batch_size:
            _flush_batch(records, stats)
            records = []
            if progress:
                progress(
                    f'Staged {stats["staged"]:,} of {stats["rows_seen"]:,} rows '
                    f'({stats["duplicates"]:,} duplicates skipped)'
                )
    
    if records:
        _flush_batch(records, stats)

    if progress:
        progress(
            f'Staging complete: {stats["staged"]:,} new rows, '
            f'{stats["duplicates"]:,} duplicates skipped'
        )
    
    logger.info(
        f'Staging complete: {stats["staged"]} staged, '
        f'{stats["duplicates"]} duplicates, {stats["missing_id"]} missing ids, '
        f'{stats["failed"]} failed out of {stats["rows_seen"]} rows seen'
    )
    return stats


def _flush_batch(batch, stats):
    """Insert a batch of RawRecords into the database."""
    try:
        with transaction.atomic():
            RawRecord.objects.bulk_create(batch, ignore_conflicts=True)
            stats['staged'] += len(batch)
    except Exception as e:
        logger.error(f'Batch insert failed: {e}')
        stats['failed'] += len(batch)


def validate_and_import_records(batch_size=500, progress=None, raw_ids=None):
    """Validate RawRecords and import valid ones into the main tables.
    
    Processes every staged row that has not been imported yet (including
    rows validated in an earlier run whose contract insert failed, so a
    failed batch can be recovered by simply running the import again).
    
    Args:
        batch_size: Records per import batch
        progress: Optional callable(stage_text) for background heartbeats
        raw_ids: Optional iterable of raw ids to restrict processing to
            (used by tests to avoid touching the full staging table)
    
    Returns:
        dict with validation/import statistics:
            rows_checked      — staged rows considered by this run
            valid             — rows that passed validation
            invalid           — rows that failed validation
            contracts_created — contracts actually persisted this run
            contracts_existing— valid rows whose contract already existed
            import_failed     — unexpected insert failures (should be 0)
            validation_errors — [{raw_id, errors}] for rejected rows
            import_errors     — [{raw_id, error}] for failed inserts
    """
    stats = {
        'rows_checked': 0, 'valid': 0, 'invalid': 0,
        'contracts_created': 0, 'contracts_existing': 0,
        'import_failed': 0, 'validation_errors': [], 'import_errors': [],
    }

    pending = RawRecord.objects.filter(is_imported=False).order_by('raw_id')
    if raw_ids is not None:
        pending = pending.filter(raw_id__in=list(raw_ids))
    logger.info(f'Validating {pending.count()} raw records...')

    # Existing nocopo ids are preloaded so duplicate contracts are counted
    # as "already present" instead of crashing the batch on the unique key.
    existing_nocopo = {
        n for n in Contract.objects.values_list('nocopo_id', flat=True) if n
    }

    batch = []
    for raw in pending.iterator():
        stats['rows_checked'] += 1
        mapped = map_ocds_row(raw.ocds_release)

        errors = _validate_mapped_record(mapped)
        if errors:
            if raw.validation_errors != errors:
                raw.is_validated = True
                raw.validation_errors = errors
                raw.save(update_fields=['is_validated', 'validation_errors'])
            stats['invalid'] += 1
            stats['validation_errors'].append({'raw_id': raw.raw_id, 'errors': errors})
            continue

        if not raw.is_validated:
            raw.is_validated = True
            raw.save(update_fields=['is_validated'])
        stats['valid'] += 1
        batch.append((raw, mapped))

        if len(batch) >= batch_size:
            _import_validated_batch(batch, stats, existing_nocopo)
            batch = []
            if progress:
                progress(
                    f'Checked {stats["rows_checked"]:,} rows — '
                    f'{stats["contracts_created"]:,} contracts created, '
                    f'{stats["contracts_existing"]:,} already present'
                )

    if batch:
        _import_validated_batch(batch, stats, existing_nocopo)

    logger.info(
        f'Validation complete: {stats["valid"]} valid, '
        f'{stats["invalid"]} invalid out of {stats["rows_checked"]}; '
        f'{stats["contracts_created"]} contracts created, '
        f'{stats["contracts_existing"]} already present, '
        f'{stats["import_failed"]} failed'
    )
    return stats


def _validate_mapped_record(mapped):
    """Validate a mapped record against required fields."""
    errors = []
    if not mapped.get('title'):
        errors.append('Missing contract title')
    if not mapped.get('amount') or mapped['amount'] == 0:
        errors.append('Missing or zero contract amount')
    if not mapped.get('nocopo_id'):
        errors.append('Missing OCDS ID (nocopo_id)')
    return errors


def _import_validated_batch(batch, stats, existing_nocopo):
    """Import validated records into ProcuringEntity, Vendor, and Contract tables.

    Each record commits inside its own savepoint. A failure on one record
    (for example a duplicate nocopo_id) rolls back only that record —
    previously the whole batch shared one transaction, so a single
    IntegrityError poisoned it and PostgreSQL silently discarded every
    insert the counters had already recorded.
    """
    for raw, mapped in batch:
        if mapped['nocopo_id'] in existing_nocopo:
            stats['contracts_existing'] += 1
            raw.is_imported = True
            raw.save(update_fields=['is_imported'])
            continue

        try:
            with transaction.atomic():
                # Create or get procuring entity
                entity = None
                entity_name = mapped.get('entity_name', '').strip()
                if entity_name:
                    entity, _ = ProcuringEntity.objects.get_or_create(
                        name=entity_name,
                        defaults={'type': mapped.get('type')},
                    )

                # Create or get vendor
                vendor = None
                vendor_name = mapped.get('vendor_name', '').strip()
                if vendor_name:
                    vendor, _ = Vendor.objects.get_or_create(
                        name=vendor_name,
                    )

                # Create contract
                Contract.objects.create(
                    entity=entity,
                    vendor=vendor,
                    title=mapped['title'],
                    amount=mapped['amount'],
                    currency=mapped.get('currency', 'NGN'),
                    award_date=mapped.get('award_date'),
                    bidding_window_days=mapped.get('bidding_window_days'),
                    num_bidders=mapped.get('num_bidders'),
                    method=mapped.get('method'),
                    category=mapped.get('category'),
                    description=mapped.get('description'),
                    nocopo_id=mapped['nocopo_id'],
                )

            existing_nocopo.add(mapped['nocopo_id'])
            stats['contracts_created'] += 1
            raw.is_imported = True
            raw.save(update_fields=['is_imported'])

        except Exception as e:
            logger.error(f'Failed to import raw {raw.raw_id}: {e}')
            stats['import_failed'] += 1
            stats['import_errors'].append({'raw_id': raw.raw_id, 'error': str(e)})
