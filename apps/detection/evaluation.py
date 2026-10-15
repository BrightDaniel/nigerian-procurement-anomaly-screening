"""
Background runner for the Model Performance evaluation pipeline.

Why this exists
---------------
The synthetic evaluation and contamination-sensitivity analysis train
scikit-learn models and take tens of seconds. Running them inside the page
request made the Model Performance page load extremely slowly and re-did
identical work on every visit. Evaluation now executes once per explicit
trigger, persists its numbers in EvaluationRun, and the page renders the
stored results instantly.

How a run executes (important for local runs)
---------------------------------------------
- An administrator triggers a run (POST /model-performance/run/). An
  EvaluationRun row is created first with status='queued', then a daemon
  thread inside the current process executes the pipeline.
- All progress lives in the database row (status, stage, heartbeat_at), so
  refreshing the page or opening it in another tab still shows progress —
  nothing depends on the browser session.
- Heartbeats are written at every stage boundary. If the process dies
  (Ctrl+C, dev-server reload, machine sleep), heartbeats stop and the next
  status read marks the run 'interrupted' with guidance to re-run it — it
  never silently disappears and it never blocks future runs.
- Single-flight: only one run may be queued/running at a time; stale runs
  are marked interrupted before a new one is accepted.
- The job lives in the process that serves `python manage.py runserver`;
  stopping the server interrupts the run (recoverable as above). This fits
  the local development setup and adds no infrastructure. A production or
  multi-process deployment should replace the thread with a task queue
  (e.g. Celery): create the EvaluationRun the same way and call
  `execute_evaluation(run_id)` from the worker — the view, status endpoint,
  and stored schema stay unchanged.
- The runner closes its database connections when it finishes.

Evaluation semantics are unchanged from the original inline computation:
synthetic anomalies are injected with random_state=42 at a 5% fraction,
both detectors use contamination=0.05 (LOF with n_neighbors=20), and the
sensitivity sweep tests contamination 0.01/0.03/0.05/0.10.
"""

import logging
import threading

from django.db import connections
from django.utils import timezone

from .models import EvaluationRun

logger = logging.getLogger(__name__)

STALE_AFTER_SECONDS = 180

DEFAULT_CONFIG = {
    'anomaly_fraction': 0.05,
    'contamination': 0.05,
    'n_neighbors': 20,
    'random_state': 42,
    'sensitivity_values': [0.01, 0.03, 0.05, 0.1],
}


class EvaluationAlreadyRunning(Exception):
    """Raised when a run is triggered while another run is still active."""


def default_config():
    import copy
    return copy.deepcopy(DEFAULT_CONFIG)


def latest_run():
    return EvaluationRun.objects.order_by('-created_at').first()


def latest_completed_run():
    return (
        EvaluationRun.objects
        .filter(status=EvaluationRun.STATUS_SUCCEEDED)
        .order_by('-finished_at')
        .first()
    )


def interrupt_stale_runs():
    """Mark active runs with dead heartbeats as interrupted (recoverable)."""
    now = timezone.now()
    for run in EvaluationRun.objects.filter(
        status__in=[EvaluationRun.STATUS_QUEUED, EvaluationRun.STATUS_RUNNING]
    ):
        reference = run.heartbeat_at or run.started_at or run.updated_at
        age = (now - reference).total_seconds() if reference else None
        if age is None or age > STALE_AFTER_SECONDS:
            run.status = EvaluationRun.STATUS_INTERRUPTED
            run.stage = 'Interrupted (process stopped unexpectedly)'
            run.finished_at = now
            run.save()


def run_status(run):
    """Serializable status for the status endpoint / page context."""
    if run is None:
        return {'status': 'none', 'stage': '', 'error': ''}

    status = run.status
    interrupted = False
    if status in (EvaluationRun.STATUS_QUEUED, EvaluationRun.STATUS_RUNNING):
        reference = run.heartbeat_at or run.started_at or run.updated_at
        age = (timezone.now() - reference).total_seconds() if reference else None
        if age is None or age > STALE_AFTER_SECONDS:
            status = EvaluationRun.STATUS_INTERRUPTED
            interrupted = True

    return {
        'run_id': run.run_id,
        'status': status,
        'stage': run.stage,
        'error': run.error,
        'interrupted': interrupted,
        'duration_seconds': run.duration_seconds,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
    }


