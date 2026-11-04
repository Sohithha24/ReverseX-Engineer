"""Allowlisted custom-application URL investigation tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reversex.api import app
from reversex.browser import validate_target
from reversex.targets import (
    ORIGIN_ALLOWLIST,
    TargetAuthorizationError,
    normalize_origin,
    resolve_authorized_application,
)

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
CONTACTPAD = ROOT / 'fixtures' / 'contactpad'


def test_allowlist_includes_contactpad_origin():
    assert 'http://127.0.0.1:8005' in ORIGIN_ALLOWLIST
    assert ORIGIN_ALLOWLIST['http://127.0.0.1:8005'] == 'contactpad'


def test_normalize_origin_rejects_public_and_aliases():
    with pytest.raises(TargetAuthorizationError):
        normalize_origin('https://example.com')
    with pytest.raises(TargetAuthorizationError):
        normalize_origin('http://localhost:8005/')
    with pytest.raises(TargetAuthorizationError):
        normalize_origin('http://127.0.0.1:9999/')
    with pytest.raises(TargetAuthorizationError):
        normalize_origin('http://user:pass@127.0.0.1:8005/')
    assert normalize_origin('http://127.0.0.1:8005/path') == 'http://127.0.0.1:8005'


def test_resolve_authorized_application_passes_feature():
    target, url = resolve_authorized_application(
        application_url='http://127.0.0.1:8005/',
        feature='Submit a contact message and view confirmation',
    )
    assert target.id == 'contactpad'
    assert 'Submit a contact message' in target.feature_label
    assert 'Submit a contact message' in target.muse_system
    assert url.startswith('http://127.0.0.1:8005')
    assert target.validation_suite is None
    assert target.supports_independent_validation is False


def test_resolve_rejects_unlisted_url():
    with pytest.raises(TargetAuthorizationError):
        resolve_authorized_application(application_url='http://127.0.0.1:8011/')


def test_browser_validate_target_rejects_cross_origin_and_bad_port():
    with pytest.raises(ValueError):
        validate_target('http://127.0.0.1:8003/', 'http://127.0.0.1:8005')
    with pytest.raises(ValueError):
        validate_target('http://127.0.0.1:8011/', 'http://127.0.0.1:8011')


def test_api_resolve_approved_and_rejected():
    ok = client.post(
        '/api/targets/resolve',
        json={
            'application_url': 'http://127.0.0.1:8005/',
            'feature': 'Submit a contact message',
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body['approved'] is True
    assert body['target_id'] == 'contactpad'
    assert body['independent_validation_available'] is False
    assert 'Submit a contact message' in body['feature']

    bad = client.post('/api/targets/resolve', json={'application_url': 'https://evil.example'})
    assert bad.status_code == 400


def test_api_create_rejects_unapproved_url():
    response = client.post(
        '/api/investigations',
        json={
            'mode': 'scripted',
            'application_url': 'http://127.0.0.1:8011/',
            'feature': 'anything',
            'investigation_goal': 'understand',
        },
    )
    assert response.status_code == 400


def test_api_targets_include_contactpad():
    response = client.get('/api/targets')
    assert response.status_code == 200
    ids = {t['id'] for t in response.json()['targets']}
    assert ids == {'taskboard', 'calculator', 'contactpad', 'it-tools'}


def test_scripted_contactpad_investigation_end_to_end(tmp_path):
    """Real browser investigation against ContactPad when the fixture server is reachable."""
    import urllib.error
    import urllib.request

    from reversex.run import explore

    try:
        urllib.request.urlopen('http://127.0.0.1:8005/', timeout=1)
    except (urllib.error.URLError, TimeoutError, OSError):
        pytest.skip('ContactPad fixture server is not running on :8005')

    out = tmp_path / 'inv'
    report = explore(
        'scripted',
        url='http://127.0.0.1:8005/',
        output_dir=str(out),
        max_actions=12,
        target_id='contactpad',
        feature='Submit a contact message and view confirmation',
    )
    assert report['target_id'] == 'contactpad'
    assert 'Submit a contact message' in report['feature']
    assert report['independent_validation_available'] is False
    assert report['status'] in ('completed', 'incomplete', 'budget_exhausted')
    assert any(ev.get('status') == 'ok' for ev in report['events'])
    assert (out / 'report.json').is_file()
    saved = json.loads((out / 'report.json').read_text(encoding='utf-8'))
    assert saved['feature'] == report['feature']


def test_contactpad_fixture_files_exist():
    assert (CONTACTPAD / 'index.html').is_file()
    assert (CONTACTPAD / 'app.js').is_file()
    assert (CONTACTPAD / 'style.css').is_file()
    html = (CONTACTPAD / 'index.html').read_text(encoding='utf-8')
    assert 'ContactPad' in html
    assert 'contact-form' in html
    assert 'Send message' in html
    # Distinct product — not a TaskBoard/MiniCalc clone
    assert 'Add task' not in html
    assert 'Subtract' not in html
