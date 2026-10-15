"""
Regression tests for the sign-in page layout and authentication fix.
Run: python test_auth_login.py

Covers:
- Login page renders standalone (no authenticated app shell/sidebar)
- Valid Administrator login redirects to dashboard
- Valid Auditor login (existing account + actual valid credentials)
- Invalid credentials show a non-sensitive error, no session created
- Inactive account cannot authenticate (temporary fixture, cleaned up)
- Logout works; no redirect loops
- Anonymous access restrictions
- Auditor restrictions (Users, Settings, Import Dataset)
- Administrator access to restricted sections
- CSRF enforcement preserved
"""
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

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


print('=' * 60)
print('AUTH / LOGIN REGRESSION TESTS')
print('=' * 60)

# ── 1. Login page layout ──
print('\n[1] LOGIN PAGE LAYOUT (standalone shell)')

def test_login_renders():
    c = Client()
    resp = c.get('/accounts/login/')
    if resp.status_code != 200:
        raise AssertionError(f'GET login returned {resp.status_code}')
test('Login page renders (200)', test_login_renders)

def test_no_sidebar():
    html = Client().get('/accounts/login/').content.decode()
    if 'id="sidebar"' in html:
        raise AssertionError('Login page contains the app sidebar')
    if 'app-layout' in html:
        raise AssertionError('Login page contains the authenticated app-layout shell')
    if 'sidebar-link' in html or 'sidebar-user' in html:
        raise AssertionError('Login page contains authenticated navigation/account controls')
    if 'class="topbar"' in html:
        raise AssertionError('Login page contains the authenticated topbar')
test('Login page has no sidebar or app shell', test_no_sidebar)

def test_no_app_js():
    html = Client().get('/accounts/login/').content.decode()
    if 'js/app.js' in html:
        raise AssertionError('Login page loads the sidebar app.js (not needed without a sidebar)')
    if 'auth-layout' not in html:
        raise AssertionError('Login page does not use the standalone auth layout')
test('Login page uses standalone auth layout (no app.js)', test_no_app_js)

def test_login_form_fields():
    html = Client().get('/accounts/login/').content.decode()
    for needle in ['name="username"', 'name="password"', 'csrfmiddlewaretoken',
                   'type="submit"', 'for="id_username"', 'for="id_password"']:
        if needle not in html:
            raise AssertionError(f'Missing form element: {needle}')
test('Login form has labelled fields, CSRF token, submit button', test_login_form_fields)

# ── 2. Administrator login ──
print('\n[2] ADMINISTRATOR LOGIN')

def test_admin_login_redirect():
    c = Client(enforce_csrf_checks=True)
    c.get('/accounts/login/')
    token = c.cookies['csrftoken'].value
    resp = c.post('/accounts/login/', {
        'username': 'admin', 'password': 'admin123',
        'csrfmiddlewaretoken': token,
    }, HTTP_REFERER='http://localhost:8000/accounts/login/')
    if resp.status_code != 302:
        raise AssertionError(f'Valid admin login returned {resp.status_code}, expected 302')
    if resp.get('Location') != '/':
        raise AssertionError(f'Redirected to {resp.get("Location")}, expected / (dashboard)')
    dash = c.get('/')
    if dash.status_code != 200:
        raise AssertionError(f'Dashboard after login returned {dash.status_code}')
    expected = str(User.objects.get(username='admin').pk)
    if c.session.get('_auth_user_id') != expected:
        raise AssertionError('Session does not contain the admin user')
test('Valid Administrator login redirects to dashboard', test_admin_login_redirect)

def test_admin_sections():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    for url in ['/system/users/', '/system/settings/', '/ingestion/import/']:
        resp = c.get(url)
        if resp.status_code != 200:
            raise AssertionError(f'Admin GET {url} returned {resp.status_code}, expected 200')
test('Administrator can access Users, Settings, Import Dataset', test_admin_sections)

