"""Focused unit tests for bounded repair (no live Meta calls)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from reversex.reconstruct import validate_reconstruction_response
from reversex.repair import (
    MAX_REPAIR_ATTEMPTS,
    FailedScenario,
    RepairReport,
    assert_repair_context_safe,
    build_repair_model_context,
    calculate_improvement,
    collect_failed_scenarios,
    introduce_controlled_defect,
    read_reconstruction_files,
)
from reversex.spec import BehaviorSpec, BehaviorRequirement, EvidenceKind, EvidenceRef
from reversex.targets import get_target


def _minimal_frozen_spec() -> BehaviorSpec:
    return BehaviorSpec(
        source_report='artifacts/test/report.json',
        source_report_sha256='a' * 64,
        feature='MiniCalc visible arithmetic behavior',
        status='frozen',
        requirements=[
            BehaviorRequirement(
                id='REQ-CALC-ADD',
                kind=EvidenceKind.OBSERVATION,
                feature='calculator_addition',
                preconditions=['two numbers'],
                action_performed='click Add',
                input_values={'num_a': '2', 'num_b': '3'},
                observed_result='Result showed 5',
                evidence=[EvidenceRef(report_path='r', step=4, note='add')],
            ),
        ],
        excluded_from_model_context=['fixtures/calculator/**', 'sample_app/**'],
    )


def test_collect_failed_scenarios_ignores_pass_and_invalid():
    payload = {
        'tests': [
            {'test_id': 'a', 'status': 'pass', 'differences': []},
            {'test_id': 'b', 'status': 'invalid', 'differences': ['x']},
            {
                'test_id': 'c',
                'status': 'fail',
                'description': 'add',
                'differences': ['result_text original=5 reconstruction=6'],
                'input_values': {'num_a': '2', 'num_b': '3'},
                'original': {'observed_state': {'result_text': '5'}},
                'reconstruction': {'observed_state': {'result_text': '6'}},
            },
        ],
    }
    failed = collect_failed_scenarios(payload)
    assert len(failed) == 1
    assert failed[0].test_id == 'c'
    assert failed[0].original_observed['result_text'] == '5'


def test_improvement_and_regression_detection():
    prior = {
        'behavioral_match_rate_percent': 60.0,
        'tests': [
            {'test_id': 't1', 'status': 'pass'},
            {'test_id': 't2', 'status': 'fail'},
            {'test_id': 't3', 'status': 'fail'},
        ],
    }
    new = {
        'behavioral_match_rate_percent': 80.0,
        'tests': [
            {'test_id': 't1', 'status': 'fail'},
            {'test_id': 't2', 'status': 'pass'},
            {'test_id': 't3', 'status': 'fail'},
        ],
    }
    newly, regressed, remaining, prior_rate, new_rate = calculate_improvement(prior=prior, new=new)
    assert newly == ['t2']
    assert regressed == ['t1']
    assert remaining == ['t1', 't3']
    assert prior_rate == 60.0 and new_rate == 80.0


def test_repair_attempt_limit_constant():
    assert MAX_REPAIR_ATTEMPTS == 2


def test_unsafe_output_filename_rejected():
    with pytest.raises(ValueError):
        validate_reconstruction_response({
            'files': [
                {'filename': '../evil.js', 'content': 'x'},
                {'filename': 'style.css', 'content': 'y'},
                {'filename': 'script.js', 'content': 'z'},
            ],
            'notes': 'bad',
        })


def test_invalid_model_response_rejected():
    with pytest.raises(ValueError):
        validate_reconstruction_response({'files': [], 'notes': 'empty'})


def test_repair_context_rejects_original_markers():
    spec = _minimal_frozen_spec()
    ctx = build_repair_model_context(
        frozen_spec=spec,
        current_files={
            'index.html': '<html></html>',
            'style.css': 'body{}',
            'script.js': 'console.log(1)',
        },
        failures=[
            FailedScenario(
                test_id='calc_addition',
                description='add',
                differences=['result mismatch'],
                original_observed={'result_text': '5'},
                reconstruction_observed={'result_text': '6'},
            ),
        ],
    )
    assert_repair_context_safe(ctx)
    poisoned = dict(ctx)
    poisoned['failed_scenarios'] = [
        {'test_id': 'x', 'description': 'reversex_fixture_tasks_v1 leak'},
    ]
    with pytest.raises(RuntimeError):
        assert_repair_context_safe(poisoned)


def test_candidate_version_dirs_preserved(tmp_path: Path):
    src = tmp_path / 'good'
    src.mkdir()
    (src / 'index.html').write_text('<html>ok</html>', encoding='utf-8')
    (src / 'style.css').write_text('body{}', encoding='utf-8')
    (src / 'script.js').write_text('function add(a,b){return a+b}', encoding='utf-8')
    dest = tmp_path / 'defective'
    note = introduce_controlled_defect(src, dest)
    assert note['defect_id']
    assert (src / 'script.js').read_text(encoding='utf-8') == 'function add(a,b){return a+b}'
    assert 'CONTROLLED_DEFECT' in (dest / 'script.js').read_text(encoding='utf-8')
    assert (dest / 'CONTROLLED_DEFECT.json').is_file()
    files = read_reconstruction_files(dest)
    assert set(files) == {'index.html', 'style.css', 'script.js'}


def test_repair_report_status_shape():
    report = RepairReport(
        evaluation_kind='controlled_fault_injection',
        label='Controlled Repair Evaluation',
        target_id='calculator',
        initial_match_rate_percent=80.0,
        final_match_rate_percent=100.0,
        stopped_reason='all_valid_tests_passed',
    )
    dumped = report.model_dump(mode='json')
    assert dumped['evaluation_kind'] == 'controlled_fault_injection'
    assert dumped['max_attempts'] == 2


def test_api_targets_only_allowlisted():
    ids = {t.id for t in [get_target('taskboard'), get_target('calculator')]}
    assert ids == {'taskboard', 'calculator'}
    with pytest.raises(ValueError):
        get_target('https://evil.example')
