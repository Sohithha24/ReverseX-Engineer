"""Focused tests for Phase 1b investigation status and observation-backed objectives."""
from reversex.run import evaluate_objectives, finalize_status


def _ok_event(step, action, *, value=None, element_id=None, before='', after=''):
    decision = {'action': action, 'element_id': element_id, 'value': value, 'reason': 'test'}
    return {
        'step': step,
        'status': 'ok',
        'decision': decision,
        'before': {'visible_text': before, 'elements': []},
        'after': {'visible_text': after, 'elements': []} if action != 'stop' else None,
    }


def test_objectives_require_observed_validation_and_persistence():
    events = [
        _ok_event(1, 'fill', value='', element_id='s1_e0', after='No tasks yet.'),
        _ok_event(
            2, 'click', element_id='s1_e1',
            before='No tasks yet.',
            after='Task name is required.\nNo tasks yet.',
        ),
        _ok_event(3, 'fill', value='Review PR', element_id='s2_e0', after='Task name is required.'),
        _ok_event(
            4, 'click', element_id='s3_e1',
            before='Task name is required.',
            after='Your tasks\nReview PR',
        ),
        _ok_event(
            5, 'reload',
            before='Your tasks\nReview PR',
            after='Your tasks\nReview PR',
        ),
        _ok_event(6, 'stop'),
    ]
    objectives = evaluate_objectives(events)
    assert objectives['empty_task_submission']['supported'] is True
    assert objectives['valid_task_submission']['supported'] is True
    assert objectives['valid_task_submission']['task_name'] == 'Review PR'
    assert objectives['reload_persistence']['supported'] is True


def test_stop_without_full_evidence_is_incomplete_not_completed():
    events = [
        _ok_event(
            1, 'click', element_id='s1_e1',
            before='No tasks yet.',
            after='Task name is required.\nNo tasks yet.',
        ),
        _ok_event(2, 'stop'),
    ]
    objectives = evaluate_objectives(events)
    status = finalize_status(
        events=events, objectives=objectives, stopped=True, budget_hit=False, errored=False,
    )
    assert objectives['empty_task_submission']['supported'] is True
    assert objectives['valid_task_submission']['supported'] is False
    assert status == 'incomplete'


def test_budget_exhausted_status_when_limit_hit():
    objectives = {
        'empty_task_submission': {'supported': True, 'evidence': 'x'},
        'valid_task_submission': {'supported': True, 'evidence': 'x', 'task_name': 'T'},
        'reload_persistence': {'supported': False, 'evidence': None, 'task_name': None},
    }
    status = finalize_status(
        events=[], objectives=objectives, stopped=False, budget_hit=True, errored=False,
    )
    assert status == 'budget_exhausted'


def test_execution_error_status_preserved():
    objectives = {
        'empty_task_submission': {'supported': False, 'evidence': None},
        'valid_task_submission': {'supported': False, 'evidence': None, 'task_name': None},
        'reload_persistence': {'supported': False, 'evidence': None, 'task_name': None},
    }
    status = finalize_status(
        events=[{'step': 1, 'status': 'error', 'error': 'expired'}],
        objectives=objectives,
        stopped=False,
        budget_hit=False,
        errored=True,
    )
    assert status == 'error'


def test_completed_only_when_stop_and_all_objectives_supported():
    objectives = {
        'empty_task_submission': {'supported': True, 'evidence': 'e'},
        'valid_task_submission': {'supported': True, 'evidence': 'e', 'task_name': 'Review PR'},
        'reload_persistence': {'supported': True, 'evidence': 'e', 'task_name': 'Review PR'},
    }
    assert finalize_status(
        events=[], objectives=objectives, stopped=True, budget_hit=False, errored=False,
    ) == 'completed'
    assert finalize_status(
        events=[], objectives=objectives, stopped=False, budget_hit=True, errored=False,
    ) == 'budget_exhausted'


def test_valid_submission_not_inferred_from_empty_click_alone():
    events = [
        _ok_event(
            1, 'click', element_id='s1_e1',
            before='No tasks yet.',
            after='Task name is required.\nNo tasks yet.',
        ),
    ]
    objectives = evaluate_objectives(events)
    assert objectives['valid_task_submission']['supported'] is False
    assert objectives['reload_persistence']['supported'] is False
