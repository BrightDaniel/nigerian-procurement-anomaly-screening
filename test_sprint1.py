"""
End-to-end test script for Sprint 1 deliverables.
Run: python test_sprint1.py
"""
import os
import sys
import json

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'

import django
django.setup()

from django.db import connection
from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from django.contrib import admin
from django.urls import reverse, resolve

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

print('=' * 60)
print('SPRINT 1 END-TO-END TESTS')
print('=' * 60)

# ── 1. Database ──
print('\n[1] DATABASE')

def test_tables():
    cursor = connection.cursor()
    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    required = {
        'users', 'procuring_entities', 'vendors', 'contracts',
        'features', 'anomaly_flags', 'raw_records', 'explanations',
        'django_migrations', 'django_content_type', 'auth_permission',
        'auth_group', 'auth_group_permissions',
        'django_admin_log', 'django_session',
    }
    missing = required - tables
    if missing:
        raise AssertionError(f'Missing tables: {missing}')
test('All required tables exist', test_tables)

def test_user_columns():
    cursor = connection.cursor()
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position")
    cols = {row[0] for row in cursor.fetchall()}
    required = {'id', 'username', 'password', 'email', 'role', 'is_active', 'is_staff', 'is_superuser'}
    missing = required - cols
    if missing:
        raise AssertionError(f'Missing user columns: {missing}')
test('User model has correct columns', test_user_columns)

def test_contracts_columns():
    cursor = connection.cursor()
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'contracts'")
    cols = {row[0] for row in cursor.fetchall()}
    required = {'contract_id', 'entity_id', 'vendor_id', 'title', 'amount', 'currency', 'award_date', 'nocopo_id'}
    missing = required - cols
    if missing:
        raise AssertionError(f'Missing contract columns: {missing}')
test('Contract model has correct columns', test_contracts_columns)

# ── 2. Authentication ──
print('\n[2] AUTHENTICATION')

User = get_user_model()

def test_superuser_exists():
    u = User.objects.get(username='admin')
    if not u.is_superuser:
        raise AssertionError('admin is not superuser')
    if not u.is_administrator:
        raise AssertionError('admin role is not ADMINISTRATOR')
test('Superuser exists with Administrator role', test_superuser_exists)

def test_create_auditor():
    u = User.objects.create_user(
        username='test_auditor', password='test1234',
        email='auditor@test.com', role='AUDITOR'
    )
    if not u.is_auditor:
        raise AssertionError('Role not set to AUDITOR')
    if u.is_administrator:
        raise AssertionError('Auditor should not be administrator')
    u.delete()
test('Create Auditor user with correct role', test_create_auditor)

def test_login_view():
    client = django.test.Client()
    resp = client.get('/accounts/login/')
    if resp.status_code != 200:
        raise AssertionError(f'Login page returned {resp.status_code}')
    if b'Login' not in resp.content and b'Sign In' not in resp.content:
        raise AssertionError('Login page missing "Login" or "Sign In" text')
test('Login page renders (200)', test_login_view)

def test_register_removed():
    client = django.test.Client()
    resp = client.get('/accounts/register/')
    if resp.status_code != 404:
        raise AssertionError(f'Register page returned {resp.status_code}, expected 404 (removed)')
test('Public registration removed (404)', test_register_removed)

def test_login_post():
    client = django.test.Client()
    resp = client.post('/accounts/login/', {
        'username': 'admin', 'password': 'admin123'
    }, follow=True)
    if resp.status_code != 200:
        raise AssertionError(f'Login POST returned {resp.status_code}')
test('Login POST with valid credentials succeeds', test_login_post)

def test_profile_view():
    client = django.test.Client()
    client.login(username='admin', password='admin123')
    resp = client.get('/accounts/profile/')
    if resp.status_code != 200:
        raise AssertionError(f'Profile returned {resp.status_code}')
test('Profile page renders when logged in', test_profile_view)

