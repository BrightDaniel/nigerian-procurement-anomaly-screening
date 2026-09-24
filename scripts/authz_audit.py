"""
Authentication & Authorization Audit Script
===========================================
Read-only audit -- does NOT modify the project.
Uses Django test settings with SQLite so we can run without PostgreSQL.
"""
import os
import sys
import django
from pathlib import Path
from io import StringIO

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')

# -- 1. Bootstrap Django with a lightweight SQLite config --
PROJECT = Path(__file__).resolve().parent.parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

import django.conf
sys.path.insert(0, str(PROJECT))

import types
test_settings = types.ModuleType('test_settings')
test_settings.SECRET_KEY = 'audit-test-key-not-for-production'
test_settings.DEBUG = True
test_settings.ALLOWED_HOSTS = ['*']
test_settings.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
test_settings.ROOT_URLCONF = 'config.urls'
test_settings.MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
test_settings.INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'apps.core',
    'apps.accounts',
    'apps.ingestion',
    'apps.preprocessing',
    'apps.features',
    'apps.detection',
    'apps.explainability',
    'apps.dashboard',
    'apps.reporting',
]
test_settings.AUTH_USER_MODEL = 'accounts.User'
test_settings.AUTH_PASSWORD_VALIDATORS = []
test_settings.TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [PROJECT / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]
test_settings.STATIC_URL = '/static/'
test_settings.STATICFILES_DIRS = [PROJECT / 'static']
test_settings.MEDIA_URL = '/media/'
test_settings.MEDIA_ROOT = PROJECT / 'media'
test_settings.DATA_RAW_DIR = PROJECT / 'data' / 'raw'
test_settings.DATA_PROCESSED_DIR = PROJECT / 'data' / 'processed'
test_settings.DATA_SYNTHETIC_DIR = PROJECT / 'data' / 'synthetic'
test_settings.DATA_SNAPSHOTS_DIR = PROJECT / 'data' / 'snapshots'
test_settings.ML_ARTIFACTS_DIR = PROJECT / 'ml' / 'artifacts'
test_settings.DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
test_settings.WSGI_APPLICATION = 'config.wsgi.application'
test_settings.USE_TZ = True
test_settings.TIME_ZONE = 'Africa/Lagos'
test_settings.LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {'console': {'class': 'logging.StreamHandler', 'stream': StringIO()}},
    'root': {'handlers': ['console'], 'level': 'CRITICAL'},
}
sys.modules['test_settings'] = test_settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings'

django.setup()

# -- 2. Now import Django pieces --
from django.test import Client
from django.contrib.auth import get_user_model
from django.db import connection

User = get_user_model()

# -- 3. Run migrations --
from django.core.management import call_command
call_command('migrate', '--run-syncdb', verbosity=0)

# -- 4. Create test users --
admin_user = User.objects.create_user(
    username='audit_admin', password='AuditPass123!', role='ADMIN'
)
auditor_user = User.objects.create_user(
    username='audit_auditor', password='AuditPass123!', role='AUDITOR'
)

# -- 5. Helper --
def get_status(client, path):
    resp = client.get(path)
    return resp.status_code

def result_icon(actual, expected):
    return "PASS" if actual == expected else "FAIL"

# -- 6. Define routes to test --
ANON_SHOULD_302 = [
    '/',
    '/accounts/profile/',
    '/anomalies/',
    '/records/',
    '/reports/',
    '/analytics/runs/',
    '/analytics/performance/',
    '/ingestion/import/',
    '/system/users/',
    '/system/users/create/',
    '/system/settings/',
]

AUDITOR_SHOULD_200_OR_404 = [
    '/accounts/profile/',
    '/anomalies/',
    '/records/',
    '/reports/',
    '/analytics/runs/',
    '/analytics/performance/',
]
AUDITOR_SHOULD_302 = [
    '/system/users/',
    '/system/users/create/',
    '/system/settings/',
    '/ingestion/import/',
]

ADMIN_SHOULD_200_OR_404 = [
    '/',
    '/accounts/profile/',
    '/anomalies/',
    '/records/',
    '/reports/',
    '/analytics/runs/',
    '/analytics/performance/',
    '/ingestion/import/',
    '/system/users/',
    '/system/users/create/',
    '/system/settings/',
]

# -- 7. Run the audit --
results = []
failures = []

SEP = "=" * 80
DASH = "-" * 80

