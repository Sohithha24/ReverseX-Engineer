from pathlib import Path

from reversex.orchestrate import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_finalize_preserves_failed_stage(tmp_path: Path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError('forced investigation failure')

    monkeypatch.setattr('reversex.orchestrate.explore', boom)
    summary = run_pipeline(
        job_id='b' * 32,
        mode='scripted',
        pipeline='investigate_only',
        reuse_reconstruction=True,
        max_actions=2,
        artifacts_root=tmp_path,
    )
    assert summary['status'] == 'failed'
    assert summary['stages']['investigation']['executed'] is True
    assert summary['stages']['investigation']['status'] == 'failed'
    assert (tmp_path / ('b' * 32) / 'final_report.json').is_file()
    # Later stages must not be marked successful
    assert 'specification' not in summary['stages']
    assert 'validation' not in summary['stages']
