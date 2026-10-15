"""
Background runner for the CSV/OCP import pipeline.

Why this exists
---------------
Importing the full OCP dataset (download + staging ~17k rows + validation +
contract creation) takes minutes. Running it inside the request blocked the
worker and looked like a frozen page. The pipeline now runs in a background
thread and reports progress through the ImportJob row, so the Import page
returns immediately and shows live status.

How a job executes (important for local runs)
---------------------------------------------
- An administrator submits the form (upload or OCP download). The upload is
  saved to disk first (fast, synchronous), then an ImportJob row is created
  with status='queued' and a daemon thread in the current process starts
  the pipeline. For the OCP source the download itself happens inside the
  thread.
- All progress lives in the database row (status, stage, heartbeat_at), so
  refreshing the page or opening it in another tab still shows progress —
  nothing depends on the browser session. Polling only reads the row; the
  job keeps running regardless of any browser.
- Heartbeats are written at every stage boundary and periodically during
  long phases (downloads, batch inserts), throttled to avoid database
  churn. If the process dies (Ctrl+C, dev-server reload, machine sleep),
  heartbeats stop and the next status read marks the job 'interrupted'
  with guidance to re-run it — it never silently disappears and it never
  blocks future jobs.
- Single-flight: only one job may be queued/running at a time; stale jobs
  are marked interrupted before a new one is accepted.
- The job lives in the process that serves `python manage.py runserver`;
  stopping the server interrupts the job (recoverable as above). This fits
  the local development setup and adds no infrastructure. A production or
  multi-process deployment should replace the thread with a task queue
  (e.g. Celery): create the ImportJob the same way and call
  `execute_import_job(job_id)` from the worker — the view, status endpoint,
  and stored schema stay unchanged.
- The runner closes its database connections when it finishes.

Statistics semantics (also visible in the Import results UI):
- staging rows_seen/staged/duplicates/missing_id/failed describe the CSV →
  staging step (a "staged" row is not yet a contract).
- validation rows_checked/valid/invalid describe validation.
- contracts_created/contracts_existing/import_failed describe what actually
  reached the contracts table; success is reported only when
  import_failed == 0.
"""

import logging
import threading
import time

from django.db import connections
from django.utils import timezone

from ..models import ImportJob

logger = logging.getLogger(__name__)

STALE_AFTER_SECONDS = 180
HEARTBEAT_MIN_INTERVAL_SECONDS = 2


class ImportAlreadyRunning(Exception):
    """Raised when a job is triggered while another job is still active."""


def latest_job():
    return ImportJob.objects.order_by('-created_at').first()


def interrupt_stale_jobs():
    """Mark active jobs with dead heartbeats as interrupted (recoverable)."""
    now = timezone.now()
    for job in ImportJob.objects.filter(
        status__in=[ImportJob.STATUS_QUEUED, ImportJob.STATUS_RUNNING]
    ):
        reference = job.heartbeat_at or job.started_at or job.updated_at
        age = (now - reference).total_seconds() if reference else None
        if age is None or age > STALE_AFTER_SECONDS:
            job.status = ImportJob.STATUS_INTERRUPTED
            job.stage = 'Interrupted (process stopped unexpectedly)'
            job.finished_at = now
            job.save()


def job_status(job):
    """Serializable status for the status endpoint / page context."""
    if job is None:
        return {'status': 'none', 'stage': '', 'error': ''}

    status = job.status
    interrupted = False
    if status in (ImportJob.STATUS_QUEUED, ImportJob.STATUS_RUNNING):
        reference = job.heartbeat_at or job.started_at or job.updated_at
        age = (timezone.now() - reference).total_seconds() if reference else None
        if age is None or age > STALE_AFTER_SECONDS:
            status = ImportJob.STATUS_INTERRUPTED
            interrupted = True

    return {
        'job_id': job.job_id,
        'status': status,
        'stage': job.stage,
        'error': job.error,
        'interrupted': interrupted,
        'source': job.source,
        'duration_seconds': job.duration_seconds,
        'finished_at': job.finished_at.isoformat() if job.finished_at else None,
    }


