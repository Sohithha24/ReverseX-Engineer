import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from reversex.spec import (
    BehaviorRequirement,
    EvidenceKind,
    EvidenceRef,
    assert_observations_have_evidence,
    build_behavior_spec,
    generate_and_freeze_spec,
    load_frozen_spec,
)

ROOT = Path(__file__).resolve().parents[1]
PHASE1B_REPORT = ROOT / 'artifacts' / 'phase1b' / 'report.json'


def _minimal_report():
    return {
        'status': 'completed',
        'objectives': {
            'empty_task_submission': {'supported': True, 'evidence': 'step 1 validation'},
            'valid_task_submission': {
                'supported': True,
                'evidence': 'step 3 created',
                'task_name': 'Review PR',
            },
            'reload_persistence': {
                'supported': True,
                'evidence': 'step 4 persisted',
                'task_name': 'Review PR',
            },
        },
        'events': [
            {
                'step': 1,
                'status': 'ok',
                'decision': {'action': 'click', 'element_id': 's1_e1', 'value': None, 'reason': 'empty'},
                'before': {'visible_text': 'No tasks yet.'},
                'after': {'visible_text': 'Task name is required.\nNo tasks yet.'},
            },
            {
                'step': 2,
                'status': 'ok',
                'decision': {'action': 'fill', 'element_id': 's2_e0', 'value': 'Review PR', 'reason': 'fill'},
                'before': {'visible_text': 'Task name is required.'},
                'after': {'visible_text': 'Task name is required.'},
            },
            {
                'step': 3,
                'status': 'ok',
                'decision': {'action': 'click', 'element_id': 's3_e1', 'value': None, 'reason': 'submit'},
                'before': {'visible_text': 'No tasks yet.'},
                'after': {'visible_text': 'Your tasks\nReview PR'},
            },
            {
                'step': 4,
                'status': 'ok',
                'decision': {'action': 'reload', 'element_id': None, 'value': None, 'reason': 'reload'},
                'before': {'visible_text': 'Your tasks\nReview PR'},
                'after': {'visible_text': 'Your tasks\nReview PR'},
            },
        ],
    }


def test_build_spec_marks_observations_and_hypotheses():
    report = _minimal_report()
    raw = json.dumps(report).encode()
    spec = build_behavior_spec(report, source_report='artifacts/phase1b/report.json', report_bytes=raw)
    kinds = {r.id: r.kind for r in spec.requirements}
    assert kinds['REQ-EMPTY-SUBMIT'] == EvidenceKind.OBSERVATION
    assert kinds['REQ-VALID-CREATE'] == EvidenceKind.OBSERVATION
    assert kinds['REQ-RELOAD-PERSIST'] == EvidenceKind.OBSERVATION
    assert kinds['HYP-STORAGE-UNKNOWN'] == EvidenceKind.HYPOTHESIS
    assert_observations_have_evidence(spec)


def test_observation_without_step_evidence_rejected():
    with pytest.raises(ValidationError):
        BehaviorRequirement(
            id='BAD',
            kind=EvidenceKind.OBSERVATION,
            feature='add_task',
            preconditions=['x'],
            action_performed='click',
            observed_result='y',
            evidence=[EvidenceRef(report_path='r.json', note='no step')],
        )


def test_freeze_and_checksum_roundtrip(tmp_path: Path):
    report_path = tmp_path / 'report.json'
    report_path.write_text(json.dumps(_minimal_report()), encoding='utf-8')
    out = tmp_path / 'phase2'
    spec = generate_and_freeze_spec(report_path, output_dir=out)
    assert spec.status == 'frozen'
    sha = (out / 'behavior_spec.sha256').read_text(encoding='utf-8').strip()
    loaded = load_frozen_spec(out / 'behavior_spec.frozen.json', expected_sha256=sha)
    assert loaded.source_report_sha256 == spec.source_report_sha256
    with pytest.raises(ValueError, match='checksum'):
        load_frozen_spec(out / 'behavior_spec.frozen.json', expected_sha256='0' * 64)


@pytest.mark.skipif(not PHASE1B_REPORT.is_file(), reason='phase1b report missing')
def test_real_phase1b_report_produces_valid_frozen_spec(tmp_path: Path):
    out = tmp_path / 'phase2'
    spec = generate_and_freeze_spec(PHASE1B_REPORT, output_dir=out)
    assert spec.status == 'frozen'
    obs = [r for r in spec.requirements if r.kind == EvidenceKind.OBSERVATION]
    assert len(obs) >= 3
    assert_observations_have_evidence(spec)
