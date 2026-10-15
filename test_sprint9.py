"""
Regression tests for the six-issue bug-fix / UX sprint.
Run: python test_sprint9.py

Covers:
- Issue 1: import staging dedup, honest validation/contract stats, savepoint
  isolation, background ImportJob lifecycle (start, single-flight, stale
  interrupt), status endpoint authz, Import results summary rendering
- Issue 2: Anomaly Queue search by contract id / title / entity / vendor
- Issue 3: Reports list (unique rows), report detail, record detail
- Issue 4: Model Performance renders persisted evaluation results quickly,
  status endpoint, role checks, priority scheme documentation
- Issue 5: sign-in card controls (password toggle, submit loading state)
- Issue 6: responsive structure (table wrappers, stat/chart grids,
  pagination wrapping, no global overflow-x hidden)
- Data integrity: live dataset counts unchanged after all fixture work

All fixtures are prefixed with __TEST and removed afterwards. No real
dataset is imported, no evaluation is re-run, no credentials are changed.
"""
import os
import re
import sys
import csv
import shutil
import tempfile
import time
from pathlib import Path

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone

from apps.ingestion.models import Contract, RawRecord, ProcuringEntity, Vendor, ImportJob
from apps.detection.models import AnomalyFlag, EvaluationRun
from apps.explainability.models import Explanation
from apps.features.models import Feature

User = get_user_model()

errors = []
passed = []


def test(name, func):
    try:
        func()
        passed.append(name)
        print(f'  PASS  {name}')
    except Exception as e:
        errors.append((name, str(e)))
        print(f'  FAIL  {name}: {e}')


def fixture_raws():
    return RawRecord.objects.annotate(
        aid=KeyTextTransform('awards/id', 'ocds_release')
    ).filter(aid__startswith='__TEST')


def fixture_contracts():
    return Contract.objects.filter(nocopo_id__startswith='__TEST')


def cleanup_fixtures():
    fixture_contracts().delete()
    fixture_raws().delete()
    ProcuringEntity.objects.filter(name__startswith='__TEST').delete()


# Remove leftovers from any previous interrupted run before snapshotting.
cleanup_fixtures()
ImportJob.objects.all().delete()

BASE = {}
T_START = timezone.now()


def capture_baseline():
    BASE['contracts'] = Contract.objects.count()
    BASE['raw_records'] = RawRecord.objects.count()
    BASE['entities'] = ProcuringEntity.objects.count()
    BASE['vendors'] = Vendor.objects.count()
    BASE['flags'] = AnomalyFlag.objects.count()
    BASE['explanations'] = Explanation.objects.count()
    BASE['features'] = Feature.objects.count()
    BASE['users'] = User.objects.count()


capture_baseline()

admin_client = Client()
admin_client.login(username='admin', password='admin123')

print('=' * 60)
print('SPRINT 9 REGRESSION TESTS (six-issue bug-fix / UX)')
print('=' * 60)

# ── Issue 2: Anomaly Queue search ──
print('\n[Issue 2] ANOMALY QUEUE SEARCH')


def _flagged(with_vendor=False):
    qs = AnomalyFlag.objects.filter(is_anomaly=True).select_related(
        'contract', 'contract__entity', 'contract__vendor'
    )
    if with_vendor:
        qs = qs.filter(contract__vendor__isnull=False)
    return qs.first()


def test_search_by_contract_id():
    flag = _flagged()
    r = admin_client.get('/anomalies/', {'search': str(flag.contract.contract_id)})
    if r.status_code != 200:
        raise AssertionError(f'search by contract id returned {r.status_code}')
    if str(flag.contract.contract_id) not in r.content.decode():
        raise AssertionError('contract id not present in search results')


test('Anomaly search by contract id returns 200 with results', test_search_by_contract_id)


def test_search_by_title():
    flag = _flagged()
    fragment = flag.contract.title[:15]
    r = admin_client.get('/anomalies/', {'search': fragment})
    if r.status_code != 200:
        raise AssertionError(f'search by title returned {r.status_code}')


test('Anomaly search by title fragment returns 200', test_search_by_title)