def start_import_job(
    user=None,
    source=ImportJob.SOURCE_OCP,
    csv_path='',
    source_name='',
    raw_ids=None,
):
    """Queue a new import job and start it in a background thread.

    raw_ids optionally restricts validation/contract creation to specific
    staged rows (used by tests so they never process the full staging
    table); production calls leave it None.
    """
    interrupt_stale_jobs()
    if ImportJob.objects.filter(
        status__in=[ImportJob.STATUS_QUEUED, ImportJob.STATUS_RUNNING]
    ).exists():
        raise ImportAlreadyRunning('An import job is already in progress.')

    job = ImportJob.objects.create(
        status=ImportJob.STATUS_QUEUED,
        stage='Queued',
        source=source,
        csv_path=str(csv_path or ''),
        source_name=source_name or '',
        triggered_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    thread = threading.Thread(
        target=execute_import_job,
        kwargs={'job_id': job.job_id, 'raw_ids': raw_ids},
        daemon=True,
        name=f'import-job-{job.job_id}',
    )
    thread.start()
    return job


def execute_import_job(job_id, raw_ids=None):
    """Run the full import pipeline and persist results on the row."""
    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        logger.error('Import job %s not found', job_id)
        return

    last_beat = [0.0]

    def stage(text):
        """Persist progress, throttled to HEARTBEAT_MIN_INTERVAL seconds."""
        now = time.monotonic()
        if now - last_beat[0] < HEARTBEAT_MIN_INTERVAL_SECONDS:
            return
        last_beat[0] = now
        job.stage = text[:200]
        job.heartbeat_at = timezone.now()
        job.save(update_fields=['stage', 'heartbeat_at', 'updated_at'])

    try:
        from .csv_importer import (
            download_csv_bundle,
            import_csv_to_raw,
            validate_and_import_records,
        )
        from ..models import Contract, ProcuringEntity, RawRecord, Vendor

        job.status = ImportJob.STATUS_RUNNING
        job.started_at = timezone.now()
        job.error = ''
        job.save()
        stage('Preparing source...')

        if job.source == ImportJob.SOURCE_OCP:
            stage('Downloading OCP data bundle...')
            csv_path = download_csv_bundle(progress=stage)
        else:
            from pathlib import Path
            csv_path = Path(job.csv_path)
            if not str(csv_path):
                raise RuntimeError('No CSV path recorded for this upload job.')
            if not csv_path.exists():
                raise FileNotFoundError(
                    f'Uploaded CSV not found at {csv_path}. The file may have '
                    'been removed before the job started.'
                )

        job.csv_path = str(csv_path)
        job.save(update_fields=['csv_path', 'updated_at'])

        stage('Loading CSV rows into staging...')
        job.staging = import_csv_to_raw(csv_path, progress=stage)
        job.save(update_fields=['staging', 'updated_at'])

        stage('Validating records and creating contracts...')
        job.validation = validate_and_import_records(progress=stage, raw_ids=raw_ids)
        job.save(update_fields=['validation', 'updated_at'])

        stage('Collecting totals...')
        job.totals = {
            'contracts': Contract.objects.count(),
            'raw_records': RawRecord.objects.count(),
            'entities': ProcuringEntity.objects.count(),
            'vendors': Vendor.objects.count(),
        }

        finished = timezone.now()
        job.status = ImportJob.STATUS_SUCCEEDED
        job.finished_at = finished
        job.heartbeat_at = finished
        job.stage = 'Completed'
        if job.started_at:
            job.duration_seconds = (finished - job.started_at).total_seconds()
        job.save()
        logger.info('Import job %s completed in %.1fs', job_id, job.duration_seconds or 0)
    except Exception as exc:
        logger.exception('Import job %s failed', job_id)
        job.status = ImportJob.STATUS_FAILED
        job.error = str(exc) or type(exc).__name__
        job.finished_at = timezone.now()
        job.heartbeat_at = job.finished_at
        job.stage = 'Failed'
        if job.started_at:
            job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
        job.save()
    finally:
        connections.close_all()
