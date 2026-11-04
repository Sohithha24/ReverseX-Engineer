"""Regression tests for ContactPad / generic Understand reporting (second UX audit)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from reversex.reporting import narrate_event, outcome_blurb, render_simple_markdown
from reversex.verification import (
    VerificationStatus,
    build_verified_results,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'
CONTACTPAD_JOB = 'fe8ef0266f9247638f69a23654d0ad5c'


def _contactpad_job() -> str:
    path = ARTIFACTS / CONTACTPAD_JOB / 'investigation' / 'report.json'
    if not path.is_file():
        pytest.skip('Saved ContactPad Muse investigation artifacts unavailable')
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('target_id') != 'contactpad':
        pytest.skip('Expected ContactPad investigation artifacts')
    return CONTACTPAD_JOB


def _write_job(tmp: Path, job_id: str, *, final=None, investigation=None):
    root = tmp / job_id
    root.mkdir(parents=True)
    if final is not None:
        (root / 'final_report.json').write_text(json.dumps(final), encoding='utf-8')
    if investigation is not None:
        (root / 'investigation').mkdir()
        (root / 'investigation' / 'report.json').write_text(json.dumps(investigation), encoding='utf-8')
    return root


def test_contactpad_behavioral_findings_from_browser_evidence():
    job = _contactpad_job()
    results = build_verified_results(ARTIFACTS, job)
    texts = [f.claim_text for f in results.verified_findings]
    rules = {f.rule_id for f in results.verified_findings}

    assert 'rule.observation_fill' in rules
    assert 'rule.observation_click' in rules
    assert 'rule.observation_visible_change' in rules
    assert 'rule.observation_new_visible_text' in rules
    assert 'rule.observation_submitted_value_visible' in rules
    assert any('Message sent: Test User' in t for t in texts)
    assert any('Send message' in t for t in texts)
    assert any('Test User' in t and 'filled' in t for t in texts)


def test_contactpad_does_not_leak_taskboard_claims():
    job = _contactpad_job()
    results = build_verified_results(ARTIFACTS, job)
    blob = ' '.join(
        f.claim_text
        for f in (
            results.verified_findings
            + results.partially_verified_findings
            + results.unsupported_findings
            + results.contradicted_findings
            + results.requires_review_findings
        )
    )
    blob += ' ' + ' '.join(results.untested_behaviors)
    assert 'PostgreSQL' not in blob
    assert 'created task' not in blob.lower()
    assert 'Task editing' not in blob
    assert 'Reload persistence was investigated for a created task.' not in blob


def test_understand_only_availability_complete_and_recon_not_requested():
    job = _contactpad_job()
    results = build_verified_results(ARTIFACTS, job)
    assert results.pipeline == 'investigate_only'
    assert results.availability == 'complete'
    assert any(f.rule_id == 'rule.reconstruction_not_requested' for f in results.verified_findings)
    blurb = outcome_blurb(results)
    assert 'not requested' in blurb.lower()
    assert 'partially available' not in blurb.lower()


def test_muse_stop_reason_alone_does_not_verify_without_browser_change(tmp_path: Path):
    """Misleading agent summary without visible_text change must not invent confirmation findings."""
    job_id = 'c' * 32
    _write_job(
        tmp_path,
        job_id,
        final={
            'id': job_id,
            'status': 'completed',
            'mode': 'muse',
            'pipeline': 'investigate_only',
            'target_id': 'contactpad',
            'stages': {
                'investigation': {'executed': True, 'status': 'completed'},
                'reconstruction': {'executed': False, 'status': 'skipped', 'note': 'Understand-only'},
                'validation': {'executed': False, 'status': 'skipped', 'note': 'Understand-only'},
            },
        },
        investigation={
            'target_id': 'contactpad',
            'feature': 'Submit a contact message and view confirmation',
            'mode': 'muse',
            'status': 'completed',
            'events': [
                {
                    'step': 1,
                    'status': 'ok',
                    'decision': {
                        'action': 'stop',
                        'reason': "Confirmation observed: 'Message sent: Test User'",
                    },
                    'before': {
                        'visible_text': 'ContactPad\nNo message sent yet.',
                        'elements': [],
                    },
                    'after': {
                        'visible_text': 'ContactPad\nNo message sent yet.',
                        'elements': [],
                    },
                }
            ],
            'objectives': {},
        },
    )
    results = build_verified_results(tmp_path, job_id)
    assert not any(f.rule_id == 'rule.observation_new_visible_text' for f in results.verified_findings)
    assert not any('Message sent' in f.claim_text for f in results.verified_findings)
    assert any(f.rule_id == 'rule.investigation_mode' for f in results.verified_findings)


def test_missing_browser_evidence_yields_no_fill_findings(tmp_path: Path):
    job_id = 'd' * 32
    _write_job(
        tmp_path,
        job_id,
        final={
            'id': job_id,
            'status': 'completed',
            'mode': 'muse',
            'pipeline': 'investigate_only',
            'target_id': 'contactpad',
            'stages': {
                'reconstruction': {'status': 'skipped'},
                'validation': {'status': 'skipped'},
            },
        },
        investigation={
            'target_id': 'contactpad',
            'feature': 'Submit a contact message and view confirmation',
            'mode': 'muse',
            'status': 'completed',
            'events': [],
            'objectives': {},
        },
    )
    results = build_verified_results(tmp_path, job_id)
    assert not any(
        (f.rule_id or '').startswith('rule.observation_') for f in results.verified_findings
    )


def test_simple_report_consistent_with_verified_findings_for_contactpad():
    job = _contactpad_job()
    results = build_verified_results(ARTIFACTS, job)
    md = render_simple_markdown(results, timeline=[], failures=[], how_we_know=[])
    for finding in results.verified_findings:
        if finding.verification_status == VerificationStatus.verified:
            assert finding.claim_text in md
    assert 'PostgreSQL' not in md
    assert 'Reconstruction was not requested' in md


def test_narrate_event_prefers_new_visible_lines():
    event = {
        'step': 4,
        'decision': {'action': 'click', 'element_id': 's4_e3', 'reason': 'submit'},
        'before': {'visible_text': 'ContactPad\nNo message sent yet.'},
        'after': {
            'visible_text': 'ContactPad\nMessage sent: Test User\nTest User <a@b.com>: hi',
        },
    }
    narrated = narrate_event(event)
    assert 'Message sent: Test User' in narrated['what_happened']
    assert 'New visible content' in narrated['what_that_shows']


def test_failed_validation_still_partial_when_expected(tmp_path: Path):
    job_id = 'e' * 32
    _write_job(
        tmp_path,
        job_id,
        final={'id': job_id, 'status': 'completed', 'mode': 'scripted', 'target_id': 'taskboard', 'stages': {}},
        investigation={'target_id': 'taskboard', 'feature': 'x', 'mode': 'scripted', 'events': [], 'objectives': {}},
    )
    results = build_verified_results(tmp_path, job_id)
    assert results.availability == 'partial'
