from pathlib import Path

from fastapi.testclient import TestClient

from reversex.api import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_health_reports_phase_and_reconstruction_flag():
    response = client.get('/health')
    assert response.status_code == 200
    body = response.json()
    assert body['phase'] == '5c'
    assert body['public'] is False
    assert 'taskboard' in (body.get('authorized_targets') or [])
    assert 'calculator' in (body.get('authorized_targets') or [])
    expected = (ROOT / 'artifacts' / 'phase2' / 'reconstructed-app' / 'index.html').is_file()
    assert body['reconstruction_available'] is expected


def test_api_targets_allowlist_only():
    response = client.get('/api/targets')
    assert response.status_code == 200
    ids = {t['id'] for t in response.json()['targets']}
    assert ids == {'taskboard', 'calculator'}
    for t in response.json()['targets']:
        assert t['origin'].startswith('http://127.0.0.1:')


def test_api_rejects_unknown_mode():
    response = client.post('/api/investigations', json={'mode': 'unlimited'})
    assert response.status_code == 422


def test_api_rejects_unknown_target_id():
    response = client.post('/api/investigations', json={
        'mode': 'scripted', 'target_id': 'https://evil.example',
    })
    assert response.status_code == 422


def test_api_rejects_arbitrary_target_urls():
    response = client.post('/api/investigations', json={
        'mode': 'scripted', 'url': 'https://example.com'
    })
    assert response.status_code == 422


def test_api_rejects_invalid_job_id():
    response = client.get('/api/investigations/../secrets')
    assert response.status_code in (400, 404, 422)


def test_demo_evidence_graph_from_preserved_artifacts():
    response = client.get('/api/demo/evidence-graph')
    assert response.status_code == 200
    body = response.json()
    assert body['nodes']
    assert body['edges']
    assert any(n['type'] == 'validation_outcome' for n in body['nodes'])


def test_get_missing_investigation_404():
    response = client.get('/api/investigations/' + ('a' * 32))
    assert response.status_code == 404


def test_screenshot_endpoint_rejects_path_traversal():
    job = 'c' * 32
    response = client.get(f'/api/investigations/{job}/screenshots/../secrets.png')
    assert response.status_code in (400, 404)


def test_screenshot_list_for_known_job_if_present():
    job = 'c' * 32
    # Job may exist on disk from Phase 4A E2E; either 200 with list or 404.
    response = client.get(f'/api/investigations/{job}/screenshots')
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        body = response.json()
        assert body['id'] == job
        assert isinstance(body['screenshots'], list)
        for item in body['screenshots']:
            assert item['filename'].endswith('.png')
            assert '..' not in item['filename']
