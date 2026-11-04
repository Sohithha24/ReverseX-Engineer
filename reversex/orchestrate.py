"""Phase 4A workflow orchestration over existing ReverseX modules.

Stages report only statuses that were actually reached. Failures preserve artifacts.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from reversex.evidence_graph import build_evidence_graph, export_evidence_graph
from reversex.run import explore
from reversex.spec import generate_and_freeze_spec, load_frozen_spec
from reversex.targets import InvestigationGoal, resolve_authorized_application

ROOT = Path(__file__).resolve().parents[1]
PHASE2_RECON = ROOT / 'artifacts' / 'phase2' / 'reconstructed-app'

JobStatus = Literal[
    'queued',
    'investigating',
    'specifying',
    'reconstructing',
    'validating',
    'completed',
    'incomplete',
    'failed',
]

Pipeline = Literal['investigate_only', 'full']


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_copy_tree(src: Path, dst: Path) -> list[str]:
    dst.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in src.iterdir():
        if path.is_file():
            target = dst / path.name
            shutil.copy2(path, target)
            copied.append(path.name)
    return copied


def run_pipeline(
    *,
    job_id: str,
    mode: Literal['scripted', 'muse'],
    pipeline: Pipeline,
    reuse_reconstruction: bool,
    max_actions: int,
    artifacts_root: Path,
    status_cb: Callable[[JobStatus, dict[str, Any]], None] | None = None,
    target_id: str | None = 'taskboard',
    application_url: str | None = None,
    feature: str | None = None,
    investigation_goal: InvestigationGoal = 'understand_and_reconstruct',
) -> dict[str, Any]:
    """Execute connected workflow. Never marks unexecuted stages successful."""
    target, start_url = resolve_authorized_application(
        application_url=application_url,
        target_id=target_id,
        feature=feature,
    )
    # Understand-only never claims reconstruction/validation occurred.
    effective_pipeline: Pipeline = (
        'investigate_only' if investigation_goal == 'understand' else pipeline
    )
    job_dir = artifacts_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    stages: dict[str, Any] = {}
    errors: list[str] = []

    def set_status(status: JobStatus, extra: dict | None = None):
        payload = {'status': status, 'updated_at': _utc(), **(extra or {})}
        if status_cb:
            status_cb(status, payload)

    def done(status: JobStatus) -> dict[str, Any]:
        return _finalize(
            job_id,
            job_dir,
            status,
            stages,
            errors,
            mode,
            effective_pipeline,
            target.id,
            feature=target.feature_label,
            application_url=start_url,
            investigation_goal=investigation_goal,
        )

    # --- Stage 1: investigation ---
    set_status('investigating')
    inv_dir = job_dir / 'investigation'
    try:
        report = explore(
            mode,
            url=start_url,
            output_dir=str(inv_dir),
            max_actions=max_actions,
            target=target,
        )
        stages['investigation'] = {
            'executed': True,
            'status': report.get('status'),
            'artifact': f'{job_id}/investigation/report.json',
            'duration_seconds': report.get('duration_seconds'),
            'api_request_count': report.get('api_request_count', 0),
            'target_id': target.id,
            'feature': target.feature_label,
            'application_url': start_url,
        }
        if report.get('status') not in ('completed', 'incomplete', 'budget_exhausted'):
            # explore uses completed/incomplete/budget_exhausted/error
            if report.get('status') == 'error':
                errors.append('investigation ended with error')
                set_status('failed', {'stages': stages, 'errors': errors})
                return done('failed')
    except Exception as exc:
        stages['investigation'] = {'executed': True, 'status': 'failed', 'error': str(exc)[:300]}
        errors.append(str(exc)[:300])
        set_status('failed', {'stages': stages, 'errors': errors})
        return done('failed')

    if effective_pipeline == 'investigate_only':
        final = 'completed' if stages['investigation']['status'] == 'completed' else 'incomplete'
        stages['specification'] = {
            'executed': False,
            'status': 'skipped',
            'note': 'Understand-only goal — specification not requested',
        }
        stages['reconstruction'] = {
            'executed': False,
            'status': 'skipped',
            'note': 'Understand-only goal — reconstruction not requested',
        }
        stages['validation'] = {
            'executed': False,
            'status': 'skipped',
            'note': 'Understand-only goal — independent validation not requested',
        }
        stages['repair'] = {
            'executed': False,
            'status': 'skipped',
            'note': 'Understand-only goal — repair not requested',
        }
        set_status(final, {'stages': stages})
        graph = build_evidence_graph(
            root=job_dir,
            investigation_report=inv_dir / 'report.json',
            behavior_spec=job_dir / 'missing_spec.json',
            reconstruction_dir=job_dir / 'missing_recon',
            validation_results=job_dir / 'missing_val.json',
        )
        export_evidence_graph(graph, job_dir / 'evidence_graph.json')
        return done(final)

    # --- Stage 2: specification ---
    set_status('specifying', {'stages': stages})
    spec_dir = job_dir / 'specification'
    try:
        spec = generate_and_freeze_spec(inv_dir / 'report.json', output_dir=spec_dir)
        stages['specification'] = {
            'executed': True,
            'status': spec.status,
            'artifact': f'{job_id}/specification/behavior_spec.frozen.json',
            'observation_requirements': [r.id for r in spec.requirements if r.kind.value == 'observation'],
        }
    except Exception as exc:
        stages['specification'] = {'executed': True, 'status': 'failed', 'error': str(exc)[:300]}
        errors.append(str(exc)[:300])
        set_status('failed', {'stages': stages, 'errors': errors})
        return done('failed')

    # --- Stage 3: reconstruction ---
    set_status('reconstructing', {'stages': stages})
    recon_dir = job_dir / 'reconstructed-app'
    try:
        # Reuse is TaskBoard Phase-2 only; never reuse TaskBoard recon for other apps.
        can_reuse = (
            reuse_reconstruction
            and target.supports_reconstruction_reuse
            and target.id == 'taskboard'
            and (PHASE2_RECON / 'index.html').is_file()
        )
        if can_reuse:
            copied = _safe_copy_tree(PHASE2_RECON, recon_dir)
            # Do not modify/overwrite the Phase 2 source directory; only copy into job dir.
            stages['reconstruction'] = {
                'executed': True,
                'status': 'reused',
                'artifact': f'{job_id}/reconstructed-app/',
                'files': copied,
                'meta_api_requests': 0,
                'note': 'Reused existing Phase 2 reconstruction; did not overwrite artifacts/phase2/reconstructed-app',
            }
        else:
            from reversex.reconstruct import run_reconstruction

            sha = (spec_dir / 'behavior_spec.sha256').read_text(encoding='utf-8').strip()
            frozen = load_frozen_spec(spec_dir / 'behavior_spec.frozen.json', expected_sha256=sha)
            result = run_reconstruction(
                frozen,
                output_dir=recon_dir,
                sample_app_dir=target.fixture_dir,
                preview_fn=lambda _d: {'status': 'deferred', 'reason': 'preview deferred to validation stage'},
            )
            stages['reconstruction'] = {
                'executed': True,
                'status': result.status,
                'artifact': f'{job_id}/reconstructed-app/',
                'files_written': result.files_written,
                'meta_api_requests': result.api_request_count,
                'meta_summary': result.meta_summary,
            }
    except Exception as exc:
        stages['reconstruction'] = {'executed': True, 'status': 'failed', 'error': str(exc)[:300]}
        errors.append(str(exc)[:300])
        set_status('failed', {'stages': stages, 'errors': errors})
        return done('failed')

    # --- Stage 4: validation ---
    set_status('validating', {'stages': stages})
    val_dir = job_dir / 'validation'
    validation = None
    final_status: JobStatus = 'completed'
    if not (target.supports_independent_validation and target.validation_suite):
        stages['validation'] = {
            'executed': False,
            'status': 'unavailable',
            'note': (
                'Independent validation is not available for this allowlisted application. '
                'Existing oracles are fixture-specific (TaskBoard / MiniCalc) and must not invent a match score.'
            ),
            'behavioral_match_rate_percent': None,
            'suite': None,
        }
        stages['repair'] = {
            'executed': False,
            'status': 'skipped',
            'note': 'Repair skipped because independent validation is unavailable for this target',
        }
        # Investigation + reconstruction may still succeed; do not invent validation success.
        inv_ok = stages.get('investigation', {}).get('status') in ('completed', 'incomplete', 'budget_exhausted')
        recon_ok = stages.get('reconstruction', {}).get('status') in ('reused', 'completed', 'generated', 'ok')
        final_status = 'completed' if inv_ok and recon_ok else 'incomplete'
        set_status(final_status, {'stages': stages, 'errors': errors})
        graph = build_evidence_graph(
            root=ROOT,
            investigation_report=inv_dir / 'report.json',
            behavior_spec=spec_dir / 'behavior_spec.frozen.json',
            reconstruction_dir=recon_dir,
            validation_results=val_dir / 'missing_validation.json',
        )
        export_evidence_graph(graph, job_dir / 'evidence_graph.json')
        return done(final_status)

    try:
        from reversex.validate import run_phase3_validation

        validation = run_phase3_validation(
            reconstructed_dir=recon_dir,
            output_dir=val_dir,
            original_origin=target.origin,
            suite=target.validation_suite,
        )
        stages['validation'] = {
            'executed': True,
            'status': 'completed' if validation.behavioral_match_rate_percent is not None else 'blocked',
            'artifact': f'{job_id}/validation/validation_results.json',
            'passed': validation.passed,
            'failed': validation.failed,
            'invalid': validation.invalid,
            'total_valid': validation.total_valid,
            'behavioral_match_rate_percent': validation.behavioral_match_rate_percent,
            'isolation': validation.isolation,
            'meta_api_requests': validation.meta_api_requests,
            'suite': target.validation_suite,
        }
        if validation.behavioral_match_rate_percent is None:
            errors.append('validation blocked or unavailable')
            set_status('incomplete', {'stages': stages, 'errors': errors})
            final_status = 'incomplete'
        elif validation.failed or validation.invalid:
            set_status('incomplete', {'stages': stages, 'errors': errors})
            final_status = 'incomplete'
        else:
            final_status = 'completed'
            set_status('completed', {'stages': stages})
    except Exception as exc:
        stages['validation'] = {'executed': True, 'status': 'failed', 'error': str(exc)[:300]}
        errors.append(str(exc)[:300])
        set_status('failed', {'stages': stages, 'errors': errors})
        return done('failed')

    # --- Stage 5: bounded repair (only when real validation failures exist) ---
    repair_report_path = job_dir / 'repair' / 'repair_report.json'
    if (
        stages.get('validation', {}).get('status') == 'completed'
        and int(stages['validation'].get('failed') or 0) > 0
    ):
        try:
            from reversex.repair import run_bounded_repair

            repair = run_bounded_repair(
                output_root=job_dir / 'repair',
                frozen_spec_path=spec_dir / 'behavior_spec.frozen.json',
                initial_recon_dir=recon_dir,
                initial_validation=validation,
                target=target,
                evaluation_kind='pipeline_repair',
                label='Pipeline bounded repair after differential validation failures',
            )
            stages['repair'] = {
                'executed': True,
                'status': repair.stopped_reason,
                'evaluation_kind': repair.evaluation_kind,
                'attempts': len(repair.attempts),
                'initial_match_rate_percent': repair.initial_match_rate_percent,
                'final_match_rate_percent': repair.final_match_rate_percent,
                'meta_api_requests': repair.meta_api_requests_total,
                'artifact': f'{job_id}/repair/repair_report.json',
                'best_candidate_dir': repair.best_candidate_dir,
            }
            if repair.final_match_rate_percent == 100.0:
                final_status = 'completed'
                set_status('completed', {'stages': stages})
            else:
                final_status = 'incomplete'
                set_status('incomplete', {'stages': stages, 'errors': errors})
        except Exception as exc:
            stages['repair'] = {'executed': True, 'status': 'failed', 'error': str(exc)[:300]}
            errors.append(f'repair: {exc!s}'[:300])
            set_status('incomplete', {'stages': stages, 'errors': errors})
            final_status = 'incomplete'
    else:
        stages['repair'] = {
            'executed': False,
            'status': 'skipped',
            'note': 'No failed validation scenarios — repair not invoked',
        }

    graph = build_evidence_graph(
        root=ROOT,
        investigation_report=inv_dir / 'report.json',
        behavior_spec=spec_dir / 'behavior_spec.frozen.json',
        reconstruction_dir=recon_dir,
        validation_results=val_dir / 'validation_results.json',
        repair_report=repair_report_path if repair_report_path.is_file() else None,
    )
    export_evidence_graph(graph, job_dir / 'evidence_graph.json')
    return done(final_status)


def _finalize(
    job_id: str,
    job_dir: Path,
    status: JobStatus,
    stages: dict,
    errors: list[str],
    mode: str,
    pipeline: str,
    target_id: str = 'taskboard',
    feature: str | None = None,
    application_url: str | None = None,
    investigation_goal: str | None = None,
) -> dict[str, Any]:
    summary = {
        'id': job_id,
        'status': status,
        'mode': mode,
        'pipeline': pipeline,
        'target_id': target_id,
        'feature': feature,
        'application_url': application_url,
        'investigation_goal': investigation_goal,
        'updated_at': _utc(),
        'stages': stages,
        'errors': errors,
        'artifacts': {
            'root': f'artifacts/{job_id}/',
            'evidence_graph': f'{job_id}/evidence_graph.json' if (job_dir / 'evidence_graph.json').is_file() else None,
            'report': f'{job_id}/final_report.json',
        },
        'meta_api_requests_total': _sum_meta(stages),
    }
    (job_dir / 'final_report.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


def _sum_meta(stages: dict) -> int:
    total = 0
    inv = stages.get('investigation') or {}
    total += int(inv.get('api_request_count') or 0)
    recon = stages.get('reconstruction') or {}
    total += int(recon.get('meta_api_requests') or 0)
    return total
