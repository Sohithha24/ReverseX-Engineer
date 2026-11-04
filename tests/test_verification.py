"""Evidence Verification Engine tests — deterministic predicate checks."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reversex.api import app
from reversex.verification import (
    ClaimCategory,
    ProblemCategory,
    StructuredClaim,
    VerificationStatus,
    build_verified_results,
    check_reload_persistence_predicates,
    check_repair_outcome,
    check_validation_pass_count,
    load_artifact_bundle,
    verify_structured_claim,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'
client = TestClient(app)

TASKBOARD_JOBS = [
    p.name
    for p in ARTIFACTS.iterdir()
    if p.is_dir()
    and len(p.name) == 32
    and (p / 'validation' / 'validation_results.json').is_file()
    and (p / 'investigation' / 'report.json').is_file()
]


def _first_taskboard_job() -> str:
    for job in TASKBOARD_JOBS:
        report = json.loads((ARTIFACTS / job / 'investigation' / 'report.json').read_text(encoding='utf-8'))
        if report.get('target_id') == 'taskboard':
            return job
    pytest.skip('No completed TaskBoard investigation artifacts available')


def _write_job(tmp: Path, job_id: str, *, final=None, investigation=None, validation=None, repair=None, recon_files=True):
    root = tmp / job_id
    root.mkdir(parents=True)
    if final is not None:
        (root / 'final_report.json').write_text(json.dumps(final), encoding='utf-8')
    if investigation is not None:
        (root / 'investigation').mkdir()
        (root / 'investigation' / 'report.json').write_text(json.dumps(investigation), encoding='utf-8')
    if validation is not None:
        (root / 'validation').mkdir()
        (root / 'validation' / 'validation_results.json').write_text(json.dumps(validation), encoding='utf-8')
    if repair is not None:
        (root / 'repair').mkdir()
        (root / 'repair' / 'repair_report.json').write_text(json.dumps(repair), encoding='utf-8')
    if recon_files:
        recon = root / 'reconstructed-app'
        recon.mkdir()
        for name in ('index.html', 'script.js', 'style.css'):
            (recon / name).write_text('/* test */', encoding='utf-8')
    return root


def _minimal_pass_test(test_id: str, status: str = 'pass') -> dict:
    return {
        'test_id': test_id,
        'description': test_id,
        'input_values': {},
        'original': {'origin': 'http://127.0.0.1:8001', 'observed_state': {}, 'screenshot': None, 'error': None},
        'reconstruction': {'origin': 'http://127.0.0.1:8002', 'observed_state': {}, 'screenshot': None, 'error': None},
        'status': status,
        'differences': [] if status == 'pass' else ['diff'],
        'evidence_refs': [],
        'error': None,
    }


def test_valid_supporting_evidence_reload_on_recorded_taskboard():
    job = _first_taskboard_job()
    inv = json.loads((ARTIFACTS / job / 'investigation' / 'report.json').read_text(encoding='utf-8'))
    status, supporting, contrad, scope, limitations = check_reload_persistence_predicates(inv)
    assert status == VerificationStatus.verified
    assert any('reload' in r.ref_id for r in supporting)
    assert any('create' in r.ref_id for r in supporting)
    assert 'single' in scope.lower() or 'reload' in scope.lower()
    assert any('permanent' in lim.lower() or 'database' in lim.lower() or 'durable' in lim.lower() for lim in limitations)


def test_missing_evidence_yields_not_verified(tmp_path: Path):
    job_id = 'a' * 32
    _write_job(
        tmp_path,
        job_id,
        final={'id': job_id, 'status': 'incomplete', 'mode': 'scripted', 'target_id': 'taskboard', 'stages': {}},
        investigation={
            'target_id': 'taskboard',
            'feature': 'TaskBoard',
            'mode': 'scripted',
            'status': 'incomplete',
            'events': [],
            'objectives': {},
        },
        recon_files=False,
    )
    results = build_verified_results(tmp_path, job_id)
    reload_findings = [f for f in results.verified_findings + results.partially_verified_findings + results.unsupported_findings if f.rule_id == 'rule.reload_persistence']
    assert reload_findings
    assert reload_findings[0].verification_status in (
        VerificationStatus.not_verified,
        VerificationStatus.partially_verified,
    )


def test_invalid_evidence_references_do_not_verify_by_existence(tmp_path: Path):
    job_id = 'b' * 32
    _write_job(
        tmp_path,
        job_id,
        final={'id': job_id, 'status': 'completed', 'mode': 'scripted', 'target_id': 'taskboard', 'stages': {}},
        investigation={
            'target_id': 'taskboard',
            'feature': 'TaskBoard',
            'mode': 'scripted',
            'status': 'completed',
            'events': [
                {
                    'step': 1,
                    'status': 'ok',
                    'decision': {'action': 'reload', 'reason': 'no prior create'},
                    'before': {'visible_text': 'empty'},
                    'after': {'visible_text': 'empty'},
                }
            ],
            'objectives': {
                'reload_persistence': {
                    'supported': True,
                    'evidence': 'fabricated reference without create predicate',
                    'task_name': 'Ghost Task',
                }
            },
        },
    )
    inv = json.loads((tmp_path / job_id / 'investigation' / 'report.json').read_text(encoding='utf-8'))
    status, supporting, contrad, *_ = check_reload_persistence_predicates(inv)
    assert status != VerificationStatus.verified
    assert contrad or status in (VerificationStatus.partially_verified, VerificationStatus.not_verified, VerificationStatus.contradicted)


def test_contradictory_test_outcomes(tmp_path: Path):
    job_id = 'c' * 32
    validation = {
        'tests': [
            _minimal_pass_test('t1', 'pass'),
            _minimal_pass_test('t2', 'fail'),
        ],
        'passed': 2,  # lies — only one pass
        'failed': 0,
        'invalid': 0,
        'total_valid': 2,
        'behavioral_match_rate_percent': 100.0,
    }
    status, stats, _sup, contrad, *_ = check_validation_pass_count(validation, asserted_count=2)
    assert stats['passed'] == 1
    assert status == VerificationStatus.contradicted
    assert contrad


def test_incorrect_pass_counts_contradicted(tmp_path: Path):
    job_id = 'd' * 32
    validation = {
        'tests': [_minimal_pass_test('a'), _minimal_pass_test('b'), _minimal_pass_test('c'), _minimal_pass_test('d')],
        'passed': 4,
        'failed': 0,
        'invalid': 0,
        'total_valid': 4,
        'behavioral_match_rate_percent': 100.0,
    }
    _write_job(
        tmp_path,
        job_id,
        final={
            'id': job_id,
            'status': 'completed',
            'mode': 'scripted',
            'target_id': 'taskboard',
            'stages': {'validation': {'executed': True, 'status': 'completed', 'passed': 5}},
        },
        investigation={'target_id': 'taskboard', 'feature': 'x', 'mode': 'scripted', 'events': [], 'objectives': {}},
        validation=validation,
    )
    results = build_verified_results(tmp_path, job_id)
    assert any(c.contradiction_id == 'val-pass-count-mismatch' for c in results.contradictions)
    finding = verify_structured_claim(
        load_artifact_bundle(tmp_path, job_id),
        StructuredClaim(claim_type='validation_pass_count', asserted_pass_count=5, claim_text='Five tests passed'),
    )
    assert finding.verification_status == VerificationStatus.contradicted


def test_overgeneralized_claims_never_verified(tmp_path: Path):
    job_id = 'e' * 32
    _write_job(
        tmp_path,
        job_id,
        final={'id': job_id, 'status': 'completed', 'mode': 'scripted', 'target_id': 'taskboard', 'stages': {}},
        investigation={'target_id': 'taskboard', 'feature': 'x', 'mode': 'scripted', 'events': [], 'objectives': {}},
        validation={
            'tests': [_minimal_pass_test(f't{i}') for i in range(5)],
            'passed': 5,
            'failed': 0,
            'invalid': 0,
            'total_valid': 5,
            'behavioral_match_rate_percent': 100.0,
        },
    )
    bundle = load_artifact_bundle(tmp_path, job_id)
    for ctype in (
        'permanent_persistence',
        'universal_behavioral_equivalence',
        'bug_free_reconstruction',
        'storage_postgres',
        'original_app_defective',
    ):
        finding = verify_structured_claim(bundle, StructuredClaim(claim_type=ctype))
        assert finding.verification_status == VerificationStatus.not_verified, ctype


def test_incomplete_investigation(tmp_path: Path):
    job_id = 'f' * 32
    _write_job(
        tmp_path,
        job_id,
        final={'id': job_id, 'status': 'incomplete', 'mode': 'scripted', 'target_id': 'taskboard', 'stages': {}},
        investigation={
            'target_id': 'taskboard',
            'feature': 'x',
            'mode': 'scripted',
            'status': 'incomplete',
            'events': [],
            'objectives': {},
        },
        recon_files=False,
    )
    results = build_verified_results(tmp_path, job_id)
    assert results.availability in ('partial', 'complete')
    assert any(p.category == ProblemCategory.investigation_limitation for p in results.problems)


def test_failed_reconstruction(tmp_path: Path):
    job_id = '1' * 32
    _write_job(
        tmp_path,
        job_id,
        final={
            'id': job_id,
            'status': 'failed',
            'mode': 'scripted',
            'target_id': 'taskboard',
            'stages': {'reconstruction': {'executed': True, 'status': 'error'}},
        },
        investigation={'target_id': 'taskboard', 'feature': 'x', 'mode': 'scripted', 'events': [], 'objectives': {}},
        recon_files=False,
    )
    results = build_verified_results(tmp_path, job_id)
    assert any(p.category == ProblemCategory.reconstruction_generation_failure for p in results.problems)


def test_failed_validation_counts_as_mismatch_not_original_defect(tmp_path: Path):
    job_id = '2' * 32
    _write_job(
        tmp_path,
        job_id,
        final={'id': job_id, 'status': 'completed', 'mode': 'scripted', 'target_id': 'taskboard', 'stages': {}},
        investigation={'target_id': 'taskboard', 'feature': 'x', 'mode': 'scripted', 'events': [], 'objectives': {}},
        validation={
            'tests': [_minimal_pass_test('t1', 'pass'), _minimal_pass_test('t2', 'fail')],
            'passed': 1,
            'failed': 1,
            'invalid': 0,
            'total_valid': 2,
            'behavioral_match_rate_percent': 50.0,
        },
    )
    results = build_verified_results(tmp_path, job_id)
    assert any(p.category == ProblemCategory.reconstruction_mismatch for p in results.problems)
    assert all(p.category != ProblemCategory.confirmed_original_defect for p in results.problems)
    original = [f for f in results.unsupported_findings if f.claim_category == ClaimCategory.original_defect]
    assert original
    assert original[0].verification_status == VerificationStatus.not_verified


def test_successful_repair_verified(tmp_path: Path):
    job_id = '3' * 32
    repair = {
        'evaluation_kind': 'pipeline_repair',
        'label': 'Pipeline repair',
        'target_id': 'calculator',
        'max_attempts': 2,
        'initial_match_rate_percent': 60.0,
        'final_match_rate_percent': 100.0,
        'initial_failed': ['calc_addition'],
        'attempts': [
            {
                'attempt': 1,
                'failed_scenarios_addressed': ['calc_addition'],
                'meta_api_requests': 1,
                'changed_files': ['script.js'],
                'validation_artifact': 'repair/attempt_1/validation/validation_results.json',
                'prior_match_rate_percent': 60.0,
                'new_match_rate_percent': 100.0,
                'newly_passed_tests': ['calc_addition'],
                'regressed_tests': [],
                'remaining_failures': [],
                'status': 'perfect',
                'accepted_as_best': True,
            }
        ],
        'best_match_rate_percent': 100.0,
        'meta_api_requests_total': 1,
        'stopped_reason': 'all_valid_tests_passed',
        'original_fixture_untouched': True,
        'notes': [],
    }
    status, support, contrad, *_rest = check_repair_outcome(repair)
    assert status == VerificationStatus.verified
    assert support
    assert not contrad


def test_unsuccessful_repair_not_verified_as_success(tmp_path: Path):
    repair = {
        'evaluation_kind': 'pipeline_repair',
        'label': 'Pipeline repair',
        'target_id': 'calculator',
        'max_attempts': 1,
        'initial_match_rate_percent': 50.0,
        'final_match_rate_percent': 50.0,
        'initial_failed': ['x'],
        'attempts': [
            {
                'attempt': 1,
                'failed_scenarios_addressed': ['x'],
                'status': 'unchanged',
                'prior_match_rate_percent': 50.0,
                'new_match_rate_percent': 50.0,
                'validation_artifact': 'repair/attempt_1/validation/validation_results.json',
                'accepted_as_best': False,
            }
        ],
        'stopped_reason': 'max_attempts',
        'meta_api_requests_total': 1,
        'notes': [],
    }
    status, *_ = check_repair_outcome(repair)
    assert status != VerificationStatus.verified


def test_repair_success_claim_without_revalidation_contradicted():
    repair = {
        'evaluation_kind': 'pipeline_repair',
        'label': 'Pipeline repair',
        'target_id': 'calculator',
        'max_attempts': 1,
        'initial_match_rate_percent': 40.0,
        'final_match_rate_percent': 100.0,
        'attempts': [
            {
                'attempt': 1,
                'status': 'perfect',
                'accepted_as_best': False,
                # no validation_artifact, no new_match_rate_percent
            }
        ],
        'stopped_reason': 'all_valid_tests_passed',
        'notes': [],
    }
    status, _s, contrad, *_ = check_repair_outcome(repair)
    assert status == VerificationStatus.contradicted
    assert contrad


def test_unsupported_storage_implementation_claim():
    job = _first_taskboard_job()
    results = build_verified_results(ARTIFACTS, job)
    storage = [f for f in results.unsupported_findings if f.claim_category == ClaimCategory.storage_implementation]
    assert storage
    assert all(f.verification_status == VerificationStatus.not_verified for f in storage)


def test_scope_limitations_present_on_recorded_job():
    job = _first_taskboard_job()
    results = build_verified_results(ARTIFACTS, job)
    assert results.coverage_limitations
    assert results.untested_behaviors
    verified_reload = [f for f in results.verified_findings if f.rule_id == 'rule.reload_persistence']
    if verified_reload:
        assert verified_reload[0].limitations
        assert 'PostgreSQL' not in verified_reload[0].claim_text


def test_missing_timestamps_still_produce_findings(tmp_path: Path):
    job_id = '4' * 32
    _write_job(
        tmp_path,
        job_id,
        final={'id': job_id, 'status': 'completed', 'mode': 'scripted', 'target_id': 'taskboard', 'stages': {}},
        investigation={'target_id': 'taskboard', 'feature': 'x', 'mode': 'scripted', 'events': [], 'objectives': {}},
        validation={
            'tests': [_minimal_pass_test('only')],
            'passed': 1,
            'failed': 0,
            'invalid': 0,
            'total_valid': 1,
            'behavioral_match_rate_percent': 100.0,
        },
    )
    results = build_verified_results(tmp_path, job_id)
    assert results.verified_findings or results.partially_verified_findings
    # timestamps may be empty lists — allowed
    assert all(isinstance(f.timestamps, list) for f in results.verified_findings)


def test_no_available_test_results(tmp_path: Path):
    job_id = '5' * 32
    _write_job(
        tmp_path,
        job_id,
        final={'id': job_id, 'status': 'completed', 'mode': 'scripted', 'target_id': 'taskboard', 'stages': {}},
        investigation={'target_id': 'taskboard', 'feature': 'x', 'mode': 'scripted', 'events': [], 'objectives': {}},
    )
    results = build_verified_results(tmp_path, job_id)
    assert results.validation_summary is None
    assert results.availability == 'partial'
    assert not any(f.rule_id == 'rule.validation_pass_count' and f.verification_status == VerificationStatus.verified for f in results.verified_findings)


def test_muse_claim_against_scripted_job_contradicted():
    job = _first_taskboard_job()
    bundle = load_artifact_bundle(ARTIFACTS, job)
    finding = verify_structured_claim(
        bundle,
        StructuredClaim(claim_type='muse_fresh_investigation', claim_text='Muse performed a fresh investigation'),
    )
    if (bundle.investigation_report or {}).get('mode') == 'scripted':
        assert finding.verification_status == VerificationStatus.contradicted


def test_invalid_tests_not_counted_as_passes():
    validation = {
        'tests': [
            _minimal_pass_test('ok', 'pass'),
            _minimal_pass_test('bad', 'invalid'),
        ],
        'passed': 2,
        'failed': 0,
        'invalid': 0,
        'total_valid': 1,
        'behavioral_match_rate_percent': 100.0,
    }
    status, stats, _s, contrad, *_ = check_validation_pass_count(validation)
    assert stats['passed'] == 1
    assert stats['invalid'] == 1
    assert status == VerificationStatus.contradicted
    assert contrad


def test_api_verified_findings_for_recorded_job():
    job = _first_taskboard_job()
    response = client.get(f'/api/investigations/{job}/verified-findings')
    assert response.status_code == 200
    body = response.json()
    assert body['investigation_id'] == job
    assert body['availability'] in ('complete', 'partial')
    assert 'verified_findings' in body
    assert 'unsupported_findings' in body
    assert 'coverage_limitations' in body
    # No absolute Windows secrets paths required in evidence locations
    blob = json.dumps(body)
    assert '.env' not in blob


def test_api_verified_findings_invalid_id():
    response = client.get('/api/investigations/../secrets/verified-findings')
    assert response.status_code in (400, 404, 422)


def test_api_verified_findings_missing_job():
    response = client.get('/api/investigations/' + ('a' * 32) + '/verified-findings')
    assert response.status_code == 404


def test_copy_real_job_preserves_partial_vs_full_buckets():
    job = _first_taskboard_job()
    results = build_verified_results(ARTIFACTS, job)
    # Shared object: same conclusions, partitioned by status only
    all_ids = {f.claim_id for f in (
        results.verified_findings
        + results.partially_verified_findings
        + results.unsupported_findings
        + results.contradicted_findings
        + results.requires_review_findings
    )}
    assert len(all_ids) == (
        len(results.verified_findings)
        + len(results.partially_verified_findings)
        + len(results.unsupported_findings)
        + len(results.contradicted_findings)
        + len(results.requires_review_findings)
    )
    assert any(f.rule_id == 'rule.reject_universal_equivalence' for f in results.unsupported_findings)


def test_controlled_repair_demo_file_if_present():
    path = ARTIFACTS / 'phase5c' / 'controlled_repair_eval' / 'repair' / 'repair_report.json'
    if not path.is_file():
        pytest.skip('Controlled repair demo artifact not present')
    repair = json.loads(path.read_text(encoding='utf-8'))
    status, support, contrad, scope, limitations, summary = check_repair_outcome(repair)
    assert status == VerificationStatus.verified
    assert summary.get('evaluation_kind') == 'controlled_fault_injection'
    assert 'controlled' in ' '.join(limitations).lower() or 'fault' in ' '.join(limitations).lower()