def test_logout():
    client = django.test.Client()
    client.login(username='admin', password='admin123')
    resp = client.get('/accounts/logout/', follow=True)
    if resp.status_code != 200:
        raise AssertionError(f'Logout returned {resp.status_code}')
test('Logout works', test_logout)

# ── 3. Dashboard ──
print('\n[3] DASHBOARD PAGES')

def test_index():
    client = django.test.Client()
    client.login(username='admin', password='admin123')
    resp = client.get('/')
    if resp.status_code != 200:
        raise AssertionError(f'Index returned {resp.status_code}')
    if b'Procurement Intelligence' not in resp.content:
        raise AssertionError('Missing project title in page')
test('Dashboard index renders', test_index)

def test_anomalies():
    client = django.test.Client()
    client.login(username='admin', password='admin123')
    resp = client.get('/anomalies/')
    if resp.status_code != 200:
        raise AssertionError(f'Anomalies returned {resp.status_code}')
    if b'Anomaly Queue' not in resp.content:
        raise AssertionError('Missing "Anomaly Queue" heading')
test('Anomalies list page renders', test_anomalies)

def test_anomaly_detail():
    client = django.test.Client()
    client.login(username='admin', password='admin123')
    resp = client.get('/anomalies/1/')
    if resp.status_code not in (200, 404):
        raise AssertionError(f'Anomaly detail returned {resp.status_code}')
test('Anomaly detail page renders (200 or 404 if no data)', test_anomaly_detail)

def test_import_page():
    client = django.test.Client()
    client.login(username='admin', password='admin123')
    resp = client.get('/ingestion/import/')
    if resp.status_code != 200:
        raise AssertionError(f'Import page returned {resp.status_code}')
    if b'Import Data' not in resp.content:
        raise AssertionError('Missing "Import Data" heading')
test('Import data page renders', test_import_page)

# ── 4. Role Permissions ──
print('\n[4] ROLE PERMISSIONS')

def test_auditor_cannot_import():
    from apps.accounts.models import User
    uname = 'test_auditor_perm_' + str(os.getpid())
    User.objects.filter(username=uname).delete()
    User.objects.create_user(username=uname, password='test1234', role='AUDITOR')
    client = django.test.Client()
    client.login(username=uname, password='test1234')
    resp = client.get('/ingestion/import/')
    if resp.status_code != 302:
        raise AssertionError(f'Auditor got {resp.status_code}, expected 302 redirect')
    User.objects.filter(username=uname).delete()
test('Auditor cannot access import page (302 redirect)', test_auditor_cannot_import)

def test_auditor_cannot_access_admin_users():
    from apps.accounts.models import User
    uname = 'test_auditor_admin_' + str(os.getpid())
    User.objects.filter(username=uname).delete()
    User.objects.create_user(username=uname, password='test1234', role='AUDITOR')
    client = django.test.Client()
    client.login(username=uname, password='test1234')
    resp = client.get('/system/users/')
    if resp.status_code != 302:
        raise AssertionError(f'Auditor got {resp.status_code} for admin users, expected 302')
    resp = client.get('/system/settings/')
    if resp.status_code != 302:
        raise AssertionError(f'Auditor got {resp.status_code} for admin settings, expected 302')
    User.objects.filter(username=uname).delete()
test('Auditor cannot access admin pages (302 redirect)', test_auditor_cannot_access_admin_users)

def test_admin_can_access_admin_pages():
    client = django.test.Client()
    client.login(username='admin', password='admin123')
    resp = client.get('/system/users/')
    if resp.status_code != 200:
        raise AssertionError(f'Admin got {resp.status_code} for admin users, expected 200')
    resp = client.get('/system/settings/')
    if resp.status_code != 200:
        raise AssertionError(f'Admin got {resp.status_code} for admin settings, expected 200')
test('Admin can access admin pages (200)', test_admin_can_access_admin_pages)

def test_unauthenticated_redirected():
    client = django.test.Client()
    resp = client.get('/')
    if resp.status_code != 302:
        raise AssertionError(f'Unauthenticated got {resp.status_code} for dashboard, expected 302')
    resp = client.get('/system/users/')
    if resp.status_code != 302:
        raise AssertionError(f'Unauthenticated got {resp.status_code} for admin users, expected 302')