def test_search_by_entity():
    flag = _flagged()
    entity = flag.contract.entity
    r = admin_client.get('/anomalies/', {'search': entity.name})
    if r.status_code != 200:
        raise AssertionError(f'search by entity returned {r.status_code}')
    html = r.content.decode()
    if 'No Anomalies Found' in html:
        raise AssertionError('entity search matched no rows')
    m = re.search(r'page-count">\(?(\d+)\)?</span>', html)
    if not m:
        raise AssertionError('no result count rendered')
    expected = AnomalyFlag.objects.filter(
        is_anomaly=True, contract__entity_id=entity.entity_id
    ).count()
    if int(m.group(1)) < expected:
        raise AssertionError(
            f'entity search count {m.group(1)} < expected {expected}'
        )


test('Anomaly search by entity name returns matching rows', test_search_by_entity)


def test_search_by_vendor():
    flag = _flagged(with_vendor=True)
    name = flag.contract.vendor.name
    r = admin_client.get('/anomalies/', {'search': name})
    if r.status_code != 200:
        raise AssertionError(f'search by vendor returned {r.status_code}')


test('Anomaly search by vendor name returns 200', test_search_by_vendor)


def test_search_no_match():
    r = admin_client.get('/anomalies/', {'search': 'zzz-no-match-zzz'})
    if r.status_code != 200:
        raise AssertionError(f'no-match search returned {r.status_code}')


test('Anomaly search with no matches returns 200 (empty state)', test_search_no_match)


def test_anomaly_priority_filters():
    for p in ('high', 'medium', 'normal'):
        r = admin_client.get('/anomalies/', {'priority': p})
        if r.status_code != 200:
            raise AssertionError(f'priority={p} returned {r.status_code}')


test('Anomaly priority filters return 200', test_anomaly_priority_filters)

# ── Issue 3: Reports + detail pages ──
print('\n[Issue 3] REPORTS AND DETAIL PAGES')


def test_reports_list():
    r = admin_client.get('/reports/')
    if r.status_code != 200:
        raise AssertionError(f'/reports/ returned {r.status_code}')
    html = r.content.decode()
    ids = re.findall(r'href="/reports/(\d+)/"', html)
    if not ids:
        raise AssertionError('reports list rendered no rows')
    if len(ids) != len(set(ids)):
        raise AssertionError(f'reports list has duplicate contract rows: {ids}')
    n_flagged = AnomalyFlag.objects.filter(is_anomaly=True).values(
        'contract_id'
    ).distinct().count()
    if len(set(ids)) > n_flagged:
        raise AssertionError('more rows than flagged contracts')


test('Reports list renders unique flagged-contract rows', test_reports_list)


def test_reports_filters():
    for params in ({'priority': 'high'}, {'priority': 'medium'}, {'search': 'Cons'}):
        r = admin_client.get('/reports/', params)
        if r.status_code != 200:
            raise AssertionError(f'/reports/ with {params} returned {r.status_code}')


test('Reports priority and search filters return 200', test_reports_filters)


def test_report_detail():
    contract = Contract.objects.filter(anomaly_flags__is_anomaly=True).first()
    r = admin_client.get(f'/reports/{contract.contract_id}/')
    if r.status_code != 200:
        raise AssertionError(f'report detail returned {r.status_code}')


test('Report detail renders (no MultipleObjectsReturned)', test_report_detail)


def test_record_detail_flagged():
    contract = Contract.objects.filter(anomaly_flags__is_anomaly=True).first()
    r = admin_client.get(f'/records/{contract.contract_id}/')
    if r.status_code != 200:
        raise AssertionError(f'record detail returned {r.status_code}')


test('Record detail renders for flagged contract', test_record_detail_flagged)


def test_record_detail_unflagged():
    flagged = set(
        AnomalyFlag.objects.filter(is_anomaly=True).values_list('contract_id', flat=True)
    )
    with_flags = set(AnomalyFlag.objects.values_list('contract_id', flat=True))
    candidates = list(with_flags - flagged)
    if not candidates:
        raise AssertionError('no contract with only non-anomalous flags found')
    last_status = None
    for cid in candidates[:50]:
        r = admin_client.get(f'/records/{cid}/')
        last_status = r.status_code
        if r.status_code == 200:
            return
    raise AssertionError(f'unflagged record detail returned {last_status}')


test('Record detail renders for unflagged contract', test_record_detail_unflagged)


def test_anomaly_detail():
    flag = _flagged()
    r = admin_client.get(f'/anomalies/{flag.contract_id}/')
    if r.status_code != 200:
        raise AssertionError(f'anomaly detail returned {r.status_code}')


