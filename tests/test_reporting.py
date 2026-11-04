"""Simple/Developer reporting package — shared VerifiedResults, no fabricated evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reversex.api import app
from reversex.reporting import (
    build_report_package,
    explain_failed_test,
    narrate_event,
    render_simple_markdown,
)
from reversex.verification import VerificationStatus, build_verified_results

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'
client = TestClient(app)


def _job_with_target(target: str) -> str:
    for p in ARTIFACTS.iterdir():
        if not (p.is_dir() and len(p.name) == 32):
            continue
        inv = p / 'investigation' / 'report.json'
        final = p / 'final_report.json'
        if not inv.is_file() or not final.is_file():
            continue
        report = json.loads(inv.read_text(encoding='utf-8'))
        if report.get('target_id') == target and (p / 'validation' / 'validation_results.json').is_file():
            return p.name
    pytest.skip(f'No completed {target} job with validation artifacts')


def test_simple_and_developer_share_verified_findings():
    job = _job_with_target('taskboard')
    package = build_report_package(ARTIFACTS, job)
    verified = package['verified']
    assert verified.investigation_id == job
    assert 'ReverseX Simple Report' in package['simple_markdown']
    assert 'ReverseX Developer Report' in package['developer_markdown']
    # Same verified claim texts appear in both downloads
    for finding in verified.verified_findings:
        assert finding.claim_text in package['simple_markdown']
        assert finding.claim_text in package['developer_markdown']
    for finding in verified.unsupported_findings:
        # Unsupported must not be implied as verified-only section facts without label
        assert finding.verification_status == VerificationStatus.not_verified


def test_pass_fail_counts_match_validation_artifact():
    job = _job_with_target('taskboard')
    validation = json.loads(
        (ARTIFACTS / job / 'validation' / 'validation_results.json').read_text(encoding='utf-8')
    )
    package = build_report_package(ARTIFACTS, job)
    summary = package['verified'].validation_summary or {}
    # Engine recomputes; must match valid pass/fail semantics
    assert summary['passed'] == sum(1 for t in validation['tests'] if t['status'] == 'pass')
    assert summary['failed'] == sum(1 for t in validation['tests'] if t['status'] == 'fail')


def test_minicalc_report_package_when_available():
    job = _job_with_target('calculator')
    package = build_report_package(ARTIFACTS, job)
    assert package['verified'].target_application == 'calculator'
    assert 'MiniCalc' in package['simple_markdown'] or 'calculator' in package['simple_markdown']


def test_failed_comparison_explanation_does_not_blame_original():
    fail = explain_failed_test(
        {
            'test_id': 'calc_addition',
            'description': 'Add two numbers',
            'status': 'fail',
            'differences': ['result_text: 13 vs 14'],
            'original': {'observed_state': {'result_text': '13'}, 'error': None},
            'reconstruction': {'observed_state': {'result_text': '14'}, 'error': None},
        }
    )
    assert '13' in fail['original_did']
    assert '14' in fail['reconstruction_did']
    assert 'defective' not in fail['why_it_matters'].lower() or 'not proof' in fail['why_it_matters'].lower()
    assert 'reconstruction mismatch' in fail['why_it_matters'].lower()


def test_invalid_test_distinguished_from_fail():
    inv = explain_failed_test(
        {
            'test_id': 'broken',
            'description': 'Could not run',
            'status': 'invalid',
            'differences': [],
            'original': {'observed_state': {}, 'error': 'timeout'},
            'reconstruction': {'observed_state': {}, 'error': None},
        }
    )
    assert inv['status'] == 'invalid'
    assert 'not counted as a behavioral pass or fail' in inv['why_it_matters'].lower()


def test_timeline_uses_recorded_events_only():
    event = {
        'step': 2,
        'status': 'ok',
        'decision': {'action': 'click', 'reason': 'Offline scripted empty submission', 'value': None},
        'before': {'visible_text': 'No tasks yet.'},
        'after': {'visible_text': 'Task name is required.\nNo tasks yet.'},
    }
    card = narrate_event(event)
    assert 'Clicked' in card['what_reversex_did']
    assert 'Task name is required' in card['what_happened'] or 'required' in card['what_that_shows'].lower()
    assert card['recorded_purpose'] == 'Offline scripted empty submission'


def test_missing_evidence_incomplete_job_honest(tmp_path: Path):
    job_id = 'a' * 32
    root = tmp_path / job_id
    root.mkdir()
    (root / 'final_report.json').write_text(
        json.dumps(
            {
                'id': job_id,
                'status': 'incomplete',
                'mode': 'scripted',
                'target_id': 'taskboard',
                'stages': {},
            }
        ),
        encoding='utf-8',
    )
    (root / 'investigation').mkdir()
    (root / 'investigation' / 'report.json').write_text(
        json.dumps(
            {
                'target_id': 'taskboard',
                'feature': 'TaskBoard',
                'mode': 'scripted',
                'status': 'incomplete',
                'events': [],
                'objectives': {},
            }
        ),
        encoding='utf-8',
    )
    package = build_report_package(tmp_path, job_id)
    assert package['verified'].availability == 'partial'
    assert 'incomplete' in package['simple_markdown'].lower() or 'partial' in package['simple_markdown'].lower()
    assert package['verified'].validation_summary is None


def test_contradicted_finding_appears_as_unverified_section():
    job = _job_with_target('taskboard')
    verified = build_verified_results(
        ARTIFACTS,
        job,
        extra_claims=[],
    )
    # Built-in unsupported findings should stay out of verified bucket
    assert all(f.verification_status != VerificationStatus.not_verified for f in verified.verified_findings)
    md = render_simple_markdown(verified, timeline=[], failures=[], how_we_know=[])
    assert 'Unverified' in md or 'uncertain' in md.lower()


def test_api_human_report_and_downloads():
    job = _job_with_target('taskboard')
    human = client.get(f'/api/investigations/{job}/human-report')
    assert human.status_code == 200
    body = human.json()
    assert body['verified']['investigation_id'] == job
    assert 'timeline' in body
    assert 'status_labels' in body

    simple = client.get(f'/api/investigations/{job}/reports/simple.md')
    assert simple.status_code == 200
    assert 'text/markdown' in simple.headers.get('content-type', '')
    assert b'ReverseX Simple Report' in simple.content

    developer = client.get(f'/api/investigations/{job}/reports/developer.md')
    assert developer.status_code == 200
    assert b'ReverseX Developer Report' in developer.content
    # Same verified claim appears in both
    for finding in body['verified']['verified_findings']:
        assert finding['claim_text'].encode() in simple.content
        assert finding['claim_text'].encode() in developer.content


def test_api_report_invalid_id():
    assert client.get('/api/investigations/not-a-job/human-report').status_code in (400, 404, 422)


def test_controlled_repair_note_in_package_if_job_has_repair():
    # Prefer a job with repair_report; otherwise skip
    found = None
    for p in ARTIFACTS.iterdir():
        if p.is_dir() and (p / 'repair' / 'repair_report.json').is_file():
            found = p.name
            break
    if not found:
        pytest.skip('No per-job repair_report.json in artifacts')
    package = build_report_package(ARTIFACTS, found)
    assert package['verified'].repair_summary is not None
