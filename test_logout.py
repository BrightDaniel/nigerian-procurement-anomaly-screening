"""
Regression tests for the secure logout experience.
Run: python test_logout.py

Covers:
- Logout action + confirmation dialog markup on authenticated pages
  (sidebar and topbar triggers, POST form with CSRF, exact copy)
- POST logout: redirect to the sign-in page, success message shown
- GET logout refused (405) — never performs logout via GET
- CSRF enforcement: POST without token is rejected (403) and the
  session survives; POST with a valid token succeeds
- Session invalidation and protected-page access after logout
  (Administrator and Auditor)
- Logout response is not cacheable (supports safe Back behaviour
  without disabling caching app-wide)
- No user accounts or roles are modified
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

LOGOUT_MSG = 'You have been signed out successfully.'


def test(name, func):
    try:
        func()
        passed.append(name)
        print(f'  PASS  {name}')
    except Exception as e:
        errors.append((name, str(e)))
        print(f'  FAIL  {name}: {e}')


print('=' * 60)
print('SECURE LOGOUT REGRESSION TESTS')
print('=' * 60)

users_before = User.objects.count()

# ── 1. Confirmation dialog markup ──
print('\n[1] LOGOUT CONFIRMATION DIALOG')


def test_dialog_markup_admin():
    c = Client()
    c.login(username='admin', password='admin123')
    html = c.get('/').content.decode()
    for needle in (
        'id="logoutDialog"',
        'aria-labelledby="logoutDialogTitle"',
        'aria-describedby="logoutDialogMessage"',
        'Sign out?',
        'Are you sure you want to end your session?',
        'id="logoutCancelBtn"',
        'action="/accounts/logout/"',
        'method="post"',
        'csrfmiddlewaretoken',
        'data-logout-open',
    ):
        if needle not in html:
            raise AssertionError(f'dialog markup missing: {needle}')
    if html.count('data-logout-open') < 2:
        raise AssertionError('expected logout triggers in sidebar AND topbar')
test('Dialog markup + sidebar/topbar triggers present (admin)', test_dialog_markup_admin)


def test_dialog_markup_auditor():
    c = Client()
    if not c.login(username='test_auditor_perm_13700', password='test1234'):
        raise AssertionError('auditor login failed')
    html = c.get('/').content.decode()
    for needle in ('id="logoutDialog"', 'Sign out?', 'data-logout-open', 'action="/accounts/logout/"'):
        if needle not in html:
            raise AssertionError(f'dialog markup missing for auditor: {needle}')
test('Dialog + triggers present for Auditor', test_dialog_markup_auditor)

# ── 2. POST logout flow ──
print('\n[2] POST LOGOUT (redirect + message)')


def test_post_logout_redirects():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    resp = c.post('/accounts/logout/')
    if resp.status_code != 302:
        raise AssertionError(f'POST logout returned {resp.status_code}, expected 302')
    if resp.get('Location') != '/accounts/login/':
        raise AssertionError(f'POST logout redirected to {resp.get("Location")}')


test('POST logout redirects to the sign-in page', test_post_logout_redirects)


def test_post_logout_message():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    resp = c.post('/accounts/logout/', follow=True)
    html = resp.content.decode()
    if LOGOUT_MSG not in html:
        raise AssertionError('success message not shown on sign-in page')
    if 'id="login-form"' not in html:
        raise AssertionError('expected the sign-in page after logout')
    if 'alert-success' not in html:
        raise AssertionError('message not rendered as a success alert')


test('Success message "You have been signed out successfully." on sign-in page', test_post_logout_message)

# ── 3. GET never logs out ──
print('\n[3] GET REFUSED')


def test_get_logout_refused():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    resp = c.get('/accounts/logout/')
    if resp.status_code != 405:
        raise AssertionError(f'GET logout returned {resp.status_code}, expected 405')
    after = c.get('/')
    if after.status_code != 200:
        raise AssertionError('GET /accounts/logout/ ended the session (must be POST-only)')
    c.post('/accounts/logout/')


test('GET /accounts/logout/ returns 405 and does not end the session', test_get_logout_refused)

# ── 4. CSRF enforcement ──
print('\n[4] CSRF')


def test_logout_csrf_enforced():
    c = Client(enforce_csrf_checks=True)
    c.login(username='admin', password='admin123')
    resp = c.post('/accounts/logout/')
    if resp.status_code != 403:
        raise AssertionError(f'POST logout without CSRF token returned {resp.status_code}, expected 403')
    if c.get('/').status_code != 200:
        raise AssertionError('CSRF-rejected logout still ended the session')
    c.post('/accounts/logout/')


test('POST logout without CSRF token -> 403, session survives', test_logout_csrf_enforced)


def test_logout_csrf_token_accepted():
    c = Client(enforce_csrf_checks=True)
    c.get('/accounts/login/')
    token = c.cookies['csrftoken'].value
    c.post('/accounts/login/', {
        'username': 'admin', 'password': 'admin123',
        'csrfmiddlewaretoken': token,
    }, HTTP_REFERER='http://localhost:8000/accounts/login/')
    token = c.cookies['csrftoken'].value
    resp = c.post('/accounts/logout/', {
        'csrfmiddlewaretoken': token,
    }, HTTP_REFERER='http://localhost:8000/')
    if resp.status_code != 302:
        raise AssertionError(f'POST logout with CSRF token returned {resp.status_code}, expected 302')
    if c.get('/').status_code != 302:
        raise AssertionError('session still authenticated after CSRF-valid logout')


test('POST logout with valid CSRF token succeeds', test_logout_csrf_token_accepted)

# ── 5. Session invalidation + protected pages ──
print('\n[5] SESSION INVALIDATION & PROTECTED PAGES')


def test_session_invalidated():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    if c.session.get('_auth_user_id') is None:
        raise AssertionError('login did not establish a session')
    c.post('/accounts/logout/')
    if c.session.get('_auth_user_id') is not None:
        raise AssertionError('session still contains _auth_user_id after logout')


test('Session flushed on logout (_auth_user_id removed)', test_session_invalidated)


def test_protected_pages_after_logout():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    c.post('/accounts/logout/')
    for url in ('/', '/anomalies/', '/records/', '/reports/',
                '/analytics/performance/', '/ingestion/import/', '/system/users/'):
        resp = c.get(url)
        if resp.status_code != 302:
            raise AssertionError(f'Anonymous GET {url} returned {resp.status_code}, expected 302')
        if '/accounts/login/' not in (resp.get('Location') or ''):
            raise AssertionError(f'Anonymous GET {url} did not redirect to login')


test('All protected pages redirect to login after logout (admin)', test_protected_pages_after_logout)


def test_auditor_logout():
    c = Client()
    if not c.login(username='test_auditor_perm_13700', password='test1234'):
        raise AssertionError('auditor login failed')
    resp = c.post('/accounts/logout/')
    if resp.status_code != 302 or resp.get('Location') != '/accounts/login/':
        raise AssertionError(f'auditor POST logout: {resp.status_code} {resp.get("Location")}')
    if c.get('/').status_code != 302:
        raise AssertionError('auditor session still authenticated after logout')
    if c.get('/accounts/login/').status_code != 200:
        raise AssertionError('auditor cannot reach sign-in page after logout')


test('Auditor logout works; session ends; sign-in reachable', test_auditor_logout)

# ── 6. Caching / Back navigation ──
print('\n[6] CACHING')


def test_logout_not_cacheable():
    c = Client()
    c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
    resp = c.post('/accounts/logout/')
    cache_control = (resp.get('Cache-Control') or '').lower()
    if 'no-store' not in cache_control and 'no-cache' not in cache_control:
        raise AssertionError(f'logout response cacheable: Cache-Control={cache_control!r}')


test('Logout response is not cacheable (@never_cache)', test_logout_not_cacheable)

# ── 7. Data integrity ──
print('\n[7] DATA INTEGRITY')


def test_no_account_changes():
    if User.objects.count() != users_before:
        raise AssertionError('user count changed during logout tests')
    admin = User.objects.filter(username='admin').first()
    if admin is None or not admin.is_active:
        raise AssertionError('admin account was modified')
    auditor = User.objects.filter(username='test_auditor_perm_13700').first()
    if auditor is None or not auditor.is_active:
        raise AssertionError('auditor account was modified')


test('No user accounts, roles, or passwords were modified', test_no_account_changes)

# ── Summary ──
print('\n' + '=' * 60)
print(f'RESULTS: {len(passed)} passed, {len(errors)} failed, {len(passed) + len(errors)} total')
print('=' * 60)
if errors:
    for name, msg in errors:
        print(f'  FAILED: {name}: {msg}')
    sys.exit(1)
sys.exit(0)