test('Anomaly detail still renders', test_anomaly_detail)

# ── Issue 4: Model Performance ──
print('\n[Issue 4] MODEL PERFORMANCE (persisted evaluation)')


def test_performance_fast_and_rendered():
    t0 = time.time()
    r = admin_client.get('/analytics/performance/')
    elapsed = time.time() - t0
    if r.status_code != 200:
        raise AssertionError(f'performance page returned {r.status_code}')
    if elapsed > 5.0:
        raise AssertionError(
            f'performance page took {elapsed:.1f}s (eval must not run inline)'
        )
    html = r.content.decode()
    for needle in (
        'Synthetic Anomaly Evaluation',
        'Contamination Sensitivity',
        '0.1659',
        '0.0841',
        'Priority bands (applied uniformly',
        'Evaluation results from',
    ):
        if needle not in html:
            raise AssertionError(f'missing on performance page: {needle}')


test('Model Performance renders persisted results in <5s', test_performance_fast_and_rendered)


def test_performance_status_endpoint():
    r = admin_client.get('/model-performance/status/')
    if r.status_code != 200:
        raise AssertionError(f'status endpoint returned {r.status_code}')
    data = r.json()
    if data['status'] != 'succeeded':
        raise AssertionError(f'expected succeeded evaluation, got {data["status"]}')
    if not data['duration_seconds']:
        raise AssertionError('missing duration on completed run')


test('Evaluation status endpoint reports the completed run', test_performance_status_endpoint)


def test_performance_roles():
    html = admin_client.get('/analytics/performance/').content.decode()
    if 'eval-start-btn' not in html:
        raise AssertionError('administrator does not see Run Evaluation button')

    from apps.accounts.models import User as AccountsUser
    auditor = AccountsUser.objects.filter(username='test_auditor_perm_13700').first()
    if auditor is None:
        raise AssertionError('auditor fixture account missing')
    c = Client()
    if not c.login(username=auditor.username, password='test1234'):
        raise AssertionError('auditor login failed')
    r = c.get('/analytics/performance/')
    if r.status_code != 200:
        raise AssertionError(f'auditor GET performance returned {r.status_code}')
    if 'eval-start-btn' in r.content.decode():
        raise AssertionError('auditor sees Run Evaluation button')
    r = c.post('/model-performance/run/')
    if r.status_code != 302 or r.headers.get('Location') != '/':
        raise AssertionError(
            f'auditor POST run not blocked: {r.status_code} {r.headers.get("Location")}'
        )


test('Run Evaluation is administrator-only (button + POST)', test_performance_roles)


def test_evaluation_single_flight():
    t_start = timezone.now()
    manual = EvaluationRun.objects.create(
        status=EvaluationRun.STATUS_RUNNING,
        stage='__TEST_MANUAL_ACTIVE__',
        heartbeat_at=timezone.now(),
    )
    try:
        from apps.detection.evaluation import (
            start_evaluation_run,
            EvaluationAlreadyRunning,
        )
        try:
            start_evaluation_run(None)
            raise AssertionError('second evaluation run was allowed while one active')
        except EvaluationAlreadyRunning:
            pass
    finally:
        EvaluationRun.objects.filter(created_at__gte=t_start).delete()


test('Evaluation single-flight refuses a second concurrent run', test_evaluation_single_flight)

# ── Issue 5: sign-in card ──
print('\n[Issue 5] SIGN-IN CARD CONTROLS')


def test_login_controls():
    html = Client().get('/accounts/login/').content.decode()
    for needle in (
        'id="password-toggle"',
        'id="login-submit"',
        'aria-busy',
        'class="password-field"',
        'id="login-form"',
        'name="username"',
        'name="password"',
        'csrfmiddlewaretoken',
        'type="submit"',
        'for="id_username"',
        'for="id_password"',
    ):
        if needle not in html:
            raise AssertionError(f'missing on login page: {needle}')
    if 'id="sidebar"' in html or 'js/app.js' in html:
        raise AssertionError('login page regressed to app shell')


test('Sign-in card has password toggle + stable loading submit', test_login_controls)

# ── Issue 6: responsive structure ──
print('\n[Issue 6] RESPONSIVE / HORIZONTAL SCROLL STRUCTURE')


