"""Unit tests for calculator objective evaluation (no live Meta calls)."""
from reversex.run import evaluate_calculator_objectives, finalize_status
from reversex.targets import get_target


def _event(step, action, *, value=None, element_id=None, label='', before='', after='', fills_before=None):
    elements = []
    if element_id:
        elements.append({'element_id': element_id, 'kind': 'button', 'label': label})
    return {
        'step': step,
        'status': 'ok',
        'decision': {
            'action': action,
            'element_id': element_id,
            'value': value,
            'reason': 'test',
        },
        'before': {'visible_text': before, 'elements': elements},
        'after': {'visible_text': after, 'elements': elements},
    }


def test_calculator_empty_and_add_objectives():
    events = [
        _event(1, 'click', element_id='s1_e2', label='Add', before='MiniCalc', after='Both numbers are required.\nResult\n'),
        _event(2, 'fill', element_id='s2_e0', value='12', after='12'),
        _event(3, 'fill', element_id='s3_e1', value='5', after='12\n5'),
        _event(4, 'click', element_id='s4_e2', label='Add', before='12\n5\nResult', after='12\n5\nResult\n17'),
        _event(5, 'fill', element_id='s5_e0', value='9', after='9'),
        _event(6, 'fill', element_id='s6_e1', value='3', after='9\n3'),
        _event(7, 'click', element_id='s7_e3', label='Subtract', before='9\n3', after='9\n3\nResult\n6'),
        _event(8, 'click', element_id='s8_e4', label='Reset', before='9\n3\nResult\n6', after='MiniCalc\nResult\n'),
    ]
    objectives = evaluate_calculator_objectives(events)
    assert objectives['empty_input_handling']['supported'] is True
    assert objectives['addition_operation']['supported'] is True
    assert objectives['subtraction_operation']['supported'] is True
    assert objectives['reset_behavior']['supported'] is True
    target = get_target('calculator')
    status = finalize_status(
        events=events,
        objectives=objectives,
        stopped=True,
        budget_hit=False,
        errored=False,
        objective_keys=target.objective_keys,
    )
    assert status == 'completed'


def test_calculator_target_origin():
    t = get_target('calculator')
    assert t.origin.endswith(':8003')
    assert t.validation_suite == 'calculator'
    assert 'fixtures/calculator' in t.excluded_from_model_context[0] or any(
        'fixtures/calculator' in x for x in t.excluded_from_model_context
    )
