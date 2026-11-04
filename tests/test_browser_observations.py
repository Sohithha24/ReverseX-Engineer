"""Generic SafeBrowser observation / privacy / Muse-handling tests (no live Meta calls)."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from reversex.browser import (
    SafeBrowser,
    diff_control_values,
    looks_sensitive_identifier,
    redact_if_sensitive_value,
    validate_target,
)
from reversex.contracts import Decision, PageSnapshot, VisibleElement
from reversex import browser as browser_mod
from reversex.meta import (
    MuseDecisionError,
    MusePlanner,
    extract_decision_payload,
    normalize_decision_dict,
    sanitize_muse_diagnostics,
)
from reversex.run import evaluate_generic_feature_objectives
from reversex.verification import VerificationStatus, build_verified_results

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'fixtures' / 'observation_lab'


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def observation_lab(monkeypatch):
    port = _free_port()
    monkeypatch.setattr(
        browser_mod,
        'ALLOWED_LOCAL_PORTS',
        frozenset(set(browser_mod.ALLOWED_LOCAL_PORTS) | {port}),
    )
    process = subprocess.Popen(
        [sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', str(LAB)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    origin = f'http://127.0.0.1:{port}'
    try:
        for _ in range(50):
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1', port)) == 0:
                    break
            time.sleep(0.05)
        else:
            pytest.skip('observation lab server did not start')
        yield origin
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_privacy_helpers():
    assert looks_sensitive_identifier('api_key')
    assert looks_sensitive_identifier('Session Token')
    val, redacted = redact_if_sensitive_value('Bearer abcdefghijklmnop')
    assert redacted and val == '[REDACTED]'
    val2, redacted2 = redact_if_sensitive_value('Hello World')
    assert not redacted2 and val2 == 'Hello World'


def test_observation_lab_captures_reactive_textarea_values(observation_lab):
    with SafeBrowser(observation_lab) as browser:
        snap = browser.goto(observation_lab + '/')
        notes = next(
            e for e in snap.elements if e.kind == 'textarea' and 'Notes' in ((e.placeholder or '') + (e.label or ''))
        )
        assert notes.value in (None, '')
        after = browser.act(
            Decision(action='fill', element_id=notes.element_id, value='Hello World', reason='lab fill')
        )
        assert after is not None
        notes_after = next(
            e for e in after.elements if e.kind == 'textarea' and 'Notes' in ((e.placeholder or '') + (e.label or ''))
        )
        result = next(
            e for e in after.elements if e.kind == 'textarea' and 'Result' in ((e.placeholder or '') + (e.label or ''))
        )
        assert notes_after.value == 'Hello World'
        assert result.value == 'OUT:Hello World'
        assert any(c.field == 'value' and c.after == 'OUT:Hello World' for c in after.control_changes)
        # Password values must not be captured.
        secret = next(e for e in after.elements if e.input_type == 'password')
        assert secret.value is None
        assert secret.value_redacted is True
        disabled = next(e for e in after.elements if e.disabled and e.kind == 'input')
        assert disabled.disabled is True
        readonly = next(e for e in after.elements if e.readonly and e.kind == 'input')
        assert readonly.value == 'fixed'


def test_select_and_checkbox_observations(observation_lab):
    with SafeBrowser(observation_lab) as browser:
        snap = browser.goto(observation_lab + '/')
        choice = next(e for e in snap.elements if e.kind == 'select')
        assert choice.selected in ('a', 'Alpha', 'a') or choice.selected == 'a'
        tog = next(e for e in snap.elements if e.input_type == 'checkbox')
        assert tog.checked is False
        after = browser.act(Decision(action='click', element_id=tog.element_id, reason='toggle'))
        tog2 = next(e for e in after.elements if e.input_type == 'checkbox')
        assert tog2.checked is True
        assert any(c.field == 'checked' for c in after.control_changes)


def test_same_origin_link_click(observation_lab):
    with SafeBrowser(observation_lab) as browser:
        snap = browser.goto(observation_lab + '/')
        link = next((e for e in snap.elements if e.kind == 'a' and e.href), None)
        assert link is not None
        after = browser.act(Decision(action='click', element_id=link.element_id, reason='nav'))
        assert after is not None
        validate_target(after.url, observation_lab)


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(('127.0.0.1', port)) == 0


@pytest.mark.skipif(not _port_open(8010), reason='IT-Tools not running on :8010')
def test_it_tools_reactive_output_captured_without_hardcoding():
    """Evaluator-controlled: Hello World fill should expose output textarea value in snapshot."""
    origin = 'http://127.0.0.1:8010'
    try:
        httpx.get(origin + '/base64-string-converter', timeout=2.0).raise_for_status()
    except Exception:
        pytest.skip('IT-Tools not running on :8010 (start reversex-it-tools to exercise this check)')
    with SafeBrowser(origin) as browser:
        snap = browser.goto(origin + '/base64-string-converter')
        encode_in = next(
            e
            for e in snap.elements
            if e.kind == 'textarea' and 'Put your string' in (e.placeholder or e.label or '')
        )
        after = browser.act(
            Decision(action='fill', element_id=encode_in.element_id, value='Hello World', reason='compat')
        )
        values = [e.value for e in after.elements if e.kind == 'textarea']
        assert 'Hello World' in values
        assert 'SGVsbG8gV29ybGQ=' in values
        assert any(
            c.field == 'value' and c.after == 'SGVsbG8gV29ybGQ=' for c in after.control_changes
        )
        # Still may omit from visible_text — that is OK if structured values exist.
        assert any(e.value == 'SGVsbG8gV29ybGQ=' for e in after.elements)


def test_generic_objectives_detect_control_value_changes():
    events = [
        {
            'step': 1,
            'status': 'ok',
            'decision': {'action': 'fill', 'element_id': 's1_e0', 'value': 'Hello World'},
            'before': {
                'visible_text': 'Tool',
                'elements': [
                    {'kind': 'textarea', 'label': 'in', 'value': ''},
                    {'kind': 'textarea', 'label': 'out', 'value': ''},
                ],
            },
            'after': {
                'visible_text': 'Tool',
                'elements': [
                    {'kind': 'textarea', 'label': 'in', 'value': 'Hello World'},
                    {'kind': 'textarea', 'label': 'out', 'value': 'SGVsbG8gV29ybGQ='},
                ],
                'control_changes': [
                    {
                        'kind': 'textarea',
                        'label': 'out',
                        'field': 'value',
                        'before': '',
                        'after': 'SGVsbG8gV29ybGQ=',
                    }
                ],
            },
        }
    ]
    objs = evaluate_generic_feature_objectives(events, feature='Base64')
    assert objs['page_response_observed']['supported'] is True


def test_verified_findings_include_control_value_change(tmp_path: Path):
    job_id = 'f' * 32
    root = tmp_path / job_id
    (root / 'investigation').mkdir(parents=True)
    final = {
        'id': job_id,
        'status': 'completed',
        'mode': 'scripted',
        'pipeline': 'investigate_only',
        'target_id': 'it-tools',
        'stages': {
            'reconstruction': {'status': 'skipped'},
            'validation': {'status': 'skipped'},
        },
    }
    investigation = {
        'target_id': 'it-tools',
        'feature': 'Base64 text encoding and decoding',
        'mode': 'scripted',
        'status': 'completed',
        'events': [
            {
                'step': 1,
                'status': 'ok',
                'decision': {
                    'action': 'fill',
                    'element_id': 's1_e4',
                    'value': 'Hello World',
                    'reason': 'encode',
                },
                'before': {
                    'visible_text': 'Base64',
                    'elements': [
                        {'element_id': 's1_e4', 'kind': 'textarea', 'label': 'Put your string here...', 'value': ''},
                        {
                            'element_id': 's1_e5',
                            'kind': 'textarea',
                            'label': 'The base64 encoding of your string will be here',
                            'value': '',
                        },
                    ],
                },
                'after': {
                    'visible_text': 'Base64',
                    'elements': [
                        {
                            'element_id': 's2_e4',
                            'kind': 'textarea',
                            'label': 'Put your string here...',
                            'value': 'Hello World',
                        },
                        {
                            'element_id': 's2_e5',
                            'kind': 'textarea',
                            'label': 'The base64 encoding of your string will be here',
                            'value': 'SGVsbG8gV29ybGQ=',
                        },
                    ],
                    'control_changes': [
                        {
                            'kind': 'textarea',
                            'label': 'The base64 encoding of your string will be here',
                            'field': 'value',
                            'before': '',
                            'after': 'SGVsbG8gV29ybGQ=',
                        }
                    ],
                },
            }
        ],
        'objectives': {
            'feature_controls_observed': {'supported': True, 'evidence': 'step 1'},
            'feature_interaction_attempted': {'supported': True, 'evidence': 'step 1'},
            'page_response_observed': {'supported': True, 'evidence': 'control changes'},
        },
    }
    (root / 'final_report.json').write_text(json.dumps(final), encoding='utf-8')
    (root / 'investigation' / 'report.json').write_text(json.dumps(investigation), encoding='utf-8')
    results = build_verified_results(tmp_path, job_id)
    texts = [f.claim_text for f in results.verified_findings]
    assert any('SGVsbG8gV29ybGQ=' in t for t in texts)
    assert any(f.rule_id == 'rule.observation_control_value_change' for f in results.verified_findings)


def test_diff_control_values_unit():
    before = PageSnapshot(
        snapshot_id=1,
        url='http://127.0.0.1:8010/',
        title='t',
        visible_text='x',
        elements=[VisibleElement(element_id='a', kind='textarea', label='out', value='')],
    )
    after = PageSnapshot(
        snapshot_id=2,
        url='http://127.0.0.1:8010/',
        title='t',
        visible_text='x',
        elements=[VisibleElement(element_id='b', kind='textarea', label='out', value='SGVsbG8=')],
    )
    changes = diff_control_values(before, after)
    assert changes and changes[0].after == 'SGVsbG8='


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        if isinstance(self._payload, str):
            return json.loads(self._payload)
        return self._payload


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def post(self, *args, **kwargs):
        self.calls.append({'args': args, 'kwargs': kwargs, 'json': kwargs.get('json')})
        if not self.responses:
            raise httpx.ConnectError('exhausted')
        return self.responses.pop(0)


def _snap() -> PageSnapshot:
    return PageSnapshot(
        snapshot_id=1,
        url='http://127.0.0.1:8001/',
        title='t',
        visible_text='hi',
        elements=[],
    )


def test_muse_valid_json(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY', 'test-key-not-real')
    planner = MusePlanner.__new__(MusePlanner)
    planner.target = type('T', (), {'muse_system': 'sys'})()
    planner.model = 'muse-test'
    planner.request_count = 0
    planner.max_empty_retries = 1
    planner.last_error_diagnostics = {}
    planner._http = _FakeClient(
        [
            _FakeResponse(
                200,
                {
                    'choices': [
                        {
                            'message': {
                                'content': json.dumps(
                                    {
                                        'action': 'stop',
                                        'element_id': None,
                                        'value': None,
                                        'reason': 'done exploring',
                                    }
                                )
                            },
                            'finish_reason': 'stop',
                        }
                    ]
                },
            )
        ]
    )
    decision = MusePlanner.decide(planner, _snap(), [])
    assert decision.action.value == 'stop'
    assert planner.request_count == 1


def test_muse_empty_content_retries_once_then_fails(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY', 'test-key-not-real')
    planner = MusePlanner.__new__(MusePlanner)
    planner.target = type('T', (), {'muse_system': 'sys'})()
    planner.model = 'muse-test'
    planner.request_count = 0
    planner.max_empty_retries = 1
    planner.last_error_diagnostics = {}
    planner._http = _FakeClient(
        [
            _FakeResponse(200, {'choices': [{'message': {'content': ''}, 'finish_reason': 'stop'}]}),
            _FakeResponse(200, {'choices': [{'message': {'content': ''}, 'finish_reason': 'stop'}]}),
        ]
    )
    with pytest.raises(MuseDecisionError) as exc:
        MusePlanner.decide(planner, _snap(), [])
    assert exc.value.kind == 'empty_content'
    assert planner.request_count == 2  # initial + one bounded retry


def test_muse_malformed_json(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY', 'test-key-not-real')
    planner = MusePlanner.__new__(MusePlanner)
    planner.target = type('T', (), {'muse_system': 'sys'})()
    planner.model = 'muse-test'
    planner.request_count = 0
    planner.max_empty_retries = 0
    planner.last_error_diagnostics = {}
    planner._http = _FakeClient(
        [_FakeResponse(200, {'choices': [{'message': {'content': 'not-json'}, 'finish_reason': 'stop'}]})]
    )
    with pytest.raises(MuseDecisionError) as exc:
        MusePlanner.decide(planner, _snap(), [])
    assert exc.value.kind == 'malformed_json'


def test_extract_recovers_prose_prefixed_json_like_it_tools_failure():
    """Live Muse sometimes prepends prose before the decision object — recover safely."""
    from reversex.meta import extract_decision_payload, normalize_decision_dict

    prose = (
        'Investigating Base64 encode/decode — testing the encoder with a sample string.'
        '{"action": "fill", "element_id": "s1_e4", "value": "Hello World", '
        '"reason": "Test Base64 encoding by entering sample text into string-to-encode field"}'
    )
    parsed, content, diag = extract_decision_payload(
        {'choices': [{'message': {'content': prose}, 'finish_reason': 'stop'}]}
    )
    assert diag.get('recovered_embedded_json') is True
    decision = normalize_decision_dict(parsed)
    assert decision.action.value == 'fill'
    assert decision.element_id == 's1_e4'
    assert decision.value == 'Hello World'
    assert content == prose


def test_extract_fence_wrapped_json():
    from reversex.meta import extract_decision_payload, normalize_decision_dict

    fenced = '```json\n{"action":"stop","element_id":null,"value":null,"reason":"done"}\n```'
    parsed, _, diag = extract_decision_payload(
        {'choices': [{'message': {'content': fenced}, 'finish_reason': 'stop'}]}
    )
    assert diag.get('recovered_embedded_json') is not True
    assert normalize_decision_dict(parsed).action.value == 'stop'


def test_muse_retry_sends_format_correction(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY', 'test-key-not-real')
    planner = MusePlanner.__new__(MusePlanner)
    planner.target = type('T', (), {'muse_system': 'sys'})()
    planner.model = 'muse-test'
    planner.request_count = 0
    planner.max_empty_retries = 1
    planner.last_error_diagnostics = {}
    good = {
        'choices': [
            {
                'message': {
                    'content': json.dumps(
                        {'action': 'stop', 'element_id': None, 'value': None, 'reason': 'enough evidence'}
                    )
                },
                'finish_reason': 'stop',
            }
        ]
    }
    client = _FakeClient(
        [
            _FakeResponse(200, {'choices': [{'message': {'content': 'not-json'}, 'finish_reason': 'stop'}]}),
            _FakeResponse(200, good),
        ]
    )
    planner._http = client
    decision = MusePlanner.decide(planner, _snap(), [])
    assert decision.action.value == 'stop'
    assert planner.request_count == 2
    # Second request must include the format-correction user message.
    second_payload = client.calls[1]['json']
    assert second_payload.get('temperature') == 0
    assert second_payload.get('response_format', {}).get('type') == 'json_schema'
    roles = [m['role'] for m in second_payload['messages']]
    assert roles.count('user') >= 2
    assert 'FORMAT CORRECTION' in second_payload['messages'][-1]['content']


def test_muse_http_error_no_retry(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY', 'test-key-not-real')
    planner = MusePlanner.__new__(MusePlanner)
    planner.target = type('T', (), {'muse_system': 'sys'})()
    planner.model = 'muse-test'
    planner.request_count = 0
    planner.max_empty_retries = 1
    planner.last_error_diagnostics = {}
    planner._http = _FakeClient([_FakeResponse(500, {'error': 'nope'})])
    with pytest.raises(MuseDecisionError) as exc:
        MusePlanner.decide(planner, _snap(), [])
    assert exc.value.kind == 'http_error'
    assert planner.request_count == 1


def test_muse_schema_invalid(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY', 'test-key-not-real')
    planner = MusePlanner.__new__(MusePlanner)
    planner.target = type('T', (), {'muse_system': 'sys'})()
    planner.model = 'muse-test'
    planner.request_count = 0
    planner.max_empty_retries = 1
    planner.last_error_diagnostics = {}
    planner._http = _FakeClient(
        [
            _FakeResponse(
                200,
                {
                    'choices': [
                        {
                            'message': {
                                'content': json.dumps(
                                    {'action': 'fill', 'element_id': None, 'value': 'x', 'reason': 'bad'}
                                )
                            }
                        }
                    ]
                },
            )
        ]
    )
    with pytest.raises(MuseDecisionError) as exc:
        MusePlanner.decide(planner, _snap(), [])
    assert exc.value.kind == 'schema_invalid'


def test_muse_transport_error(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY', 'test-key-not-real')
    planner = MusePlanner.__new__(MusePlanner)
    planner.target = type('T', (), {'muse_system': 'sys'})()
    planner.model = 'muse-test'
    planner.request_count = 0
    planner.max_empty_retries = 1
    planner.last_error_diagnostics = {}

    class Boom:
        def post(self, *a, **k):
            raise httpx.ConnectError('down')

    planner._http = Boom()
    with pytest.raises(MuseDecisionError) as exc:
        MusePlanner.decide(planner, _snap(), [])
    assert exc.value.kind == 'transport_error'


def test_extract_decision_payload_parsed_field():
    parsed, content, diag = extract_decision_payload(
        {
            'choices': [
                {
                    'message': {
                        'parsed': {'action': 'observe', 'element_id': None, 'value': None, 'reason': 'look'},
                        'content': None,
                    }
                }
            ]
        }
    )
    assert parsed['action'] == 'observe'
    assert diag['has_parsed'] is True
    decision = normalize_decision_dict(parsed)
    assert decision.action.value == 'observe'


def test_sanitize_diagnostics_strips_unknown():
    cleaned = sanitize_muse_diagnostics({'kind': 'empty_content', 'Authorization': 'secret', 'content_len': 0})
    assert 'Authorization' not in cleaned
    assert cleaned['kind'] == 'empty_content'