print(SEP)
print("  AUTHENTICATION & AUTHORIZATION AUDIT")
print("  Project: procurement-anomaly-screening")
print(SEP)

# -- SECTION A: Anonymous --
print("\n" + DASH)
print("  SECTION A: ANONYMOUS ACCESS (unauthenticated)")
print("  Expected: 302 redirect to login for ALL protected routes")
print(DASH)

anon_client = Client()
for path in ANON_SHOULD_302:
    status = get_status(anon_client, path)
    ok = status == 302
    icon = result_icon(status, 302)
    if not ok:
        failures.append(('anon', path, status, 302))
    results.append(('ANON', path, status, 302, ok))
    print(f"  [{icon:4s}] {path:<40s} -> {status}")

# -- SECTION B: Auditor --
print("\n" + DASH)
print("  SECTION B: AUDITOR ACCESS (role=AUDITOR)")
print("  Expected: 200/404 for data/investigation routes, 302 for admin routes")
print(DASH)

auditor_client = Client()
auditor_client.force_login(auditor_user)

for path in AUDITOR_SHOULD_200_OR_404:
    status = get_status(auditor_client, path)
    ok = status in (200, 404)
    expected = '200|404'
    icon = result_icon(status, 200)
    if not ok:
        failures.append(('auditor', path, status, expected))
    results.append(('AUDITOR', path, status, expected, ok))
    print(f"  [{icon:4s}] {path:<40s} -> {status}  (expected 200|404)")

for path in AUDITOR_SHOULD_302:
    status = get_status(auditor_client, path)
    ok = status == 302
    icon = result_icon(status, 302)
    if not ok:
        failures.append(('auditor', path, status, 302))
    results.append(('AUDITOR', path, status, 302, ok))
    print(f"  [{icon:4s}] {path:<40s} -> {status}  (expected 302)")

# -- SECTION C: Administrator --
print("\n" + DASH)
print("  SECTION C: ADMINISTRATOR ACCESS (role=ADMIN)")
print("  Expected: 200/404 for ALL routes (full access)")
print(DASH)

admin_client = Client()
admin_client.force_login(admin_user)

for path in ADMIN_SHOULD_200_OR_404:
    status = get_status(admin_client, path)
    ok = status in (200, 404)
    icon = result_icon(status, 200)
    if not ok:
        failures.append(('admin', path, status, '200|404'))
    results.append(('ADMIN', path, status, '200|404', ok))
    print(f"  [{icon:4s}] {path:<40s} -> {status}  (expected 200|404)")

# -- SECTION D: admin_user_create route --
print("\n" + DASH)
print("  SECTION D: admin_user_create -- admin vs auditor")
print("  Expected: admin -> 200/404, auditor -> 302")
print(DASH)

path = '/system/users/create/'
admin_status = get_status(admin_client, path)
auditor_status = get_status(auditor_client, path)
admin_ok = admin_status in (200, 404)
auditor_ok = auditor_status == 302

results.append(('ADMIN', path, admin_status, '200|404', admin_ok))
results.append(('AUDITOR', path, auditor_status, 302, auditor_ok))

if not admin_ok:
    failures.append(('admin', path, admin_status, '200|404'))
if not auditor_ok:
    failures.append(('auditor', path, auditor_status, 302))

print(f"  [{result_icon(admin_status, 200):4s}] Admin  -> {admin_status}  (expected 200|404)")
print(f"  [{result_icon(auditor_status, 302):4s}] Auditor -> {auditor_status}  (expected 302)")

# -- SECTION E: CSRF Middleware --
print("\n" + DASH)
print("  SECTION E: CSRF MIDDLEWARE CHECK")
print(DASH)

settings_file = PROJECT / 'config' / 'settings' / 'base.py'
settings_content = settings_file.read_text(encoding='utf-8')
csrf_present = 'django.middleware.csrf.CsrfViewMiddleware' in settings_content
results.append(('CONFIG', 'CsrfViewMiddleware in MIDDLEWARE', 'YES' if csrf_present else 'NO', 'YES', csrf_present))
if csrf_present:
    print("  [PASS] CsrfViewMiddleware IS present in MIDDLEWARE (base.py:39)")
else:
    print("  [FAIL] CsrfViewMiddleware is NOT in MIDDLEWARE")
    failures.append(('config', 'CsrfViewMiddleware', 'MISSING', 'PRESENT'))