# ── 3. Auditor login (existing account, actual credentials) ──
print('\n[3] AUDITOR LOGIN (existing account)')

def test_auditor_exists():
    if not User.objects.filter(username='test_auditor_perm_13700', role='AUDITOR').exists():
        raise AssertionError('Existing auditor account test_auditor_perm_13700 not found')
test('Existing auditor account present in database', test_auditor_exists)

def test_auditor_login():
    c = Client(enforce_csrf_checks=True)
    c.get('/accounts/login/')
    token = c.cookies['csrftoken'].value
    resp = c.post('/accounts/login/', {
        'username': 'test_auditor_perm_13700', 'password': 'test1234',
        'csrfmiddlewaretoken': token,
    }, HTTP_REFERER='http://localhost:8000/accounts/login/')
    if resp.status_code != 302:
        raise AssertionError(f'Valid auditor login returned {resp.status_code}, expected 302')
    if resp.get('Location') != '/':
        raise AssertionError(f'Auditor redirected to {resp.get("Location")}, expected /')
test('Valid Auditor login redirects to dashboard', test_auditor_login)

def test_auditor_restrictions():
    c = Client()
    c.post('/accounts/login/', {'username': 'test_auditor_perm_13700', 'password': 'test1234'})
    for url in ['/system/users/', '/system/settings/', '/ingestion/import/']:
        resp = c.get(url)
        if resp.status_code != 302:
            raise AssertionError(f'Auditor GET {url} returned {resp.status_code}, expected 302 redirect')
    resp = c.get('/anomalies/')
    if resp.status_code != 200:
        raise AssertionError(f'Auditor GET /anomalies/ returned {resp.status_code}, expected 200')
test('Auditor blocked from admin sections, can view anomalies', test_auditor_restrictions)

# ── 4. Invalid credentials ──
print('\n[4] INVALID CREDENTIALS')

def test_wrong_password():
    c = Client(enforce_csrf_checks=True)
    c.get('/accounts/login/')
    token = c.cookies['csrftoken'].value
    resp = c.post('/accounts/login/', {
        'username': 'admin', 'password': 'definitely-wrong-pw',
        'csrfmiddlewaretoken': token,
    }, HTTP_REFERER='http://localhost:8000/accounts/login/')
    if resp.status_code != 200:
        raise AssertionError(f'Wrong-password POST returned {resp.status_code}, expected 200 (re-render)')
    if 'alert-error' not in resp.content.decode():
        raise AssertionError('Wrong-password response shows no error message')
    if c.session.get('_auth_user_id') is not None:
        raise AssertionError('Session created despite invalid credentials')
test('Invalid password shows error, no session created', test_wrong_password)

def test_unknown_user():
    c = Client(enforce_csrf_checks=True)
    c.get('/accounts/login/')
    token = c.cookies['csrftoken'].value
    resp = c.post('/accounts/login/', {
        'username': 'no-such-user-zz', 'password': 'whatever',
        'csrfmiddlewaretoken': token,
    }, HTTP_REFERER='http://localhost:8000/accounts/login/')
    if resp.status_code != 200 or 'alert-error' not in resp.content.decode():
        raise AssertionError('Unknown user did not receive a non-sensitive error')
    if c.session.get('_auth_user_id') is not None:
        raise AssertionError('Session created for unknown user')
test('Unknown user shows non-sensitive error', test_unknown_user)

def test_error_message_not_sensitive():
    c = Client()
    resp = c.post('/accounts/login/', {'username': 'admin', 'password': 'wrong'})
    body = resp.content.decode().lower()
    if 'hash' in body or 'pbkdf2' in body or 'traceback' in body:
        raise AssertionError('Error response leaks sensitive details')
test('Error messages do not leak sensitive details', test_error_message_not_sensitive)

# ── 5. Inactive account ──
print('\n[5] INACTIVE ACCOUNT')

