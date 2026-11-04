"""Investigation error events must surface in VerifiedResults and human reports."""
from __future__ import annotations

import json
from pathlib import Path

from reversex.reporting import build_report_package, build_timeline, narrate_error_event
from reversex.verification import build_verified_results

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'
IT_TOOLS_FAIL = 'c3f925d4254d4ba586cf886daf9e61c7'


def test_narrate_error_event_is_plain_english():
    card = narrate_error_event(
        {
            'step': 1,
            'status': 'error',
            'error': 'Meta returned malformed JSON decision: Expecting value',
            'error_kind': 'malformed_json',
            'error_diagnostics': {
                'message_preview': 'Investigating Base64…{"action": "fill"',
            },
        }
    )
    assert card['action'] == 'error'
    assert 'valid decision JSON' in card['what_happened']
    assert 'guess' in card['what_that_shows'].lower() or 'invent' in card['what_that_shows'].lower()


def test_it_tools_failed_job_surfaces_muse_problem():
    path = ARTIFACTS / IT_TOOLS_FAIL / 'investigation' / 'report.json'
    if not path.is_file():
        import pytest

        pytest.skip('IT-Tools second Muse evaluation artifacts unavailable')

    verified = build_verified_results(ARTIFACTS, IT_TOOLS_FAIL)
    assert verified.investigation_status == 'failed'
    assert verified.problems, 'Failed Muse parse must become a VerifiedResults problem'
    blob = ' '.join(p.description for p in verified.problems)
    assert 'JSON' in blob or 'AI' in blob

    timeline = build_timeline(json.loads(path.read_text(encoding='utf-8')))
    assert timeline
    assert any(item.get('action') == 'error' for item in timeline)

    package = build_report_package(ARTIFACTS, IT_TOOLS_FAIL)
    assert 'Why the investigation had problems' in package['simple_markdown']
    assert 'malformed_json' in package['developer_markdown'] or 'JSON' in package['developer_markdown']
    assert package['timeline']