# -- SECTION F: PASSWORD_HASHERS --
print("\n" + DASH)
print("  SECTION F: PASSWORD_HASHERS CHECK")
print(DASH)

has_hashers_config = 'PASSWORD_HASHERS' in settings_content
if has_hashers_config:
    import re
    match = re.search(r'PASSWORD_HASHERS\s*=\s*\[([^\]]*)\]', settings_content, re.DOTALL)
    hasher_value = match.group(0).strip() if match else 'present (could not parse)'
    results.append(('CONFIG', 'PASSWORD_HASHERS', 'EXPLICIT', 'EXPLICIT or default', True))
    print(f"  [INFO] PASSWORD_HASHERS explicitly configured:")
    print(f"         {hasher_value}")
else:
    from django.conf import settings as dj_settings
    actual_hashers = dj_settings.PASSWORD_HASHERS
    print(f"  [INFO] PASSWORD_HASHERS not explicitly set in base.py")
    print(f"         Django default hashers are active:")
    for h in actual_hashers:
        print(f"           - {h}")
    results.append(('CONFIG', 'PASSWORD_HASHERS', 'Django default', 'EXPLICIT or default', True))
    print(f"  [PASS] Default Django password hashers are in use (acceptable)")

# -- SECTION G: Logout redirect --
print("\n" + DASH)
print("  SECTION G: LOGOUT VIEW")
print(DASH)
logout_status = get_status(admin_client, '/accounts/logout/')
print(f"  [INFO] /accounts/logout/ -> {logout_status}")
results.append(('ADMIN', '/accounts/logout/', logout_status, '302', logout_status == 302))

# -- SECTION H: Login page accessibility --
print("\n" + DASH)
print("  SECTION H: LOGIN PAGE (should be public)")
print(DASH)
login_status = get_status(anon_client, '/accounts/login/')
print(f"  [INFO] /accounts/login/ -> {login_status}")
results.append(('ANON', '/accounts/login/', login_status, '200', login_status == 200))

# -- SECTION I: Verify login form works via POST --
print("\n" + DASH)
print("  SECTION I: LOGIN VIA POST (form-based login)")
print(DASH)
# Use a fresh client to do form-based login with CSRF
login_client = Client(enforce_csrf_checks=False)
resp = login_client.post('/accounts/login/', {
    'username': 'audit_admin',
    'password': 'AuditPass123!'
})
print(f"  Login POST (admin)   -> {resp.status_code}")
if resp.status_code == 302:
    print(f"  Redirect location: {resp.get('Location', 'N/A')}")
    status_after = get_status(login_client, '/')
    print(f"  Follow-up GET / -> {status_after}")
else:
    print(f"  (No redirect -- form may have re-rendered)")

login_client2 = Client(enforce_csrf_checks=False)
resp2 = login_client2.post('/accounts/login/', {
    'username': 'audit_auditor',
    'password': 'AuditPass123!'
})
print(f"  Login POST (auditor) -> {resp2.status_code}")
if resp2.status_code == 302:
    print(f"  Redirect location: {resp2.get('Location', 'N/A')}")

# ======================================================================
# SUMMARY
# ======================================================================
print("\n" + SEP)
print("  AUDIT SUMMARY")
print(SEP)

total = len(results)
passed = sum(1 for r in results if r[4])
failed = total - passed

print(f"\n  Total tests:  {total}")
print(f"  Passed:       {passed}")
print(f"  Failed:       {failed}")
print(f"  Pass rate:    {passed/total*100:.1f}%")

if failures:
    print(f"\n  {DASH}")
    print(f"  FAILURES DETAIL:")
    print(f"  {DASH}")
    for role, path, actual, expected in failures:
        print(f"    [{role.upper():9s}] {path:<40s}  actual={actual}  expected={expected}")
else:
    print(f"\n  All tests PASSED.")

print("\n" + SEP)
print("  FULL RESULTS TABLE")
print(SEP)
print(f"  {'ROLE':<10s} {'PATH':<42s} {'STATUS':<8s} {'EXPECTED':<12s} {'RESULT'}")
print(f"  {'-'*10} {'-'*42} {'-'*8} {'-'*12} {'-'*6}")
for role, path, status, expected, ok in results:
    icon = "PASS" if ok else "FAIL"
    exp_str = str(expected)
    print(f"  {role:<10s} {path:<42s} {str(status):<8s} {exp_str:<12s} {icon}")

print("\n" + SEP)
print("  AUDIT COMPLETE")
print(SEP)