def test_inactive_cannot_login():
    tmp = User.objects.create_user(
        username='_tmp_inactive_login_test', password='TmpPass1234!',
        role='AUDITOR', is_active=False)
    try:
        c = Client(enforce_csrf_checks=True)
        c.get('/accounts/login/')
        token = c.cookies['csrftoken'].value
        resp = c.post('/accounts/login/', {
            'username': '_tmp_inactive_login_test', 'password': 'TmpPass1234!',
            'csrfmiddlewaretoken': token,
        }, HTTP_REFERER='http://localhost:8000/accounts/login/')
        if c.session.get('_auth_user_id') is not None:
            raise AssertionError('Inactive account was authenticated')
        if resp.status_code != 200:
            raise AssertionError(f'Inactive login returned {resp.status_code}, expected 200 (rejected)')
        if 'alert-error' not in resp.content.decode():
            raise AssertionError('Inactive login rejection shows no error')
    finally:
        User.objects.filter(username='_tmp_inactive_login_test').delete()
        if User.objects.filter(username='_tmp_inactive_login_test').exists():
            raise AssertionError('Temp fixture user not cleaned up')
test('Inactive account cannot authenticate (fixture cleaned up)', test_inactive_cannot_login)

# ── 6. Logout and redirect safety ──
print('\n[6] LOGOUT & REDIRECTS')

def test_logout():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    resp = c.post('/accounts/logout/', follow=True)
    if resp.status_code != 200:
        raise AssertionError(f'Logout returned {resp.status_code}')
    html = resp.content.decode()
    if 'You have been signed out successfully.' not in html:
        raise AssertionError('Logout success message not shown on sign-in page')
    if 'id="login-form"' not in html:
        raise AssertionError('After logout expected the sign-in page')
    after = c.get('/')
    if after.status_code != 302:
        raise AssertionError(f'After logout GET / returned {after.status_code}, expected 302 (anonymous)')
test('Logout works; user becomes anonymous', test_logout)

def test_no_login_redirect_loop():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    resp = c.get('/accounts/login/')
    if resp.status_code != 302:
        raise AssertionError(f'Authenticated GET login returned {resp.status_code}, expected 302 away')
    if resp.get('Location') != '/':
        raise AssertionError(f'Authenticated GET login redirected to {resp.get("Location")}, expected /')
    dash = c.get('/')
    if dash.status_code != 200:
        raise AssertionError('Dashboard not reachable after login redirect (loop?)')
test('No redirect loop between login and dashboard', test_no_login_redirect_loop)

# ── 7. Anonymous restrictions ──
print('\n[7] ANONYMOUS ACCESS')

def test_anonymous_redirected():
    c = Client()
    for url in ['/', '/anomalies/', '/records/', '/reports/']:
        resp = c.get(url)
        if resp.status_code != 302:
            raise AssertionError(f'Anonymous GET {url} returned {resp.status_code}, expected 302')
        if '/accounts/login/' not in (resp.get('Location') or ''):
            raise AssertionError(f'Anonymous GET {url} redirected to {resp.get("Location")}, not login')
test('Anonymous users are redirected to login', test_anonymous_redirected)

def test_anonymous_admin_blocked():
    c = Client()
    for url in ['/system/users/', '/system/settings/', '/ingestion/import/']:
        resp = c.get(url)
        if resp.status_code != 302:
            raise AssertionError(f'Anonymous GET {url} returned {resp.status_code}, expected 302')
test('Anonymous users blocked from admin sections', test_anonymous_admin_blocked)

# ── 8. CSRF enforcement ──
print('\n[8] CSRF')

def test_csrf_enforced():
    c = Client(enforce_csrf_checks=True)
    resp = c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    if resp.status_code != 403:
        raise AssertionError(f'POST without CSRF token returned {resp.status_code}, expected 403')
test('CSRF protection still enforced on login POST', test_csrf_enforced)

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
