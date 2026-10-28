import hashlib
from pathlib import Path

import pytest

from reversex.reconstruct import (
    ALLOWED_FILENAMES,
    MAX_FILE_BYTES,
    assert_no_original_source_in_context,
    observation_only_spec_for_model,
    snapshot_sample_app_hashes,
    validate_reconstruction_response,
    verify_original_app_untouched,
    write_reconstructed_app,
)
from reversex.spec import BehaviorSpec, EvidenceKind, EvidenceRef, BehaviorRequirement

ROOT = Path(__file__).resolve().parents[1]


def _frozen_spec() -> BehaviorSpec:
    return BehaviorSpec(
        source_report='artifacts/phase1b/report.json',
        source_report_sha256='a' * 64,
        feature='Add task',
        status='frozen',
        requirements=[
            BehaviorRequirement(
                id='REQ-EMPTY-SUBMIT',
                kind=EvidenceKind.OBSERVATION,
                feature='add_task',
                preconditions=['empty list'],
                action_performed='click Add task',
                observed_result='Task name is required.',
                evidence=[EvidenceRef(report_path='r.json', step=1, note='validation')],
            ),
        ],
        excluded_from_model_context=['sample_app/**'],
    )


def _valid_files():
    return {
        'files': [
            {'filename': 'index.html', 'content': '<!doctype html><title>t</title>'},
            {'filename': 'style.css', 'content': 'body{margin:0}'},
            {'filename': 'script.js', 'content': 'console.log(1)'},
        ],
        'notes': 'minimal',
    }


def test_validate_accepts_allowlisted_triplet():
    payload = validate_reconstruction_response(_valid_files())
    assert {f.filename for f in payload.files} == ALLOWED_FILENAMES


def test_reject_unsupported_filename():
    data = _valid_files()
    data['files'][2] = {'filename': 'evil.exe', 'content': 'x'}
    with pytest.raises(ValueError):
        validate_reconstruction_response(data)


def test_reject_path_traversal_filename():
    data = _valid_files()
    data['files'][0] = {'filename': '../index.html', 'content': '<html></html>'}
    with pytest.raises(ValueError):
        validate_reconstruction_response(data)


def test_reject_absolute_path_filename():
    data = _valid_files()
    data['files'][0] = {'filename': r'C:\Windows\index.html', 'content': '<html></html>'}
    with pytest.raises(ValueError):
        validate_reconstruction_response(data)


def test_reject_oversized_file():
    data = _valid_files()
    data['files'][1] = {'filename': 'style.css', 'content': 'x' * (MAX_FILE_BYTES + 10)}
    with pytest.raises(ValueError, match='limit|byte'):
        validate_reconstruction_response(data)


def test_reject_invalid_model_json():
    with pytest.raises(ValueError, match='invalid model JSON'):
        validate_reconstruction_response('{not-json')


def test_write_stays_in_output_dir(tmp_path: Path):
    payload = validate_reconstruction_response(_valid_files())
    written = write_reconstructed_app(payload, tmp_path / 'out')
    assert len(written) == 3
    for path in written:
        assert Path(path).parent == (tmp_path / 'out').resolve()


def test_model_context_excludes_sample_app_and_blocks_fingerprints():
    ctx = observation_only_spec_for_model(_frozen_spec())
    assert 'sample_app/**' in ctx['excluded_from_model_context']
    assert 'observation_requirements' in ctx
    assert_no_original_source_in_context(ctx)
    poisoned = dict(ctx)
    poisoned['observation_requirements'] = [
        {'observed_result': "localStorage.setItem('reversex_fixture_tasks_v1', '[]')"},
    ]
    with pytest.raises(RuntimeError, match='forbidden'):
        assert_no_original_source_in_context(poisoned)


def test_original_application_preserved(tmp_path: Path):
    sample = tmp_path / 'sample_app'
    sample.mkdir()
    (sample / 'index.html').write_text('ORIGINAL', encoding='utf-8')
    (sample / 'app.js').write_text('console.log("orig")', encoding='utf-8')
    before = snapshot_sample_app_hashes(sample)
    # Write reconstruction elsewhere
    payload = validate_reconstruction_response(_valid_files())
    write_reconstructed_app(payload, tmp_path / 'reconstructed-app')
    assert verify_original_app_untouched(sample, before) is True
    (sample / 'app.js').write_text('tampered', encoding='utf-8')
    assert verify_original_app_untouched(sample, before) is False


def test_real_sample_app_hash_snapshot_stable():
    sample = ROOT / 'sample_app'
    if not sample.is_dir():
        pytest.skip('sample_app missing')
    before = snapshot_sample_app_hashes(sample)
    assert before
    assert verify_original_app_untouched(sample, before) is True
    # Ensure hashes are sha256 hex
    for digest in before.values():
        assert len(digest) == 64
        int(digest, 16)