def test_table_wrappers():
    checks = {
        'templates/dashboard/analysis_runs.html': 1,
        'templates/dashboard/model_performance.html': 2,
    }
    root = Path(__file__).resolve().parent
    for rel, minimum in checks.items():
        text = (root / rel).read_text(encoding='utf-8')
        count = text.count('table-wrapper')
        if count < minimum:
            raise AssertionError(f'{rel}: expected >= {minimum} table-wrapper, found {count}')


test('All wide tables are inside .table-wrapper', test_table_wrappers)


def test_grid_css_defined():
    root = Path(__file__).resolve().parent
    css = (root / 'static/css/design-system.css').read_text(encoding='utf-8')
    for needle in ('.stat-grid {', '.chart-grid {', 'progress-indeterminate'):
        if needle not in css:
            raise AssertionError(f'design-system.css missing {needle}')
    if 'min-width: 0;' not in css:
        raise AssertionError('.main-content missing min-width: 0 flex-guard')
    if 'overflow-x: hidden' in css:
        raise AssertionError('global overflow-x: hidden found in design-system.css')
    custom = (root / 'static/css/custom.css').read_text(encoding='utf-8')
    if 'overflow-x: hidden' in custom:
        raise AssertionError('overflow-x: hidden found in custom.css')
    if 'text-overflow: ellipsis' not in css:
        raise AssertionError('topbar title ellipsis missing')


test('Grid/progress CSS defined; no global overflow-x hidden', test_grid_css_defined)


def test_pagination_wraps():
    root = Path(__file__).resolve().parent
    text = (root / 'templates/includes/pagination.html').read_text(encoding='utf-8')
    if text.count('flex-wrap: wrap') < 2:
        raise AssertionError('pagination does not wrap on narrow screens')


test('Pagination controls wrap on narrow screens', test_pagination_wraps)

# ── Issue 1: import pipeline ──
print('\n[Issue 1] IMPORT PIPELINE (dedup, stats, background job)')

bundle_dir = Path(tempfile.mkdtemp(prefix='sprint9_bundle_'))

with open(bundle_dir / 'main.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow([
        'ocid', 'buyer_name', 'buyer_id', 'tender_procurementMethod',
        'tender_numberOfTenderers', 'tender_tenderPeriod_durationInDays',
        'tender_procuringEntity_name',
    ])
    w.writerow([
        'ocd-t-sprint9', '__TEST ENTITY', 'T-SPRINT9', 'open', '3', '14',
        '__TEST ENTITY',
    ])

with open(bundle_dir / 'awards.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow([
        'id', 'main_ocid', 'title', 'value_amount', 'value_currency', 'date',
        'description',
    ])
    w.writerow(['__TEST_A', 'ocd-t-sprint9', '__TEST Contract A', '1000', 'NGN', '2024-01-15', 'fixture A'])
    w.writerow(['__TEST_B', 'ocd-t-sprint9', '__TEST Contract B', '2000', 'NGN', '2024-01-16', 'fixture B'])
    w.writerow(['__TEST_C', 'ocd-t-sprint9', '__TEST Contract C', '0', 'NGN', '2024-01-17', 'fixture C'])
    w.writerow(['__TEST_OV', 'ocd-t-sprint9', '__TEST Contract OV', '1e999', 'NGN', '2024-01-18', 'fixture OV'])
    w.writerow(['', 'ocd-t-sprint9', '__TEST Contract NoId', '500', 'NGN', '2024-01-19', 'no id'])
    w.writerow(['__TEST_A', 'ocd-t-sprint9', '__TEST Contract A', '1000', 'NGN', '2024-01-15', 'dup row'])


def test_staging_dedup():
    from apps.ingestion.services.csv_importer import import_csv_to_raw
    s1 = import_csv_to_raw(bundle_dir)
    expected = {'rows_seen': 6, 'staged': 4, 'duplicates': 1, 'missing_id': 1, 'failed': 0}
    for k, v in expected.items():
        if s1[k] != v:
            raise AssertionError(f'run 1 {k}: expected {v}, got {s1[k]}')
    if s1['rows_seen'] != s1['staged'] + s1['duplicates'] + s1['missing_id'] + s1['failed']:
        raise AssertionError('run 1 staging arithmetic does not add up')

    s2 = import_csv_to_raw(bundle_dir)
    expected2 = {'rows_seen': 6, 'staged': 0, 'duplicates': 5, 'missing_id': 1, 'failed': 0}
    for k, v in expected2.items():
        if s2[k] != v:
            raise AssertionError(f'run 2 {k}: expected {v}, got {s2[k]}')
    if fixture_raws().count() != 4:
        raise AssertionError(f'expected 4 staged fixture rows, got {fixture_raws().count()}')


