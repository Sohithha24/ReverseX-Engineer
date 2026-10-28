import pytest
from pydantic import ValidationError
from reversex.contracts import Decision
from reversex.browser import validate_target


def test_valid_empty_fill():
    d = Decision(action='fill', element_id='s1_e0', value='', reason='Test empty input')
    assert d.value == ''


@pytest.mark.parametrize('payload', [
    {'action': 'shell', 'reason': 'unsafe'},
    {'action': 'click', 'reason': 'missing element'},
    {'action': 'fill', 'element_id': 's1_e0', 'reason': 'missing value'},
    {'action': 'observe', 'element_id': 's1_e0', 'reason': 'incorrect target'},
    {'action': 'click', 'element_id': 's1_e1', 'value': 'X', 'reason': 'unexpected value'},
    {'action': 'stop', 'reason': 'done', 'unknown': True},
])
def test_invalid_actions_rejected(payload):
    with pytest.raises(ValidationError):
        Decision.model_validate(payload)


@pytest.mark.parametrize('url', [
    'https://127.0.0.1:8001/',
    'http://example.com:8001/',
    'http://127.0.0.1:9000/',
    'file:///etc/passwd',
    'http://127.0.0.1:8001@evil.test/',
    'http://127.0.0.1:8001/#fragment',
])
def test_outside_origins_blocked(url):
    with pytest.raises(ValueError):
        validate_target(url, 'http://127.0.0.1:8001')


def test_approved_local_origin():
    validate_target('http://127.0.0.1:8001/index.html', 'http://127.0.0.1:8001')