test('Unauthenticated users redirected to login (302)', test_unauthenticated_redirected)

# ── 5. Models ──
print('\n[5] MODELS')

def test_procuring_entity():
    from apps.ingestion.models import ProcuringEntity
    e = ProcuringEntity.objects.create(name='Test MDA', type='Ministry', state='Lagos')
    if str(e) != 'Test MDA':
        raise AssertionError(f'str() returned {str(e)}')
    e.delete()
test('ProcuringEntity create and __str__', test_procuring_entity)

def test_vendor():
    from apps.ingestion.models import Vendor
    v = Vendor.objects.create(name='Test Vendor', cac_number='CAC123', state='Abuja')
    if str(v) != 'Test Vendor':
        raise AssertionError(f'str() returned {str(v)}')
    v.delete()
test('Vendor create and __str__', test_vendor)

def test_raw_record():
    from apps.ingestion.models import RawRecord
    r = RawRecord.objects.create(source_file='test.csv', ocds_release={'awards': [{'id': 'test-123'}]})
    if not r.is_validated == False:
        raise AssertionError('is_validated should default to False')
    if not r.is_imported == False:
        raise AssertionError('is_imported should default to False')
    r.delete()
test('RawRecord defaults (is_validated=False, is_imported=False)', test_raw_record)

def test_feature_model():
    from apps.features.models import Feature
    from apps.ingestion.models import Contract
    c = Contract.objects.create(title='Test Contract', amount=1000000, nocopo_id='test-feature-1')
    f = Feature.objects.create(contract=c, price_deviation=1.5, single_bidder_flag=True)
    if not f.single_bidder_flag:
        raise AssertionError('single_bidder_flag not set')
    f.delete()
    c.delete()
test('Feature model create with fields', test_feature_model)

def test_anomaly_flag_model():
    from apps.detection.models import AnomalyFlag
    from apps.ingestion.models import Contract
    c = Contract.objects.create(title='Test Anomaly', amount=500000, nocopo_id='test-anomaly-1')
    a = AnomalyFlag.objects.create(contract=c, risk_score=0.95, model_used='IsolationForest', is_anomaly=True)
    if float(a.risk_score) != 0.95:
        raise AssertionError(f'risk_score is {a.risk_score}')
    a.delete()
    c.delete()
test('AnomalyFlag model create with fields', test_anomaly_flag_model)

# ── 6. Preprocessing ──
print('\n[6] PREPROCESSING')

def test_quality_report():
    import pandas as pd
    import numpy as np
    from apps.preprocessing.quality_report import generate_quality_report, format_quality_report
    df = pd.DataFrame({
        'amount': [1000, 2000, 3000],
        'method': ['open', 'selective', None],
        'category': ['goods', 'services', 'works'],
        'award_date': ['1949-01-01', '2021-06-15', '2919-03-20'],
        'nocopo_id': ['id-1', 'id-2', 'id-3'],
    })
    report = generate_quality_report(df)
    if report['total_records'] != 3:
        raise AssertionError(f'total_records is {report["total_records"]}')
    if len(report['issues']) == 0:
        raise AssertionError('Expected at least one issue flagged (outlier years)')
    text = format_quality_report(report)
    if 'DATA QUALITY REPORT' not in text:
        raise AssertionError('Report format missing header')
test('Quality report flags known dataset issues', test_quality_report)

def test_cleaners():
    import pandas as pd
    from apps.preprocessing.cleaners import clean_award_dates, handle_missing_values
    df = pd.DataFrame({
        'amount': [1000, None, 3000],
        'method': ['open', None, 'selective'],
        'currency': ['NGN', None, 'NGN'],
        'title': ['A', None, 'C'],
        'entity_name': ['E1', None, 'E3'],
        'vendor_name': ['V1', None, 'V3'],
        'award_date': ['1949-01-01', '2021-06-15', '2919-03-20'],
    })
    df = clean_award_dates(df)
    df = handle_missing_values(df)
    # Outlier years should be NaT
    if pd.notna(df['award_date'].iloc[0]):
        raise AssertionError('1949 date not cleaned')
    # Missing amount should be filled
    if pd.isna(df['amount'].iloc[1]):
        raise AssertionError('Missing amount not filled')
    # Missing method should be filled
    if pd.isna(df['method'].iloc[1]):
        raise AssertionError('Missing method not filled')