test('Staging dedup: re-import stages nothing (flat award-id lookup)', test_staging_dedup)


def test_validation_stats_and_savepoint():
    from apps.ingestion.services.csv_importer import validate_and_import_records
    ids = list(fixture_raws().values_list('raw_id', flat=True))
    if len(ids) != 4:
        raise AssertionError(f'expected 4 fixture raws, got {len(ids)}')
    s = validate_and_import_records(raw_ids=ids)
    if s['rows_checked'] != 4:
        raise AssertionError(f'rows_checked expected 4 (fixture only), got {s["rows_checked"]}')
    if s['valid'] != 3 or s['invalid'] != 1:
        raise AssertionError(f'valid/invalid expected 3/1, got {s["valid"]}/{s["invalid"]}')
    if s['contracts_created'] != 2:
        raise AssertionError(f'contracts_created expected 2, got {s["contracts_created"]}')
    if s['import_failed'] != 1:
        raise AssertionError(f'import_failed expected 1 (overflow amount), got {s["import_failed"]}')
    if s['contracts_created'] + s['contracts_existing'] + s['import_failed'] != s['valid']:
        raise AssertionError('created + existing + failed != valid')
    if fixture_contracts().count() != 2:
        raise AssertionError(f'expected 2 fixture contracts, got {fixture_contracts().count()}')


test('Validation: honest stats + per-record savepoint isolation', test_validation_stats_and_savepoint)


def test_existing_contract_counted():
    from apps.ingestion.services.csv_importer import validate_and_import_records
    target = fixture_raws().annotate(
        aid2=KeyTextTransform('awards/id', 'ocds_release')
    ).filter(aid2='__TEST_A').first()
    if target is None:
        raise AssertionError('fixture raw A missing')
    target.is_imported = False
    target.save(update_fields=['is_imported'])
    s = validate_and_import_records(raw_ids=[target.raw_id])
    if s['contracts_existing'] != 1 or s['contracts_created'] != 0:
        raise AssertionError(
            f'expected existing=1 created=0, got {s["contracts_existing"]}/{s["contracts_created"]}'
        )
    target.refresh_from_db()
    if not target.is_imported:
        raise AssertionError('existing-contract row not marked imported')


test('Duplicate nocopo counted as already present, not an error', test_existing_contract_counted)


def test_import_job_lifecycle():
    from apps.ingestion.services.import_job import start_import_job
    from apps.ingestion.models import ImportJob as IJ
    from django.contrib.auth import get_user_model as gum
    admin = gum().objects.get(username='admin')
    fixture_ids = list(fixture_raws().values_list('raw_id', flat=True))

    job = start_import_job(
        admin,
        source=IJ.SOURCE_UPLOAD,
        csv_path=str(bundle_dir),
        source_name='sprint9-fixture',
        raw_ids=fixture_ids,
    )
    deadline = time.time() + 90
    while time.time() < deadline:
        job.refresh_from_db()
        if job.status in (IJ.STATUS_SUCCEEDED, IJ.STATUS_FAILED, IJ.STATUS_INTERRUPTED):
            break
        time.sleep(0.5)
    if job.status != IJ.STATUS_SUCCEEDED:
        raise AssertionError(f'job ended as {job.status}: {job.error}')
    if job.staging is None or job.validation is None or job.totals is None:
        raise AssertionError('job missing staging/validation/totals buckets')
    if job.staging['rows_seen'] != 6 or job.staging['staged'] != 0:
        raise AssertionError(f'unexpected staging bucket: {job.staging}')
    if job.validation['rows_checked'] != 2:
        raise AssertionError(f'job processed more than fixture rows: {job.validation}')
    if job.totals['contracts'] != BASE['contracts'] + 2:
        raise AssertionError(f'total contracts {job.totals["contracts"]} != baseline+2')
    if not job.duration_seconds:
        raise AssertionError('job missing duration')


test('ImportJob runs in background, survives to persisted summary', test_import_job_lifecycle)


