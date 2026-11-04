"""IT-Tools allowlist / security registration tests (no Muse calls)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from reversex.api import app
from reversex.browser import validate_target
from reversex.targets import (
    ALLOWED_LOCAL_PORTS,
    INVESTIGATION_PORTS,
    ORIGIN_ALLOWLIST,
    TargetAuthorizationError,
    normalize_origin,
    resolve_authorized_application,
)

client = TestClient(app)


def test_it_tools_origin_allowlisted():
    assert 8010 in INVESTIGATION_PORTS
    assert 8010 in ALLOWED_LOCAL_PORTS
    assert ORIGIN_ALLOWLIST.get('http://127.0.0.1:8010') == 'it-tools'


def test_it_tools_resolve_with_feature_description():
    target, url = resolve_authorized_application(
        application_url='http://127.0.0.1:8010/',
        feature='Base64 text encoding and decoding',
    )
    assert target.id == 'it-tools'
    assert target.feature_label == 'Base64 text encoding and decoding'
    assert 'Base64 text encoding and decoding' in target.muse_system
    assert target.supports_independent_validation is False
    assert target.validation_suite is None
    assert url.startswith('http://127.0.0.1:8010')


def test_it_tools_rejects_unrelated_urls():
    with pytest.raises(TargetAuthorizationError):
        normalize_origin('https://example.com/')
    with pytest.raises(TargetAuthorizationError):
        normalize_origin('http://127.0.0.1:9999/')
    with pytest.raises(TargetAuthorizationError):
        normalize_origin('http://localhost:8010/')
    with pytest.raises(ValueError):
        validate_target('http://127.0.0.1:8003/', 'http://127.0.0.1:8010')


def test_api_resolve_it_tools_approved():
    response = client.post(
        '/api/targets/resolve',
        json={
            'application_url': 'http://127.0.0.1:8010/',
            'feature': 'Base64 text encoding and decoding',
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body['approved'] is True
    assert body['target_id'] == 'it-tools'


def test_api_resolve_public_url_rejected():
    response = client.post(
        '/api/targets/resolve',
        json={'application_url': 'https://it-tools.tech/', 'feature': 'Base64'},
    )
    assert response.status_code in (400, 422)