test('Cleaners handle outlier dates and missing values', test_cleaners)

# ── 7. Feature Registry ──
print('\n[7] FEATURE REGISTRY')

def test_registry():
    from apps.features.registry import FEATURE_REGISTRY
    required = {
        'log_contract_value', 'single_bidder_flag',
        'vendor_win_frequency', 'vendor_win_concentration',
        'price_deviation', 'splitting_flag', 'splitting_count',
    }
    missing = required - set(FEATURE_REGISTRY.keys())
    if missing:
        raise AssertionError(f'Missing features: {missing}')
    for name, spec in FEATURE_REGISTRY.items():
        if 'category' not in spec:
            raise AssertionError(f'{name} missing category')
        if 'computation' not in spec:
            raise AssertionError(f'{name} missing computation')
test('Feature registry has all required features', test_registry)

# ── 8. Management Commands ──
print('\n[8] MANAGEMENT COMMANDS')

def test_import_data_cmd():
    from django.core.management import get_commands
    cmds = get_commands()
    if 'import_data' not in cmds:
        raise AssertionError('import_data command not found')
test('import_data management command registered', test_import_data_cmd)

# ── 9. URL Routes ──
print('\n[9] URL ROUTES')

def test_url_patterns():
    from django.urls import reverse
    urls = [
        ('dashboard:index', {}),
        ('dashboard:anomalies', {}),
        ('dashboard:anomaly_detail', {'contract_id': 1}),
        ('dashboard:records', {}),
        ('accounts:login', {}),
        ('accounts:logout', {}),
        ('accounts:profile', {}),
        ('ingestion:import_data', {}),
        ('reporting:report_list', {}),
        ('reporting:report_detail', {'contract_id': 1}),
        ('analytics_runs', {}),
        ('analytics_performance', {}),
        ('admin_users', {}),
        ('admin_user_create', {}),
        ('admin_settings', {}),
    ]
    for name, kwargs in urls:
        try:
            url = reverse(name, kwargs=kwargs)
        except Exception as e:
            raise AssertionError(f'URL {name} failed: {e}')
test('All URL patterns resolve correctly', test_url_patterns)

# ── 10. Templates ──
print('\n[10] TEMPLATES')

def test_base_template():
    from django.template.loader import get_template
    t = get_template('base.html')
    if not t:
        raise AssertionError('base.html not found')
test('base.html template loads', test_base_template)

def test_dashboard_templates():
    from django.template.loader import get_template
    templates = [
        'dashboard/index.html',
        'dashboard/anomalies.html',
        'dashboard/anomaly_detail.html',
        'dashboard/records.html',
        'dashboard/analysis_runs.html',
        'dashboard/model_performance.html',
        'dashboard/record_detail.html',
        'accounts/login.html',
        'accounts/profile.html',
        'accounts/user_list.html',
        'accounts/user_edit.html',
        'accounts/user_create.html',
        'accounts/settings.html',
        'reports/report_list.html',
        'reports/investigation_report.html',
    ]
    for tmpl in templates:
        t = get_template(tmpl)
        if not t:
            raise AssertionError(f'{tmpl} not found')
test('All app templates load', test_dashboard_templates)

# ── Summary ──
print('\n' + '=' * 60)
print(f'RESULTS: {len(passed)} passed, {len(errors)} failed')
print('=' * 60)

if errors:
    print('\nFAILED TESTS:')
    for name, err in errors:
        print(f'  FAIL  {name}: {err}')
    sys.exit(1)
else:
    print('\nAll tests passed!')
    sys.exit(0)