def test_import_single_flight_and_stale():
    from apps.ingestion.services.import_job import (
        start_import_job,
        interrupt_stale_jobs,
        ImportAlreadyRunning,
    )
    from apps.ingestion.models import ImportJob as IJ
    from django.contrib.auth import get_user_model as gum
    admin = gum().objects.get(username='admin')

    t_start = timezone.now()
    fresh = IJ.objects.create(
        status=IJ.STATUS_RUNNING, stage='__TEST_ACTIVE__', heartbeat_at=timezone.now()
    )
    try:
        try:
            start_import_job(admin, source=IJ.SOURCE_OCP)
            raise AssertionError('second import job was allowed while one active')
        except ImportAlreadyRunning:
            pass
    finally:
        fresh.delete()

    aged = IJ.objects.create(
        status=IJ.STATUS_RUNNING,
        stage='__TEST_STALE__',
        heartbeat_at=timezone.now() - timezone.timedelta(minutes=10),
        started_at=timezone.now() - timezone.timedelta(minutes=10),
    )
    try:
        interrupt_stale_jobs()
        aged.refresh_from_db()
        if aged.status != IJ.STATUS_INTERRUPTED:
            raise AssertionError(f'stale job not interrupted: {aged.status}')
    finally:
        IJ.objects.filter(created_at__gte=t_start).delete()


test('Import single-flight + stale-job interruption', test_import_single_flight_and_stale)


def test_import_page_and_status_authz():
    r = admin_client.get('/ingestion/import/')
    if r.status_code != 200:
        raise AssertionError(f'admin import page returned {r.status_code}')
    html = r.content.decode()
    for needle in ('CSV Rows Read', 'Duplicates Skipped', 'Contracts Created', 'Import Results'):
        if needle not in html:
            raise AssertionError(f'import results summary missing: {needle}')

    job = ImportJob.objects.order_by('-created_at').first()
    if job is None:
        raise AssertionError('no import job to poll')
    r = admin_client.get(f'/ingestion/import/status/{job.job_id}/')
    if r.status_code != 200:
        raise AssertionError(f'admin status endpoint returned {r.status_code}')
    if r.json()['status'] not in ('succeeded', 'failed', 'interrupted'):
        raise AssertionError(f'expected terminal status, got {r.json()["status"]}')

    from apps.accounts.models import User as AccountsUser
    auditor = AccountsUser.objects.filter(username='test_auditor_perm_13700').first()
    c = Client()
    c.login(username=auditor.username, password='test1234')
    r = c.get('/ingestion/import/')
    if r.status_code != 302:
        raise AssertionError(f'auditor import page returned {r.status_code}')
    r = c.get(f'/ingestion/import/status/{job.job_id}/')
    if r.status_code != 302:
        raise AssertionError(f'auditor status endpoint returned {r.status_code}')

    anon = Client()
    r = anon.get(f'/ingestion/import/status/{job.job_id}/')
    if r.status_code != 302:
        raise AssertionError(f'anonymous status endpoint returned {r.status_code}')


test('Import page summary + status endpoint authz', test_import_page_and_status_authz)

# ── Final integrity checks ──
print('\n[FINAL] CLEANUP AND DATA INTEGRITY')


def test_cleanup_and_counts():
    cleanup_fixtures()
    ImportJob.objects.filter(created_at__gte=T_START).delete()
    shutil.rmtree(bundle_dir, ignore_errors=True)

    current = {
        'contracts': Contract.objects.count(),
        'raw_records': RawRecord.objects.count(),
        'entities': ProcuringEntity.objects.count(),
        'vendors': Vendor.objects.count(),
        'flags': AnomalyFlag.objects.count(),
        'explanations': Explanation.objects.count(),
        'features': Feature.objects.count(),
        'users': User.objects.count(),
    }
    for k, v in BASE.items():
        if current[k] != v:
            raise AssertionError(f'{k}: baseline {v} != current {current[k]}')


test('Fixtures removed; live dataset counts unchanged', test_cleanup_and_counts)

# ── Summary ──
print('\n' + '=' * 60)
print(f'RESULTS: {len(passed)} passed, {len(errors)} failed, {len(passed) + len(errors)} total')
print('=' * 60)
if errors:
    for name, msg in errors:
        print(f'  FAILED: {name}: {msg}')
    sys.exit(1)
sys.exit(0)
