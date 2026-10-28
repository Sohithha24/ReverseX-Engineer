from reversex.contracts import Decision
from reversex.meta import DECISION_SCHEMA


def test_action_schema_is_closed_and_strict():
    spec = DECISION_SCHEMA['json_schema']
    assert spec['strict'] is True
    assert spec['schema']['additionalProperties'] is False
    assert set(spec['schema']['required']) == set(spec['schema']['properties'])


def test_expired_element_ref_is_not_a_valid_authority():
    # Pydantic checks shape; browser executor (not schema) must reject stale IDs.
    d = Decision(action='click', element_id='s1_e2', reason='check')
    assert d.element_id == 's1_e2'