def start_evaluation_run(user=None):
    """Queue a new evaluation run and start it in a background thread."""
    interrupt_stale_runs()
    if EvaluationRun.objects.filter(
        status__in=[EvaluationRun.STATUS_QUEUED, EvaluationRun.STATUS_RUNNING]
    ).exists():
        raise EvaluationAlreadyRunning('An evaluation run is already in progress.')

    run = EvaluationRun.objects.create(
        status=EvaluationRun.STATUS_QUEUED,
        stage='Queued',
        config=default_config(),
        triggered_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    thread = threading.Thread(
        target=execute_evaluation,
        args=(run.run_id,),
        daemon=True,
        name=f'evaluation-run-{run.run_id}',
    )
    thread.start()
    return run


def _set_stage(run, stage):
    run.stage = stage
    run.heartbeat_at = timezone.now()
    run.save()


def execute_evaluation(run_id):
    """Run the full evaluation pipeline and persist results on the row."""
    try:
        run = EvaluationRun.objects.get(pk=run_id)
    except EvaluationRun.DoesNotExist:
        logger.error('Evaluation run %s not found', run_id)
        return

    try:
        from .trainer import FEATURE_COLUMNS, load_feature_matrix, run_sensitivity_analysis
        from .evaluator import precision_recall_f1
        from .synthetic import inject_synthetic_anomalies
        from .isolation_forest import IsolationForestDetector
        from .local_outlier import LOFDetector

        run.status = EvaluationRun.STATUS_RUNNING
        run.started_at = timezone.now()
        run.error = ''
        _set_stage(run, 'Loading feature matrix')

        X, _contract_ids = load_feature_matrix()
        if X.empty:
            raise RuntimeError(
                'No feature data available. Run "python manage.py generate_features" first.'
            )

        config = dict(run.config or default_config())
        config['n_samples'] = int(len(X))
        config['n_features'] = int(X.shape[1])
        run.config = config
        run.save()

        eval_results = {}

        _set_stage(run, 'Injecting synthetic anomalies (5%)')
        X_float = X.copy().astype(float)
        X_synth_raw, synth_labels = inject_synthetic_anomalies(
            X_float, anomaly_fraction=config.get('anomaly_fraction', 0.05)
        )
        synth_feature_cols = [c for c in FEATURE_COLUMNS if c in X_synth_raw.columns]
        X_synth = X_synth_raw[synth_feature_cols].fillna(0)

        _set_stage(run, 'Training Isolation Forest (synthetic evaluation)')
        if_detector = IsolationForestDetector(
            contamination=config.get('contamination', 0.05)
        )
        if_detector.fit(X_synth)
        if_preds = if_detector.predict(X_synth)
        if_binary = (if_preds == -1).astype(int)
        eval_results['if_synth'] = precision_recall_f1(synth_labels, if_binary)

        _set_stage(run, 'Training Local Outlier Factor (synthetic evaluation)')
        lof_detector = LOFDetector(
            contamination=config.get('contamination', 0.05),
            n_neighbors=config.get('n_neighbors', 20),
        )
        lof_detector.fit(X_synth)
        lof_preds = lof_detector.predict(X_synth)
        lof_binary = (lof_preds == -1).astype(int)
        eval_results['lof_synth'] = precision_recall_f1(synth_labels, lof_binary)

        _set_stage(run, 'Running contamination sensitivity analysis')
        sensitivity_results = run_sensitivity_analysis(
            config.get('sensitivity_values', [0.01, 0.03, 0.05, 0.1])
        )
        sensitivity = {
            str(c): {
                'n_anomalies': r.get('n_anomalies', 0),
                'n_samples': r.get('n_samples', config['n_samples']),
            }
            for c, r in sensitivity_results.items()
        }

        _set_stage(run, 'Saving results')
        finished = timezone.now()
        run.status = EvaluationRun.STATUS_SUCCEEDED
        run.synthetic_results = eval_results
        run.sensitivity_results = sensitivity
        run.error = ''
        run.finished_at = finished
        run.heartbeat_at = finished
        run.stage = 'Completed'
        if run.started_at:
            run.duration_seconds = (finished - run.started_at).total_seconds()
        run.save()
        logger.info('Evaluation run %s completed in %.1fs', run_id, run.duration_seconds or 0)
    except Exception as exc:
        logger.exception('Evaluation run %s failed', run_id)
        run.status = EvaluationRun.STATUS_FAILED
        run.error = str(exc) or type(exc).__name__
        run.finished_at = timezone.now()
        run.heartbeat_at = run.finished_at
        run.stage = 'Failed'
        if run.started_at:
            run.duration_seconds = (run.finished_at - run.started_at).total_seconds()
        run.save()
    finally:
        connections.close_all()
