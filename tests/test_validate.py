import json
from pathlib import Path

import pytest

from reversex.browser import validate_target
from reversex.validate import (
    BehavioralCaseResult,
    ObservedState,
    SideObservation,
    build_observed_state,
    calculate_match_rate,
    compare_observed_states,
    make_holdout_values,
)


def test_normalize_and_extract_validation():
    state = build_observed_state(
        'TaskBoard\nTask name is required.\nNo tasks yet.',
        expected_tasks=[],
    )
    assert state.validation_error_present is True
    assert state.validation_message_normalized == 'task name is required'
    assert state.empty_state_visible is True


def test_task_visibility_holdout():
    state = build_observed_state('Your tasks\nHoldout Briefing abcd\n', expected_tasks=['Holdout Briefing abcd'])
    assert state.task_visible is True
    assert state.tasks_visible == ['Holdout Briefing abcd']
    assert state.empty_state_visible is False


def test_compare_pass_and_fail():
    a = ObservedState(
        task_visible=True,
        tasks_visible=['T'],
        validation_error_present=False,
        validation_message_normalized=None,
        empty_state_visible=False,
    )
    b = a.model_copy()
    assert compare_observed_states(a, b, compare_tasks=True) == []
    c = a.model_copy(update={'task_visible': False, 'tasks_visible': []})
    diffs = compare_observed_states(a, c, compare_tasks=True)
    assert diffs


def test_match_rate_excludes_invalid():
    results = [
        BehavioralCaseResult(
            test_id='a', description='d', input_values={},
            original=SideObservation(origin='o', observed_state=ObservedState()),
            reconstruction=SideObservation(origin='r', observed_state=ObservedState()),
            status='pass',
        ),
        BehavioralCaseResult(
            test_id='b', description='d', input_values={},
            original=SideObservation(origin='o', observed_state=ObservedState()),
            reconstruction=SideObservation(origin='r', observed_state=ObservedState()),
            status='fail',
        ),
        BehavioralCaseResult(
            test_id='c', description='d', input_values={},
            original=SideObservation(origin='o', observed_state=ObservedState(), error='oracle down'),
            reconstruction=SideObservation(origin='r', observed_state=ObservedState()),
            status='invalid',
            error='oracle down',
        ),
    ]
    total_valid, passed, failed, invalid, rate = calculate_match_rate(results)
    assert (total_valid, passed, failed, invalid) == (2, 1, 1, 1)
    assert rate == 50.0


def test_match_rate_unavailable_when_no_valid_tests():
    total_valid, passed, failed, invalid, rate = calculate_match_rate([])
    assert total_valid == 0
    assert rate is None


def test_holdouts_are_fresh_and_not_phase2_spec_values():
    a = make_holdout_values()
    b = make_holdout_values()
    assert a['task_a'] != b['task_a']
    assert 'Review PR' not in a['task_a']
    assert a['whitespace'].strip() == ''


def test_missing_elements_surface_as_errors_in_state_builder_path():
    # Without expected tasks, missing names yield empty visibility list.
    state = build_observed_state('TaskBoard only', expected_tasks=['Missing Task'])
    assert state.task_visible is False
    assert state.tasks_visible == []


def test_reconstruction_origin_isolation_contract():
    # Validator uses separate allowlisted origins; cross-origin must be rejected.
    validate_target('http://127.0.0.1:8002/', 'http://127.0.0.1:8002')
    with pytest.raises(ValueError):
        validate_target('http://127.0.0.1:8001/', 'http://127.0.0.1:8002')
    with pytest.raises(ValueError):
        validate_target('https://api.meta.ai/v1/chat/completions', 'http://127.0.0.1:8002')


def test_validation_report_schema_roundtrip(tmp_path: Path):
    from reversex.validate import ValidationReport

    report = ValidationReport(
        original_origin='http://127.0.0.1:8001',
        reconstruction_origin='http://127.0.0.1:8002',
        isolation={'status': 'running'},
        holdout_values={'task_a': 'X'},
        tests=[],
        total_valid=0,
        passed=0,
        failed=0,
        invalid=0,
        behavioral_match_rate_percent=None,
        notes=['blocked'],
    )
    path = tmp_path / 'validation_results.json'
    path.write_text(json.dumps(report.model_dump(mode='json'), indent=2), encoding='utf-8')
    loaded = ValidationReport.model_validate_json(path.read_text(encoding='utf-8'))
    assert loaded.behavioral_match_rate_percent is None
    assert loaded.meta_api_requests == 0
