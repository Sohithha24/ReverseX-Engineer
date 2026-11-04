"""Evidence Verification Engine — deterministic checks against recorded artifacts.

Does not call Meta / Muse. Does not invent confidence scores.
A claim is never verified merely because an evidence reference string exists.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from reversex.run import evaluate_objectives
from reversex.targets import get_target
from reversex.validate import BehavioralCaseResult, calculate_match_rate

JOB_ID_RE = re.compile(r'^[a-f0-9]{32}$')


class VerificationStatus(str, Enum):
    verified = 'verified'
    partially_verified = 'partially_verified'
    not_verified = 'not_verified'
    contradicted = 'contradicted'
    requires_review = 'requires_review'


class ClaimCategory(str, Enum):
    investigation_observation = 'investigation_observation'
    reload_persistence = 'reload_persistence'
    validation_match = 'validation_match'
    reconstruction_status = 'reconstruction_status'
    repair_outcome = 'repair_outcome'
    investigation_mode = 'investigation_mode'
    storage_implementation = 'storage_implementation'
    overgeneralization = 'overgeneralization'
    original_defect = 'original_defect'
    pipeline_consistency = 'pipeline_consistency'


class ProblemCategory(str, Enum):
    reconstruction_mismatch = 'reconstruction_mismatch'
    investigation_limitation = 'investigation_limitation'
    validation_execution_failure = 'validation_execution_failure'
    reconstruction_generation_failure = 'reconstruction_generation_failure'
    infrastructure_failure = 'infrastructure_failure'
    unverified_hypothesis = 'unverified_hypothesis'
    confirmed_original_defect = 'confirmed_original_defect'


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra='forbid')

    ref_id: str
    kind: Literal[
        'investigation_report',
        'investigation_event',
        'investigation_objective',
        'behavior_spec',
        'validation_test',
        'validation_summary',
        'reconstruction_artifact',
        'repair_attempt',
        'repair_report',
        'final_report_stage',
        'missing',
    ]
    location: str
    note: str | None = None
    available: bool = True


class VerifiedFinding(BaseModel):
    model_config = ConfigDict(extra='forbid')

    claim_id: str
    investigation_id: str
    target_application: str | None
    feature_investigated: str | None
    claim_category: ClaimCategory
    claim_text: str
    supporting_evidence: list[EvidenceReference] = Field(default_factory=list)
    contradictory_evidence: list[EvidenceReference] = Field(default_factory=list)
    verification_status: VerificationStatus
    verification_scope: str
    limitations: list[str] = Field(default_factory=list)
    related_test_ids: list[str] = Field(default_factory=list)
    timestamps: list[str] = Field(default_factory=list)
    problem_category: ProblemCategory | None = None
    rule_id: str | None = None


class ContradictionRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    contradiction_id: str
    description: str
    claim_text: str
    expected: str
    observed: str
    evidence: list[EvidenceReference] = Field(default_factory=list)
    decidable: bool = True


class ProblemRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    problem_id: str
    category: ProblemCategory
    description: str
    related_test_ids: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VerifiedResults(BaseModel):
    """Shared payload for future Simple and Developer reports."""

    model_config = ConfigDict(extra='forbid')

    investigation_id: str
    generated_at: str
    availability: Literal['complete', 'partial', 'unavailable']
    target_application: str | None = None
    feature_investigated: str | None = None
    investigation_mode: str | None = None
    pipeline: str | None = None
    investigation_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    verified_findings: list[VerifiedFinding] = Field(default_factory=list)
    partially_verified_findings: list[VerifiedFinding] = Field(default_factory=list)
    unsupported_findings: list[VerifiedFinding] = Field(default_factory=list)
    contradicted_findings: list[VerifiedFinding] = Field(default_factory=list)
    requires_review_findings: list[VerifiedFinding] = Field(default_factory=list)
    contradictions: list[ContradictionRecord] = Field(default_factory=list)
    problems: list[ProblemRecord] = Field(default_factory=list)
    untested_behaviors: list[str] = Field(default_factory=list)
    reconstruction_status: dict[str, Any] | None = None
    validation_summary: dict[str, Any] | None = None
    repair_summary: dict[str, Any] | None = None
    coverage_limitations: list[str] = Field(default_factory=list)
    evidence_index: list[EvidenceReference] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StructuredClaim(BaseModel):
    """Typed claim input for verification — not free-form NLP."""

    model_config = ConfigDict(extra='forbid')

    claim_type: Literal[
        'reload_persistence_observed',
        'validation_all_passed',
        'validation_pass_count',
        'reconstruction_completed',
        'repair_succeeded',
        'muse_fresh_investigation',
        'storage_postgres',
        'permanent_persistence',
        'universal_behavioral_equivalence',
        'original_app_defective',
        'bug_free_reconstruction',
    ]
    claim_text: str | None = None
    asserted_pass_count: int | None = None
    asserted_mode: str | None = None


class ArtifactBundle(BaseModel):
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True)

    investigation_id: str
    job_root: Path
    final_report: dict[str, Any] | None = None
    investigation_report: dict[str, Any] | None = None
    behavior_spec: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    repair: dict[str, Any] | None = None
    reconstruction_files: list[str] = Field(default_factory=list)
    missing_artifacts: list[str] = Field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read_json(job_root: Path, *parts: str) -> tuple[Any | None, str | None]:
    root = job_root.resolve()
    path = root.joinpath(*parts).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None, '/'.join(parts)
    if not path.is_file():
        return None, '/'.join(parts)
    return json.loads(path.read_text(encoding='utf-8')), None


def load_artifact_bundle(artifacts_root: Path, investigation_id: str) -> ArtifactBundle:
    if not JOB_ID_RE.match(investigation_id):
        raise ValueError('Invalid investigation id')
    job_root = (artifacts_root / investigation_id).resolve()
    try:
        job_root.relative_to(artifacts_root.resolve())
    except ValueError as exc:
        raise ValueError('Investigation path escapes artifacts root') from exc

    missing: list[str] = []
    final, miss = _safe_read_json(job_root, 'final_report.json')
    if miss:
        missing.append(miss)
    inv, miss = _safe_read_json(job_root, 'investigation', 'report.json')
    if miss:
        missing.append(miss)
    spec, miss = _safe_read_json(job_root, 'specification', 'behavior_spec.frozen.json')
    if miss:
        missing.append(miss)
    validation, miss = _safe_read_json(job_root, 'validation', 'validation_results.json')
    if miss:
        missing.append(miss)
    repair, miss = _safe_read_json(job_root, 'repair', 'repair_report.json')
    if miss:
        # Optional unless claimed — track but do not require.
        pass

    recon_dir = job_root / 'reconstructed-app'
    files: list[str] = []
    if recon_dir.is_dir():
        for name in ('index.html', 'script.js', 'style.css'):
            if (recon_dir / name).is_file():
                files.append(name)
    else:
        missing.append('reconstructed-app/')

    return ArtifactBundle(
        investigation_id=investigation_id,
        job_root=job_root,
        final_report=final if isinstance(final, dict) else None,
        investigation_report=inv if isinstance(inv, dict) else None,
        behavior_spec=spec if isinstance(spec, dict) else None,
        validation=validation if isinstance(validation, dict) else None,
        repair=repair if isinstance(repair, dict) else None,
        reconstruction_files=files,
        missing_artifacts=missing,
    )


def _ref(
    ref_id: str,
    kind: EvidenceReference.__annotations__['kind'],
    location: str,
    *,
    note: str | None = None,
    available: bool = True,
) -> EvidenceReference:
    return EvidenceReference(
        ref_id=ref_id,
        kind=kind,
        location=location,
        note=note,
        available=available,
    )


def _ok_events(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in (report.get('events') or []) if e.get('status') == 'ok']


def _visible(event: dict[str, Any], which: str) -> str:
    snap = event.get(which) or {}
    return str(snap.get('visible_text') or '')


def check_reload_persistence_predicates(
    investigation_report: dict[str, Any],
) -> tuple[VerificationStatus, list[EvidenceReference], list[EvidenceReference], str, list[str]]:
    """Require: task creation observed, reload occurred, same task visible after reload."""
    events = _ok_events(investigation_report)
    target_id = investigation_report.get('target_id') or 'taskboard'
    try:
        target = get_target(str(target_id))
    except Exception:
        target = get_target('taskboard')
    derived = evaluate_objectives(events, target)
    reload_obj = derived.get('reload_persistence') or {}
    create_obj = derived.get('valid_task_submission') or {}

    supporting: list[EvidenceReference] = []
    contradictory: list[EvidenceReference] = []
    limitations: list[str] = []

    create_event = next(
        (
            e
            for e in events
            if (e.get('decision') or {}).get('action') == 'click'
            and create_obj.get('task_name')
            and create_obj.get('task_name') in _visible(e, 'after')
        ),
        None,
    )
    reload_event = next(
        (e for e in events if (e.get('decision') or {}).get('action') == 'reload'),
        None,
    )

    if create_event is not None:
        supporting.append(
            _ref(
                f"event:step={create_event.get('step')}:create",
                'investigation_event',
                f"investigation/report.json#events[step={create_event.get('step')}]",
                note='Task creation observation',
            )
        )
    else:
        contradictory.append(
            _ref('missing:create', 'missing', 'investigation/report.json', note='No create observation', available=False)
        )

    if reload_event is not None:
        supporting.append(
            _ref(
                f"event:step={reload_event.get('step')}:reload",
                'investigation_event',
                f"investigation/report.json#events[step={reload_event.get('step')}]",
                note='Browser reload observed',
            )
        )
        task_name = create_obj.get('task_name') or reload_obj.get('task_name')
        after = _visible(reload_event, 'after')
        if task_name and task_name in after:
            supporting.append(
                _ref(
                    f"event:step={reload_event.get('step')}:post-reload-visible",
                    'investigation_event',
                    f"investigation/report.json#events[step={reload_event.get('step')}].after",
                    note=f'Task text "{task_name}" visible after reload',
                )
            )
        elif task_name:
            contradictory.append(
                _ref(
                    f"event:step={reload_event.get('step')}:post-reload-missing",
                    'investigation_event',
                    f"investigation/report.json#events[step={reload_event.get('step')}].after",
                    note=f'Task text "{task_name}" not visible after reload',
                )
            )
    else:
        contradictory.append(
            _ref('missing:reload', 'missing', 'investigation/report.json', note='No reload event', available=False)
        )

    supporting.append(
        _ref(
            'objective:reload_persistence',
            'investigation_objective',
            'investigation/report.json#objectives.reload_persistence',
            note=str(reload_obj.get('evidence') or 'derived objective'),
        )
    )

    limitations = [
        'Verified for a single browser reload during this investigation only.',
        'Does not prove durable storage, database persistence, or multi-session survival.',
    ]
    scope = 'Single observed reload within the recorded investigation session'

    if create_event and reload_event and reload_obj.get('supported') and not any(
        r.ref_id.endswith('post-reload-missing') for r in contradictory
    ):
        return VerificationStatus.verified, supporting, [], scope, limitations
    if create_event and reload_event and not reload_obj.get('supported'):
        return VerificationStatus.contradicted, supporting, contradictory, scope, limitations
    if create_event or reload_event:
        return VerificationStatus.partially_verified, supporting, contradictory, scope, limitations
    return VerificationStatus.not_verified, supporting, contradictory, scope, limitations


def check_validation_pass_count(
    validation: dict[str, Any],
    *,
    asserted_count: int | None = None,
) -> tuple[VerificationStatus, dict[str, Any], list[EvidenceReference], list[EvidenceReference], str, list[str]]:
    tests_raw = validation.get('tests') or []
    results: list[BehavioralCaseResult] = []
    for item in tests_raw:
        try:
            results.append(BehavioralCaseResult.model_validate(item))
        except Exception:
            continue
    total_valid, passed, failed, invalid, rate = calculate_match_rate(results)
    summary_passed = validation.get('passed')
    summary_failed = validation.get('failed')
    summary_invalid = validation.get('invalid')
    summary_rate = validation.get('behavioral_match_rate_percent')

    supporting = [
        _ref(
            'validation:summary',
            'validation_summary',
            'validation/validation_results.json',
            note=f'Recomputed: passed={passed} failed={failed} invalid={invalid} total_valid={total_valid}',
        )
    ]
    contradictory: list[EvidenceReference] = []
    for t in results:
        if t.status == 'pass':
            supporting.append(
                _ref(
                    f'validation:test:{t.test_id}',
                    'validation_test',
                    f'validation/validation_results.json#tests[test_id={t.test_id}]',
                    note=f'status={t.status}',
                )
            )
        elif t.status == 'fail':
            contradictory.append(
                _ref(
                    f'validation:test:{t.test_id}:fail',
                    'validation_test',
                    f'validation/validation_results.json#tests[test_id={t.test_id}]',
                    note='status=fail',
                )
            )

    # Invalid tests must never count as passes.
    invalid_counted_as_pass = False
    if summary_passed is not None and isinstance(summary_passed, int):
        if summary_passed > passed:
            invalid_counted_as_pass = True
            contradictory.append(
                _ref(
                    'validation:summary:pass-inflation',
                    'validation_summary',
                    'validation/validation_results.json',
                    note=f'Summary passed={summary_passed} exceeds recomputed valid passes={passed}',
                )
            )

    summary_mismatch = (
        summary_passed not in (None, passed)
        or summary_failed not in (None, failed)
        or summary_invalid not in (None, invalid)
    )
    if summary_mismatch and not invalid_counted_as_pass:
        contradictory.append(
            _ref(
                'validation:summary:mismatch',
                'validation_summary',
                'validation/validation_results.json',
                note='Stored summary counts disagree with recomputed valid pass/fail/invalid',
            )
        )

    expected = asserted_count if asserted_count is not None else passed
    scope = f'{passed} valid pass result(s) out of {total_valid} valid comparison(s); {invalid} invalid excluded'
    limitations = [
        'Match applies only to the executed comparison suite.',
        'Invalid tests are excluded from pass counts.',
        'Does not prove the reconstruction is bug-free outside these scenarios.',
    ]
    stats = {
        'passed': passed,
        'failed': failed,
        'invalid': invalid,
        'total_valid': total_valid,
        'behavioral_match_rate_percent': rate,
        'summary_passed': summary_passed,
        'summary_rate': summary_rate,
        'test_ids_passed': [t.test_id for t in results if t.status == 'pass'],
        'test_ids_failed': [t.test_id for t in results if t.status == 'fail'],
        'test_ids_invalid': [t.test_id for t in results if t.status == 'invalid'],
    }

    if total_valid == 0:
        return VerificationStatus.not_verified, stats, supporting, contradictory, scope, limitations
    if asserted_count is not None and asserted_count != passed:
        return VerificationStatus.contradicted, stats, supporting, contradictory, scope, limitations
    if contradictory and (summary_mismatch or invalid_counted_as_pass):
        return VerificationStatus.contradicted, stats, supporting, contradictory, scope, limitations
    if asserted_count is None and failed == 0 and passed > 0 and not summary_mismatch:
        return VerificationStatus.verified, stats, supporting, contradictory, scope, limitations
    if asserted_count is not None and asserted_count == passed and failed == 0:
        return VerificationStatus.verified, stats, supporting, contradictory, scope, limitations
    if passed > 0 and failed > 0:
        return VerificationStatus.partially_verified, stats, supporting, contradictory, scope, limitations
    if expected == passed:
        return VerificationStatus.verified, stats, supporting, contradictory, scope, limitations
    return VerificationStatus.not_verified, stats, supporting, contradictory, scope, limitations


def check_reconstruction_status(
    bundle: ArtifactBundle,
) -> tuple[VerificationStatus, list[EvidenceReference], list[EvidenceReference], str, list[str]]:
    stage = ((bundle.final_report or {}).get('stages') or {}).get('reconstruction') or {}
    status = str(stage.get('status') or '')
    supporting: list[EvidenceReference] = []
    contradictory: list[EvidenceReference] = []

    if stage:
        supporting.append(
            _ref(
                'final:reconstruction',
                'final_report_stage',
                'final_report.json#stages.reconstruction',
                note=f'status={status}',
            )
        )
    for name in bundle.reconstruction_files:
        supporting.append(
            _ref(
                f'recon:{name}',
                'reconstruction_artifact',
                f'reconstructed-app/{name}',
                note='Generated/reused file present',
            )
        )

    claimed_ok = status in ('reused', 'generated', 'completed', 'success')
    claimed_error = status in ('error', 'failed')
    has_files = bool(bundle.reconstruction_files)

    scope = 'Files present under reconstructed-app for this investigation'
    limitations = [
        'Presence of reconstruction files does not imply behavioral correctness.',
        'Correctness requires validation results.',
    ]

    if claimed_error and has_files:
        return VerificationStatus.requires_review, supporting, contradictory, scope, limitations
    if claimed_error and not has_files:
        contradictory.append(
            _ref('recon:missing', 'missing', 'reconstructed-app/', available=False, note='No reconstruction files')
        )
        return VerificationStatus.verified, supporting, contradictory, scope, limitations + [
            'Claim that reconstruction failed is consistent with missing files.'
        ]
    if claimed_ok and has_files:
        return VerificationStatus.verified, supporting, contradictory, scope, limitations
    if claimed_ok and not has_files:
        contradictory.append(
            _ref('recon:missing', 'missing', 'reconstructed-app/', available=False, note='Claimed complete but files missing')
        )
        return VerificationStatus.contradicted, supporting, contradictory, scope, limitations
    if has_files:
        return VerificationStatus.partially_verified, supporting, contradictory, scope, limitations
    return VerificationStatus.not_verified, supporting, contradictory, scope, limitations


def check_repair_outcome(
    repair: dict[str, Any] | None,
) -> tuple[VerificationStatus, list[EvidenceReference], list[EvidenceReference], str, list[str], dict[str, Any]]:
    if not repair:
        return (
            VerificationStatus.not_verified,
            [],
            [_ref('repair:missing', 'missing', 'repair/repair_report.json', available=False)],
            'No repair report available',
            ['Repair outcomes cannot be verified without repair/repair_report.json'],
            {},
        )

    attempts = repair.get('attempts') or []
    initial = repair.get('initial_match_rate_percent')
    final = repair.get('final_match_rate_percent')
    best = repair.get('best_match_rate_percent')
    stopped = repair.get('stopped_reason')
    supporting = [
        _ref('repair:report', 'repair_report', 'repair/repair_report.json', note=str(repair.get('label') or ''))
    ]
    contradictory: list[EvidenceReference] = []
    successful = False
    for attempt in attempts:
        aid = attempt.get('attempt')
        supporting.append(
            _ref(
                f'repair:attempt:{aid}',
                'repair_attempt',
                f'repair/repair_report.json#attempts[{aid}]',
                note=(
                    f"status={attempt.get('status')} "
                    f"{attempt.get('prior_match_rate_percent')}%→{attempt.get('new_match_rate_percent')}%"
                ),
            )
        )
        if attempt.get('status') in ('perfect', 'improved') and attempt.get('new_match_rate_percent') is not None:
            if attempt.get('validation_artifact') or attempt.get('accepted_as_best'):
                successful = True
        if attempt.get('status') in ('perfect', 'improved') and not (
            attempt.get('validation_artifact') or attempt.get('new_match_rate_percent') is not None
        ):
            contradictory.append(
                _ref(
                    f'repair:attempt:{aid}:no-revalidation',
                    'repair_attempt',
                    f'repair/repair_report.json#attempts[{aid}]',
                    note='Success claimed without revalidation metrics',
                )
            )

    claimed_success = (
        stopped in ('all_valid_tests_passed', 'improved', 'accepted_best')
        or (isinstance(final, (int, float)) and isinstance(initial, (int, float)) and final > initial)
        or (isinstance(best, (int, float)) and isinstance(initial, (int, float)) and best > initial)
    )
    scope = f"{len(attempts)} recorded repair attempt(s); evaluation_kind={repair.get('evaluation_kind')}"
    limitations = [
        'Repair success is scoped to revalidation of the failing scenarios addressed.',
        'Controlled fault-injection evaluations are not organic Muse failures.',
    ]
    summary = {
        'evaluation_kind': repair.get('evaluation_kind'),
        'initial_match_rate_percent': initial,
        'final_match_rate_percent': final,
        'best_match_rate_percent': best,
        'stopped_reason': stopped,
        'attempts': len(attempts),
    }

    if claimed_success and successful and not contradictory:
        return VerificationStatus.verified, supporting, contradictory, scope, limitations, summary
    if claimed_success and not successful:
        return VerificationStatus.contradicted, supporting, contradictory, scope, limitations, summary
    if attempts and not claimed_success:
        return VerificationStatus.partially_verified, supporting, contradictory, scope, limitations, summary
    return VerificationStatus.not_verified, supporting, contradictory, scope, limitations, summary


def check_investigation_mode(
    bundle: ArtifactBundle,
    *,
    asserted_muse_fresh: bool = False,
) -> tuple[VerificationStatus, list[EvidenceReference], list[EvidenceReference], str, list[str]]:
    final = bundle.final_report or {}
    inv = bundle.investigation_report or {}
    mode = final.get('mode') or inv.get('mode')
    api_count = inv.get('api_request_count')
    supporting = [
        _ref(
            'investigation:mode',
            'investigation_report',
            'investigation/report.json',
            note=f'mode={mode} api_request_count={api_count}',
        )
    ]
    if final.get('mode') is not None:
        supporting.append(
            _ref('final:mode', 'final_report_stage', 'final_report.json', note=f'mode={final.get("mode")}')
        )
    contradictory: list[EvidenceReference] = []
    scope = f'Recorded investigation mode for job {bundle.investigation_id}'
    limitations = ['Mode is taken from recorded artifacts, not from UI labels.']

    if asserted_muse_fresh:
        if mode == 'muse' and (api_count is None or api_count > 0):
            return VerificationStatus.verified, supporting, contradictory, scope, limitations
        if mode == 'scripted' or api_count == 0:
            contradictory.append(
                _ref(
                    'mode:scripted',
                    'investigation_report',
                    'investigation/report.json',
                    note='Job used scripted mode / zero Meta requests',
                )
            )
            return VerificationStatus.contradicted, supporting, contradictory, scope, limitations
        return VerificationStatus.requires_review, supporting, contradictory, scope, limitations

    if mode in ('scripted', 'muse'):
        return VerificationStatus.verified, supporting, contradictory, scope, limitations
    return VerificationStatus.not_verified, supporting, contradictory, scope, limitations


def unsupported_claim(
    *,
    claim_id: str,
    investigation_id: str,
    target: str | None,
    feature: str | None,
    category: ClaimCategory,
    claim_text: str,
    scope: str,
    limitations: list[str],
    status: VerificationStatus = VerificationStatus.not_verified,
    problem_category: ProblemCategory | None = None,
    rule_id: str,
) -> VerifiedFinding:
    return VerifiedFinding(
        claim_id=claim_id,
        investigation_id=investigation_id,
        target_application=target,
        feature_investigated=feature,
        claim_category=category,
        claim_text=claim_text,
        supporting_evidence=[],
        contradictory_evidence=[],
        verification_status=status,
        verification_scope=scope,
        limitations=limitations,
        related_test_ids=[],
        timestamps=[],
        problem_category=problem_category,
        rule_id=rule_id,
    )


def detect_structured_contradictions(bundle: ArtifactBundle) -> list[ContradictionRecord]:
    out: list[ContradictionRecord] = []
    final = bundle.final_report or {}
    stages = final.get('stages') or {}

    # Validation pass count vs recomputed
    if bundle.validation:
        status, stats, supporting, contradictory, _scope, _lim = check_validation_pass_count(bundle.validation)
        stage_val = stages.get('validation') or {}
        if stage_val.get('passed') not in (None, stats['passed']):
            out.append(
                ContradictionRecord(
                    contradiction_id='val-pass-count-mismatch',
                    description='final_report validation.passed disagrees with recomputed valid passes',
                    claim_text=f"Report claims passed={stage_val.get('passed')}",
                    expected=str(stats['passed']),
                    observed=str(stage_val.get('passed')),
                    evidence=supporting + contradictory,
                )
            )
        if status == VerificationStatus.contradicted and contradictory:
            out.append(
                ContradictionRecord(
                    contradiction_id='val-summary-inconsistent',
                    description='Validation summary inconsistent with per-test statuses',
                    claim_text='Validation summary pass/fail/invalid counts',
                    expected=f"passed={stats['passed']} failed={stats['failed']} invalid={stats['invalid']}",
                    observed=str(
                        {
                            'passed': bundle.validation.get('passed'),
                            'failed': bundle.validation.get('failed'),
                            'invalid': bundle.validation.get('invalid'),
                        }
                    ),
                    evidence=contradictory,
                )
            )

    # Reconstruction claimed complete without files
    recon_stage = stages.get('reconstruction') or {}
    if str(recon_stage.get('status') or '') in ('reused', 'generated', 'completed', 'success'):
        if not bundle.reconstruction_files:
            out.append(
                ContradictionRecord(
                    contradiction_id='recon-missing-files',
                    description='Reconstruction marked complete but reconstructed-app files are missing',
                    claim_text=f"reconstruction.status={recon_stage.get('status')}",
                    expected='index.html, script.js, style.css present',
                    observed='missing reconstructed-app files',
                    evidence=[
                        _ref('recon:missing', 'missing', 'reconstructed-app/', available=False),
                        _ref('final:reconstruction', 'final_report_stage', 'final_report.json#stages.reconstruction'),
                    ],
                )
            )

    # Repair claimed success without successful attempt revalidation
    if bundle.repair:
        _st, _sup, contrad, _sc, _lim, summary = check_repair_outcome(bundle.repair)
        stopped = summary.get('stopped_reason')
        if stopped in ('all_valid_tests_passed',) and contrad:
            out.append(
                ContradictionRecord(
                    contradiction_id='repair-success-without-revalidation',
                    description='Repair stopped as success without recorded revalidation evidence',
                    claim_text=f'stopped_reason={stopped}',
                    expected='attempt with validation metrics / artifact',
                    observed='missing revalidation evidence on successful attempts',
                    evidence=contrad,
                )
            )

    # Mode contradiction: stage/meta implies muse but mode scripted
    inv = bundle.investigation_report or {}
    mode = final.get('mode') or inv.get('mode')
    meta_total = final.get('meta_api_requests_total')
    if mode == 'scripted' and isinstance(meta_total, int) and meta_total > 0:
        # Scripted investigation itself should be 0; repair/demo may add Meta — flag for review only if investigation api_request_count > 0
        if (inv.get('api_request_count') or 0) > 0:
            out.append(
                ContradictionRecord(
                    contradiction_id='mode-scripted-with-muse-requests',
                    description='Investigation mode is scripted but investigation recorded Meta API requests',
                    claim_text='mode=scripted',
                    expected='api_request_count=0 for scripted investigation',
                    observed=str(inv.get('api_request_count')),
                    evidence=[
                        _ref('investigation:mode', 'investigation_report', 'investigation/report.json'),
                    ],
                )
            )

    return out


def classify_problems(bundle: ArtifactBundle) -> list[ProblemRecord]:
    problems: list[ProblemRecord] = []
    stages = ((bundle.final_report or {}).get('stages') or {})

    if bundle.validation:
        _, stats, supporting, _, _, _ = check_validation_pass_count(bundle.validation)
        for tid in stats.get('test_ids_failed') or []:
            problems.append(
                ProblemRecord(
                    problem_id=f'mismatch:{tid}',
                    category=ProblemCategory.reconstruction_mismatch,
                    description=(
                        f'Validation test {tid} failed: reconstruction differed from original under the same actions. '
                        'This is a reconstruction mismatch, not proof that the original application is defective.'
                    ),
                    related_test_ids=[tid],
                    evidence=[
                        _ref(
                            f'validation:test:{tid}',
                            'validation_test',
                            f'validation/validation_results.json#tests[test_id={tid}]',
                        )
                    ],
                    notes=['Do not label the original app broken solely due to this mismatch.'],
                )
            )
        for tid in stats.get('test_ids_invalid') or []:
            problems.append(
                ProblemRecord(
                    problem_id=f'invalid:{tid}',
                    category=ProblemCategory.validation_execution_failure,
                    description=f'Validation test {tid} is invalid (execution/oracle issue), not a behavioral fail.',
                    related_test_ids=[tid],
                    evidence=supporting,
                )
            )

    recon = stages.get('reconstruction') or {}
    if str(recon.get('status') or '') in ('error', 'failed'):
        problems.append(
            ProblemRecord(
                problem_id='recon-generation-failure',
                category=ProblemCategory.reconstruction_generation_failure,
                description='Reconstruction stage recorded an error/failed status.',
                evidence=[_ref('final:reconstruction', 'final_report_stage', 'final_report.json#stages.reconstruction')],
            )
        )

    inv_status = (bundle.investigation_report or {}).get('status') or (bundle.final_report or {}).get('status')
    if inv_status in ('incomplete', 'budget_exhausted'):
        problems.append(
            ProblemRecord(
                problem_id='investigation-limitation',
                category=ProblemCategory.investigation_limitation,
                description=f'Investigation ended as {inv_status}; objectives may be incomplete.',
                evidence=[_ref('investigation:status', 'investigation_report', 'investigation/report.json')],
            )
        )

    # Muse / browser decision failures — surface for Simple + Developer reports.
    from reversex.meta import humanize_muse_error

    inv_events = list((bundle.investigation_report or {}).get('events') or [])
    for idx, event in enumerate(inv_events):
        if not isinstance(event, dict):
            continue
        status = str(event.get('status') or '')
        if status not in ('error', 'startup_error'):
            continue
        kind = str(event.get('error_kind') or '') or (
            'startup_error' if status == 'startup_error' else 'malformed_json'
        )
        step = event.get('step')
        step_bit = f' (step {step})' if step is not None else ''
        problems.append(
            ProblemRecord(
                problem_id=f'investigation-error:{idx}:{kind}',
                category=ProblemCategory.investigation_limitation,
                description=humanize_muse_error(kind, event.get('error')) + step_bit,
                evidence=[
                    _ref(
                        f'investigation:event:{idx}',
                        'investigation_event',
                        f'investigation/report.json#events[{idx}]',
                        note=f'error_kind={kind}',
                    )
                ],
                notes=[
                    f'error_kind={kind}',
                    'ReverseX did not invent a browser action from an unusable AI reply.',
                ],
            )
        )

    if inv_status in ('error', 'failed') and not any(
        p.problem_id.startswith('investigation-error:') for p in problems
    ):
        problems.append(
            ProblemRecord(
                problem_id='investigation-error',
                category=ProblemCategory.investigation_limitation,
                description=humanize_muse_error(None, 'The investigation ended with an error before completing its goals.'),
                evidence=[_ref('investigation:status', 'investigation_report', 'investigation/report.json')],
            )
        )

    isolation = (bundle.validation or {}).get('isolation') or {}
    if isolation.get('status') in ('error', 'failed', 'unavailable'):
        problems.append(
            ProblemRecord(
                problem_id='infra-preview',
                category=ProblemCategory.infrastructure_failure,
                description='Validation isolation/preview infrastructure reported a failure.',
                evidence=[_ref('validation:isolation', 'validation_summary', 'validation/validation_results.json#isolation')],
            )
        )

    if bundle.behavior_spec:
        for req in bundle.behavior_spec.get('requirements') or []:
            if req.get('kind') == 'hypothesis':
                problems.append(
                    ProblemRecord(
                        problem_id=f"hypothesis:{req.get('id')}",
                        category=ProblemCategory.unverified_hypothesis,
                        description=f"Hypothesis {req.get('id')} is not an observation-backed requirement.",
                        evidence=[
                            _ref(
                                f"spec:{req.get('id')}",
                                'behavior_spec',
                                f"specification/behavior_spec.frozen.json#requirements[id={req.get('id')}]",
                            )
                        ],
                    )
                )

    return problems


def default_untested_behaviors(target_id: str | None) -> list[str]:
    if target_id == 'calculator':
        return [
            'Division and multiplication operators (if not exercised)',
            'Floating-point edge cases beyond recorded holdouts',
            'Concurrent multi-user sessions',
            'Server-side persistence across browser profiles',
        ]
    if target_id == 'taskboard':
        return [
            'Task editing, deletion, and reordering (if not exercised)',
            'Multi-browser / multi-session persistence',
            'Server or database storage technology',
            'Accessibility and internationalization behaviors',
            'Unauthorized or malicious input beyond the validation suite',
        ]
    if target_id == 'contactpad':
        return [
            'Required-field validation for empty name, email, or message (if not exercised)',
            'Clear-form behavior after a successful send (if not exercised)',
            'Email-format validation beyond the recorded submission',
            'Persistence of messages after a browser refresh or new session',
            'Accessibility and internationalization behaviors',
        ]
    return [
        'Behaviors outside the recorded browser actions for this feature',
        'Persistence across refresh or new sessions (if not exercised)',
        'Server or database storage technology',
        'Accessibility and internationalization behaviors',
        'Inputs and edge cases beyond the recorded investigation',
    ]


def _pipeline_is_investigate_only(final: dict[str, Any] | None, inv: dict[str, Any] | None) -> bool:
    final = final or {}
    inv = inv or {}
    if str(final.get('pipeline') or inv.get('pipeline') or '').lower() == 'investigate_only':
        return True
    stages = final.get('stages') or {}
    recon = str((stages.get('reconstruction') or {}).get('status') or '').lower()
    validation = str((stages.get('validation') or {}).get('status') or '').lower()
    return recon == 'skipped' and validation == 'skipped'


def _element_label(event: dict[str, Any], element_id: str | None) -> str | None:
    if not element_id:
        return None
    for which in ('before', 'after'):
        elements = ((event.get(which) or {}).get('elements') or [])
        for el in elements:
            if el.get('element_id') == element_id and el.get('label'):
                return str(el.get('label'))
    return None


def _new_visible_lines(before: str, after: str) -> list[str]:
    before_lines = {ln.strip() for ln in before.splitlines() if ln.strip()}
    out: list[str] = []
    for ln in after.splitlines():
        text = ln.strip()
        if text and text not in before_lines:
            out.append(text)
    return out


def build_observation_findings(bundle: ArtifactBundle) -> list[VerifiedFinding]:
    """Deterministic behavioral findings from recorded browser observations (not Muse prose)."""
    findings: list[VerifiedFinding] = []
    inv = bundle.investigation_report or {}
    final = bundle.final_report or {}
    target = final.get('target_id') or inv.get('target_id')
    feature = inv.get('feature')
    job_id = bundle.investigation_id
    timestamps = [t for t in [final.get('updated_at'), inv.get('queued_at')] if t]
    events = _ok_events(inv)
    if not events:
        return findings

    fill_values: list[str] = []
    for event in events:
        decision = event.get('decision') or {}
        action = str(decision.get('action') or '')
        step = event.get('step')
        value = decision.get('value')
        element_id = decision.get('element_id')
        label = _element_label(event, str(element_id) if element_id else None)
        before = _visible(event, 'before')
        after = _visible(event, 'after')
        support = [
            _ref(
                f'event:step={step}:{action}',
                'investigation_event',
                f'investigation/report.json#events[step={step}]',
                note=f'action={action}',
            )
        ]

        if action == 'fill' and value not in (None, ''):
            shown = str(value)
            fill_values.append(shown)
            field = f' (“{label}”)' if label else ''
            findings.append(
                VerifiedFinding(
                    claim_id=f'{job_id}:fill:{step}',
                    investigation_id=job_id,
                    target_application=target,
                    feature_investigated=feature,
                    claim_category=ClaimCategory.investigation_observation,
                    claim_text=f'A form field{field} was filled with “{shown}”.',
                    supporting_evidence=support,
                    verification_status=VerificationStatus.verified,
                    verification_scope=f'Recorded fill action at investigation step {step}',
                    limitations=[
                        'Records that the investigation entered this value; it does not prove server-side storage.',
                    ],
                    timestamps=timestamps,
                    rule_id='rule.observation_fill',
                )
            )

        if action == 'click':
            control = f' labeled “{label}”' if label else ''
            findings.append(
                VerifiedFinding(
                    claim_id=f'{job_id}:click:{step}',
                    investigation_id=job_id,
                    target_application=target,
                    feature_investigated=feature,
                    claim_category=ClaimCategory.investigation_observation,
                    claim_text=f'A visible control{control} was clicked.',
                    supporting_evidence=support
                    + (
                        [
                            _ref(
                                f'event:step={step}:control-label',
                                'investigation_event',
                                f'investigation/report.json#events[step={step}].before.elements',
                                note=f'label={label}',
                            )
                        ]
                        if label
                        else []
                    ),
                    verification_status=VerificationStatus.verified,
                    verification_scope=f'Recorded click at investigation step {step}',
                    limitations=['Records the click observation only; outcome is covered by separate findings when evidence exists.'],
                    timestamps=timestamps,
                    rule_id='rule.observation_click',
                )
            )
            if before and after and after != before:
                new_lines = _new_visible_lines(before, after)
                excerpt = re.sub(r'\s+', ' ', (new_lines[0] if new_lines else after)).strip()
                if len(excerpt) > 160:
                    excerpt = excerpt[:157] + '…'
                findings.append(
                    VerifiedFinding(
                        claim_id=f'{job_id}:visible-change:{step}',
                        investigation_id=job_id,
                        target_application=target,
                        feature_investigated=feature,
                        claim_category=ClaimCategory.investigation_observation,
                        claim_text='Visible page content changed after a click.',
                        supporting_evidence=support
                        + [
                            _ref(
                                f'event:step={step}:after-text',
                                'investigation_event',
                                f'investigation/report.json#events[step={step}].after.visible_text',
                                note=f'new_or_changed_excerpt={excerpt}' if excerpt else 'after text differs from before',
                            )
                        ],
                        verification_status=VerificationStatus.verified,
                        verification_scope=f'Before/after visible_text comparison at step {step}',
                        limitations=[
                            'Establishes a visible text change only; it does not by itself prove business success.',
                        ],
                        timestamps=timestamps,
                        rule_id='rule.observation_visible_change',
                    )
                )
                for idx, phrase in enumerate(new_lines[:4]):
                    short = phrase if len(phrase) <= 140 else phrase[:137] + '…'
                    findings.append(
                        VerifiedFinding(
                            claim_id=f'{job_id}:new-text:{step}:{idx}',
                            investigation_id=job_id,
                            target_application=target,
                            feature_investigated=feature,
                            claim_category=ClaimCategory.investigation_observation,
                            claim_text=f'New visible content appeared after a click: “{short}”.',
                            supporting_evidence=[
                                _ref(
                                    f'event:step={step}:new-line:{idx}',
                                    'investigation_event',
                                    f'investigation/report.json#events[step={step}].after.visible_text',
                                    note=f'line={short}',
                                )
                            ],
                            verification_status=VerificationStatus.verified,
                            verification_scope=f'Line present in after.visible_text but not in before at step {step}',
                            limitations=['Taken from recorded DOM text; Muse stop reasons are not used as proof.'],
                            timestamps=timestamps,
                            rule_id='rule.observation_new_visible_text',
                        )
                    )
                for filled in fill_values:
                    if filled and filled in after and filled not in before:
                        safe = re.sub(r'[^a-zA-Z0-9]+', '-', filled).strip('-').lower()[:40] or 'value'
                        findings.append(
                            VerifiedFinding(
                                claim_id=f'{job_id}:submitted-value-visible:{step}:{safe}',
                                investigation_id=job_id,
                                target_application=target,
                                feature_investigated=feature,
                                claim_category=ClaimCategory.investigation_observation,
                                claim_text=f'A previously entered value “{filled}” appeared in the page after the click.',
                                supporting_evidence=[
                                    _ref(
                                        f'event:step={step}:value-in-after:{safe}',
                                        'investigation_event',
                                        f'investigation/report.json#events[step={step}].after.visible_text',
                                        note=f'value={filled}',
                                    )
                                ],
                                verification_status=VerificationStatus.verified,
                                verification_scope=f'Filled value visible in after text and absent from before at step {step}',
                                limitations=[
                                    'Shows the value became visible after the click; does not prove durable storage.',
                                ],
                                timestamps=timestamps,
                                rule_id='rule.observation_submitted_value_visible',
                            )
                        )

        # Structured control-value changes (textarea/input values, toggles, etc.)
        after_snap = event.get('after') or {}
        changes = list(after_snap.get('control_changes') or event.get('control_changes') or [])
        if not changes and action in ('fill', 'click', 'observe'):
            # Derive from element values when control_changes missing (compat with mixed artifacts).
            before_els = {
                (str(el.get('kind')), str(el.get('label'))): el for el in (event.get('before') or {}).get('elements') or []
            }
            for el in after_snap.get('elements') or []:
                if el.get('value_redacted'):
                    continue
                key = (str(el.get('kind')), str(el.get('label')))
                prev = before_els.get(key) or {}
                for field in ('value', 'checked', 'selected'):
                    if el.get(field) is None and prev.get(field) is None:
                        continue
                    if str(el.get(field)) != str(prev.get(field)):
                        changes.append(
                            {
                                'kind': el.get('kind'),
                                'label': el.get('label'),
                                'field': field,
                                'before': prev.get(field),
                                'after': el.get(field),
                                'element_id_after': el.get('element_id'),
                            }
                        )
        for idx, change in enumerate(changes[:8]):
            if not isinstance(change, dict):
                continue
            label = str(change.get('label') or 'control')
            field = str(change.get('field') or 'value')
            before_v = change.get('before')
            after_v = change.get('after')
            short_after = None if after_v is None else (str(after_v) if len(str(after_v)) <= 120 else str(after_v)[:117] + '…')
            findings.append(
                VerifiedFinding(
                    claim_id=f'{job_id}:control-change:{step}:{idx}',
                    investigation_id=job_id,
                    target_application=target,
                    feature_investigated=feature,
                    claim_category=ClaimCategory.investigation_observation,
                    claim_text=(
                        f'Control “{label}” {field} changed'
                        + (f' to “{short_after}”.' if short_after is not None else '.')
                    ),
                    supporting_evidence=[
                        _ref(
                            f'event:step={step}:control-change:{idx}',
                            'investigation_event',
                            f'investigation/report.json#events[step={step}].after.control_changes',
                            note=f'field={field} before={before_v!r} after={after_v!r}',
                        )
                    ],
                    verification_status=VerificationStatus.verified,
                    verification_scope=f'Structured before/after control {field} at step {step}',
                    limitations=[
                        'Reports an observed value/state difference only; does not explain application logic.',
                        'Sensitive values may be redacted in observations.',
                    ],
                    timestamps=timestamps,
                    rule_id='rule.observation_control_value_change',
                )
            )

    objectives = inv.get('objectives') or {}
    for key in ('feature_controls_observed', 'feature_interaction_attempted', 'page_response_observed'):
        obj = objectives.get(key) or {}
        if not obj.get('supported'):
            continue
        evidence = str(obj.get('evidence') or key)
        label_map = {
            'feature_controls_observed': 'Interactive controls for the investigated feature were visible.',
            'feature_interaction_attempted': 'An interaction with a visible control was recorded.',
            'page_response_observed': 'A page or control-value response was recorded after an interaction.',
        }
        findings.append(
            VerifiedFinding(
                claim_id=f'{job_id}:objective:{key}',
                investigation_id=job_id,
                target_application=target,
                feature_investigated=feature,
                claim_category=ClaimCategory.investigation_observation,
                claim_text=label_map[key],
                supporting_evidence=[
                    _ref(
                        f'objective:{key}',
                        'investigation_objective',
                        f'investigation/report.json#objectives.{key}',
                        note=evidence,
                    )
                ],
                verification_status=VerificationStatus.verified,
                verification_scope='Derived from recorded investigation objectives and events',
                limitations=['Objective support is derived from recorded events, not from agent free text.'],
                timestamps=timestamps,
                rule_id=f'rule.objective_{key}',
            )
        )

    return findings


def build_default_findings(bundle: ArtifactBundle) -> list[VerifiedFinding]:
    findings: list[VerifiedFinding] = []
    inv = bundle.investigation_report or {}
    final = bundle.final_report or {}
    target = final.get('target_id') or inv.get('target_id')
    feature = inv.get('feature')
    job_id = bundle.investigation_id
    timestamps = [t for t in [final.get('updated_at'), inv.get('queued_at')] if t]

    # Mode finding
    st, support, contrad, scope, lim = check_investigation_mode(bundle)
    findings.append(
        VerifiedFinding(
            claim_id=f'{job_id}:mode',
            investigation_id=job_id,
            target_application=target,
            feature_investigated=feature,
            claim_category=ClaimCategory.investigation_mode,
            claim_text=f'Investigation mode was recorded as {(final.get("mode") or inv.get("mode") or "unknown")}.',
            supporting_evidence=support,
            contradictory_evidence=contrad,
            verification_status=st,
            verification_scope=scope,
            limitations=lim,
            timestamps=timestamps,
            rule_id='rule.investigation_mode',
        )
    )

    # Evidence-grounded behavioral observations (generic; not Muse prose)
    findings.extend(build_observation_findings(bundle))

    investigate_only = _pipeline_is_investigate_only(final, inv)

    # Reload persistence + TaskBoard-specific overclaim guards (TaskBoard only)
    if target == 'taskboard' and inv:
        st, support, contrad, scope, lim = check_reload_persistence_predicates(inv)
        findings.append(
            VerifiedFinding(
                claim_id=f'{job_id}:reload-persistence',
                investigation_id=job_id,
                target_application=target,
                feature_investigated=feature,
                claim_category=ClaimCategory.reload_persistence,
                claim_text=(
                    'A created task remained visible after the tested browser reload.'
                    if st == VerificationStatus.verified
                    else 'Reload persistence was investigated for a created task.'
                ),
                supporting_evidence=support,
                contradictory_evidence=contrad,
                verification_status=st,
                verification_scope=scope,
                limitations=lim,
                related_test_ids=['persistence_after_reload'] if bundle.validation else [],
                timestamps=timestamps,
                rule_id='rule.reload_persistence',
            )
        )
        findings.append(
            unsupported_claim(
                claim_id=f'{job_id}:permanent-persistence',
                investigation_id=job_id,
                target=target,
                feature=feature,
                category=ClaimCategory.overgeneralization,
                claim_text='The task is permanently stored (e.g. in PostgreSQL) across all sessions.',
                scope='Not established by a single reload observation',
                limitations=[
                    'One reload does not prove durable storage technology or permanent persistence.',
                    'Storage implementation claims require an independent infrastructure oracle.',
                ],
                status=VerificationStatus.not_verified,
                rule_id='rule.reject_storage_overclaim',
            )
        )

    # Validation findings
    if bundle.validation:
        st, stats, support, contrad, scope, lim = check_validation_pass_count(bundle.validation)
        passed = stats['passed']
        findings.append(
            VerifiedFinding(
                claim_id=f'{job_id}:validation-match',
                investigation_id=job_id,
                target_application=target,
                feature_investigated=feature,
                claim_category=ClaimCategory.validation_match,
                claim_text=(
                    f'The reconstruction matched the original in {passed} tested scenario(s) '
                    f'({stats["behavioral_match_rate_percent"]}% of {stats["total_valid"]} valid tests).'
                ),
                supporting_evidence=support,
                contradictory_evidence=contrad,
                verification_status=st,
                verification_scope=scope,
                limitations=lim,
                related_test_ids=stats.get('test_ids_passed') or [],
                timestamps=timestamps,
                rule_id='rule.validation_pass_count',
            )
        )
        findings.append(
            unsupported_claim(
                claim_id=f'{job_id}:universal-equivalence',
                investigation_id=job_id,
                target=target,
                feature=feature,
                category=ClaimCategory.overgeneralization,
                claim_text='The reconstructed application is behaviorally equivalent for all possible inputs.',
                scope=f'Only {stats["total_valid"]} valid comparison tests were executed',
                limitations=[
                    'Finite test suites cannot prove universal behavioral equivalence.',
                    'Do not treat a high match rate as complete correctness.',
                ],
                status=VerificationStatus.not_verified,
                rule_id='rule.reject_universal_equivalence',
            )
        )
        findings.append(
            unsupported_claim(
                claim_id=f'{job_id}:bug-free',
                investigation_id=job_id,
                target=target,
                feature=feature,
                category=ClaimCategory.overgeneralization,
                claim_text='The reconstructed application is completely bug-free.',
                scope='Outside the executed validation suite',
                limitations=['Passing recorded tests does not prove absence of all defects.'],
                status=VerificationStatus.not_verified,
                rule_id='rule.reject_bug_free',
            )
        )

    # Reconstruction — distinguish intentional skip (Understand) from missing artifacts
    recon_stage = (final.get('stages') or {}).get('reconstruction') or {}
    if investigate_only or str(recon_stage.get('status') or '').lower() == 'skipped':
        findings.append(
            VerifiedFinding(
                claim_id=f'{job_id}:reconstruction-status',
                investigation_id=job_id,
                target_application=target,
                feature_investigated=feature,
                claim_category=ClaimCategory.reconstruction_status,
                claim_text='Reconstruction was not requested.',
                supporting_evidence=[
                    _ref(
                        'final:reconstruction-skipped',
                        'final_report_stage',
                        'final_report.json#stages.reconstruction',
                        note=str(recon_stage.get('note') or 'skipped'),
                    )
                ],
                verification_status=VerificationStatus.verified,
                verification_scope='Investigation goal/pipeline did not request reconstruction',
                limitations=[
                    'This is an intentional skip, not a reconstruction failure.',
                ],
                timestamps=timestamps,
                rule_id='rule.reconstruction_not_requested',
            )
        )
    else:
        st, support, contrad, scope, lim = check_reconstruction_status(bundle)
        findings.append(
            VerifiedFinding(
                claim_id=f'{job_id}:reconstruction-status',
                investigation_id=job_id,
                target_application=target,
                feature_investigated=feature,
                claim_category=ClaimCategory.reconstruction_status,
                claim_text=(
                    f'Reconstruction artifacts are available ({", ".join(bundle.reconstruction_files) or "none"}).'
                ),
                supporting_evidence=support,
                contradictory_evidence=contrad,
                verification_status=st,
                verification_scope=scope,
                limitations=lim,
                timestamps=timestamps,
                rule_id='rule.reconstruction_status',
            )
        )

    # Repair if present
    if bundle.repair:
        st, support, contrad, scope, lim, _summary = check_repair_outcome(bundle.repair)
        kind = bundle.repair.get('evaluation_kind')
        label = 'Controlled Fault-Injection Evaluation' if kind == 'controlled_fault_injection' else 'Pipeline repair'
        findings.append(
            VerifiedFinding(
                claim_id=f'{job_id}:repair-outcome',
                investigation_id=job_id,
                target_application=target,
                feature_investigated=feature,
                claim_category=ClaimCategory.repair_outcome,
                claim_text=(
                    f'{label}: match rate '
                    f'{bundle.repair.get("initial_match_rate_percent")}% → '
                    f'{bundle.repair.get("final_match_rate_percent")}%.'
                ),
                supporting_evidence=support,
                contradictory_evidence=contrad,
                verification_status=st,
                verification_scope=scope,
                limitations=lim
                + (
                    ['This is a controlled fault-injection evaluation, not an organic Muse failure.']
                    if kind == 'controlled_fault_injection'
                    else []
                ),
                timestamps=timestamps,
                rule_id='rule.repair_outcome',
            )
        )

    # Original defect claims are never auto-verified from mismatches alone.
    # Only surface this reject-guard when validation ran (otherwise it is noise).
    if bundle.validation:
        findings.append(
            unsupported_claim(
                claim_id=f'{job_id}:original-defective',
                investigation_id=job_id,
                target=target,
                feature=feature,
                category=ClaimCategory.original_defect,
                claim_text='The original application is defective.',
                scope='Requires an independent correctness oracle or explicit requirement',
                limitations=[
                    'Reconstruction mismatches do not prove the original application is broken.',
                    'Confirmed original defects need an oracle independent of the reconstruction.',
                ],
                status=VerificationStatus.not_verified,
                problem_category=ProblemCategory.confirmed_original_defect,
                rule_id='rule.reject_original_defect_without_oracle',
            )
        )

    if target == 'taskboard':
        findings.append(
            unsupported_claim(
                claim_id=f'{job_id}:postgres',
                investigation_id=job_id,
                target=target,
                feature=feature,
                category=ClaimCategory.storage_implementation,
                claim_text='The application stores data in PostgreSQL.',
                scope='Storage technology is not observed by browser investigation',
                limitations=['UI observations cannot establish database product or schema.'],
                status=VerificationStatus.not_verified,
                rule_id='rule.reject_storage_implementation',
            )
        )

    return findings


def verify_structured_claim(bundle: ArtifactBundle, claim: StructuredClaim) -> VerifiedFinding:
    """Verify a typed claim against loaded artifacts (no NLP keyword matching)."""
    inv = bundle.investigation_report or {}
    final = bundle.final_report or {}
    target = final.get('target_id') or inv.get('target_id')
    feature = inv.get('feature')
    job_id = bundle.investigation_id
    text = claim.claim_text or claim.claim_type

    if claim.claim_type == 'reload_persistence_observed':
        if not inv:
            return unsupported_claim(
                claim_id=f'{job_id}:proposed:reload',
                investigation_id=job_id,
                target=target,
                feature=feature,
                category=ClaimCategory.reload_persistence,
                claim_text=text,
                scope='Investigation report missing',
                limitations=['Cannot verify without investigation/report.json'],
                status=VerificationStatus.not_verified,
                rule_id='rule.reload_persistence',
            )
        st, support, contrad, scope, lim = check_reload_persistence_predicates(inv)
        return VerifiedFinding(
            claim_id=f'{job_id}:proposed:reload',
            investigation_id=job_id,
            target_application=target,
            feature_investigated=feature,
            claim_category=ClaimCategory.reload_persistence,
            claim_text=text,
            supporting_evidence=support,
            contradictory_evidence=contrad,
            verification_status=st,
            verification_scope=scope,
            limitations=lim,
            rule_id='rule.reload_persistence',
        )

    if claim.claim_type in ('validation_all_passed', 'validation_pass_count'):
        if not bundle.validation:
            return unsupported_claim(
                claim_id=f'{job_id}:proposed:validation',
                investigation_id=job_id,
                target=target,
                feature=feature,
                category=ClaimCategory.validation_match,
                claim_text=text,
                scope='Validation results missing',
                limitations=['Cannot verify without validation/validation_results.json'],
                status=VerificationStatus.not_verified,
                rule_id='rule.validation_pass_count',
            )
        asserted = claim.asserted_pass_count
        if claim.claim_type == 'validation_all_passed' and asserted is None:
            # Interpret as: all valid tests passed (failed == 0 and passed == total_valid)
            tests = bundle.validation.get('tests') or []
            asserted = sum(1 for t in tests if t.get('status') == 'pass')
            # Force contradiction path if fails exist by asserting full pass equality after recompute
        st, stats, support, contrad, scope, lim = check_validation_pass_count(
            bundle.validation,
            asserted_count=claim.asserted_pass_count,
        )
        if claim.claim_type == 'validation_all_passed':
            if stats['total_valid'] == 0:
                st = VerificationStatus.not_verified
            elif stats['failed'] == 0 and stats['passed'] == stats['total_valid'] and not contrad:
                st = VerificationStatus.verified
            elif stats['failed'] > 0:
                st = VerificationStatus.contradicted
                contrad = list(contrad) + [
                    _ref(
                        'validation:has-failures',
                        'validation_summary',
                        'validation/validation_results.json',
                        note=f"failed={stats['failed']}",
                    )
                ]
        return VerifiedFinding(
            claim_id=f'{job_id}:proposed:validation',
            investigation_id=job_id,
            target_application=target,
            feature_investigated=feature,
            claim_category=ClaimCategory.validation_match,
            claim_text=text,
            supporting_evidence=support,
            contradictory_evidence=contrad,
            verification_status=st,
            verification_scope=scope,
            limitations=lim,
            related_test_ids=stats.get('test_ids_passed') or [],
            rule_id='rule.validation_pass_count',
        )

    if claim.claim_type == 'reconstruction_completed':
        st, support, contrad, scope, lim = check_reconstruction_status(bundle)
        return VerifiedFinding(
            claim_id=f'{job_id}:proposed:recon',
            investigation_id=job_id,
            target_application=target,
            feature_investigated=feature,
            claim_category=ClaimCategory.reconstruction_status,
            claim_text=text,
            supporting_evidence=support,
            contradictory_evidence=contrad,
            verification_status=st,
            verification_scope=scope,
            limitations=lim,
            rule_id='rule.reconstruction_status',
        )

    if claim.claim_type == 'repair_succeeded':
        st, support, contrad, scope, lim, _ = check_repair_outcome(bundle.repair)
        return VerifiedFinding(
            claim_id=f'{job_id}:proposed:repair',
            investigation_id=job_id,
            target_application=target,
            feature_investigated=feature,
            claim_category=ClaimCategory.repair_outcome,
            claim_text=text,
            supporting_evidence=support,
            contradictory_evidence=contrad,
            verification_status=st,
            verification_scope=scope,
            limitations=lim,
            rule_id='rule.repair_outcome',
        )

    if claim.claim_type == 'muse_fresh_investigation':
        st, support, contrad, scope, lim = check_investigation_mode(bundle, asserted_muse_fresh=True)
        return VerifiedFinding(
            claim_id=f'{job_id}:proposed:muse',
            investigation_id=job_id,
            target_application=target,
            feature_investigated=feature,
            claim_category=ClaimCategory.investigation_mode,
            claim_text=text or 'Muse performed a fresh investigation.',
            supporting_evidence=support,
            contradictory_evidence=contrad,
            verification_status=st,
            verification_scope=scope,
            limitations=lim,
            rule_id='rule.investigation_mode',
        )

    if claim.claim_type == 'storage_postgres':
        return unsupported_claim(
            claim_id=f'{job_id}:proposed:postgres',
            investigation_id=job_id,
            target=target,
            feature=feature,
            category=ClaimCategory.storage_implementation,
            claim_text=text or 'Data is stored in PostgreSQL.',
            scope='Storage implementation is outside browser-observable evidence',
            limitations=['No browser observation establishes database technology.'],
            status=VerificationStatus.not_verified,
            rule_id='rule.reject_storage_implementation',
        )

    if claim.claim_type == 'permanent_persistence':
        return unsupported_claim(
            claim_id=f'{job_id}:proposed:permanent',
            investigation_id=job_id,
            target=target,
            feature=feature,
            category=ClaimCategory.overgeneralization,
            claim_text=text or 'Persistence is permanent across all sessions.',
            scope='Exceeds single-reload observation scope',
            limitations=['One reload cannot verify permanent persistence.'],
            status=VerificationStatus.not_verified,
            rule_id='rule.reject_storage_overclaim',
        )

    if claim.claim_type == 'universal_behavioral_equivalence':
        return unsupported_claim(
            claim_id=f'{job_id}:proposed:universal',
            investigation_id=job_id,
            target=target,
            feature=feature,
            category=ClaimCategory.overgeneralization,
            claim_text=text or 'Reconstruction matches the original for all behaviors.',
            scope='Finite validation suite only',
            limitations=['Cannot verify universal equivalence from a finite test set.'],
            status=VerificationStatus.not_verified,
            rule_id='rule.reject_universal_equivalence',
        )

    if claim.claim_type == 'bug_free_reconstruction':
        return unsupported_claim(
            claim_id=f'{job_id}:proposed:bugfree',
            investigation_id=job_id,
            target=target,
            feature=feature,
            category=ClaimCategory.overgeneralization,
            claim_text=text or 'Reconstruction is completely bug-free.',
            scope='Outside recorded tests',
            limitations=['Passing tests do not prove absence of all bugs.'],
            status=VerificationStatus.not_verified,
            rule_id='rule.reject_bug_free',
        )

    if claim.claim_type == 'original_app_defective':
        return unsupported_claim(
            claim_id=f'{job_id}:proposed:original-defect',
            investigation_id=job_id,
            target=target,
            feature=feature,
            category=ClaimCategory.original_defect,
            claim_text=text or 'The original application is defective.',
            scope='Requires independent correctness oracle',
            limitations=['Reconstruction mismatch ≠ original defect.'],
            status=VerificationStatus.not_verified,
            problem_category=ProblemCategory.confirmed_original_defect,
            rule_id='rule.reject_original_defect_without_oracle',
        )

    return unsupported_claim(
        claim_id=f'{job_id}:proposed:unknown',
        investigation_id=job_id,
        target=target,
        feature=feature,
        category=ClaimCategory.pipeline_consistency,
        claim_text=text,
        scope='Unknown claim type',
        limitations=['Claim type is not supported by the verification engine.'],
        status=VerificationStatus.requires_review,
        rule_id='rule.requires_review',
    )


def build_verified_results(
    artifacts_root: Path,
    investigation_id: str,
    *,
    extra_claims: list[StructuredClaim] | None = None,
) -> VerifiedResults:
    if not JOB_ID_RE.match(investigation_id):
        return VerifiedResults(
            investigation_id=investigation_id,
            generated_at=_utc_now(),
            availability='unavailable',
            notes=['Invalid investigation id'],
        )

    job_root = artifacts_root / investigation_id
    if not job_root.is_dir():
        return VerifiedResults(
            investigation_id=investigation_id,
            generated_at=_utc_now(),
            availability='unavailable',
            notes=['Investigation artifacts directory not found'],
        )

    bundle = load_artifact_bundle(artifacts_root, investigation_id)
    if not bundle.final_report and not bundle.investigation_report and not bundle.validation:
        return VerifiedResults(
            investigation_id=investigation_id,
            generated_at=_utc_now(),
            availability='unavailable',
            notes=['No investigation, validation, or final report artifacts could be loaded'],
            coverage_limitations=['Evidence incomplete — cannot produce verified findings'],
        )

    findings = build_default_findings(bundle)
    for claim in extra_claims or []:
        findings.append(verify_structured_claim(bundle, claim))

    contradictions = detect_structured_contradictions(bundle)
    problems = classify_problems(bundle)

    inv = bundle.investigation_report or {}
    final = bundle.final_report or {}
    target = final.get('target_id') or inv.get('target_id')

    def bucket(status: VerificationStatus) -> list[VerifiedFinding]:
        return [f for f in findings if f.verification_status == status]

    evidence_index: list[EvidenceReference] = []
    seen: set[str] = set()
    for f in findings:
        for ref in f.supporting_evidence + f.contradictory_evidence:
            if ref.ref_id not in seen:
                seen.add(ref.ref_id)
                evidence_index.append(ref)

    investigate_only = _pipeline_is_investigate_only(final, inv)
    expected_missing = set()
    if investigate_only:
        expected_missing = {
            'specification/behavior_spec.frozen.json',
            'validation/validation_results.json',
            'reconstructed-app/',
        }
    unexpected_missing = [m for m in bundle.missing_artifacts if m not in expected_missing]

    availability: Literal['complete', 'partial', 'unavailable'] = 'complete'
    if not bundle.investigation_report and not bundle.final_report:
        availability = 'unavailable'
    elif not bundle.investigation_report:
        availability = 'partial'
    elif investigate_only:
        # Understand / investigate_only: skipped recon+validation are expected, not incomplete.
        availability = 'partial' if unexpected_missing else 'complete'
    elif unexpected_missing or not bundle.validation:
        availability = 'partial'

    validation_summary = None
    if bundle.validation:
        _st, stats, *_rest = check_validation_pass_count(bundle.validation)
        validation_summary = {
            'passed': stats['passed'],
            'failed': stats['failed'],
            'invalid': stats['invalid'],
            'total_valid': stats['total_valid'],
            'behavioral_match_rate_percent': stats['behavioral_match_rate_percent'],
            'isolation_status': ((bundle.validation.get('isolation') or {}).get('status')),
        }

    repair_summary = None
    if bundle.repair:
        repair_summary = {
            'evaluation_kind': bundle.repair.get('evaluation_kind'),
            'label': bundle.repair.get('label'),
            'initial_match_rate_percent': bundle.repair.get('initial_match_rate_percent'),
            'final_match_rate_percent': bundle.repair.get('final_match_rate_percent'),
            'stopped_reason': bundle.repair.get('stopped_reason'),
            'attempts': len(bundle.repair.get('attempts') or []),
        }

    recon_status = (final.get('stages') or {}).get('reconstruction')
    if recon_status is not None:
        recon_status = {
            'status': recon_status.get('status'),
            'files': bundle.reconstruction_files,
            'executed': recon_status.get('executed'),
        }

    coverage = [
        'Findings are limited to recorded investigation events and validation suites.',
        'No Meta/Muse calls are made during verification.',
        'Storage technology and universal correctness claims are rejected by rule.',
    ]
    if investigate_only:
        coverage.append(
            'Reconstruction and independent validation were not requested for this investigation (Understand / investigate_only).'
        )
    if unexpected_missing:
        coverage.append('Missing artifacts: ' + ', '.join(unexpected_missing))
    elif bundle.missing_artifacts and not investigate_only:
        coverage.append('Missing artifacts: ' + ', '.join(bundle.missing_artifacts))

    return VerifiedResults(
        investigation_id=investigation_id,
        generated_at=_utc_now(),
        availability=availability,
        target_application=target,
        feature_investigated=inv.get('feature'),
        investigation_mode=final.get('mode') or inv.get('mode'),
        pipeline=final.get('pipeline'),
        investigation_status=final.get('status') or inv.get('status'),
        metadata={
            'missing_artifacts': bundle.missing_artifacts,
            'reconstruction_files': bundle.reconstruction_files,
        },
        verified_findings=bucket(VerificationStatus.verified),
        partially_verified_findings=bucket(VerificationStatus.partially_verified),
        unsupported_findings=bucket(VerificationStatus.not_verified),
        contradicted_findings=bucket(VerificationStatus.contradicted),
        requires_review_findings=bucket(VerificationStatus.requires_review),
        contradictions=contradictions,
        problems=problems,
        untested_behaviors=default_untested_behaviors(str(target) if target else None),
        reconstruction_status=recon_status,
        validation_summary=validation_summary,
        repair_summary=repair_summary,
        coverage_limitations=coverage,
        evidence_index=evidence_index,
        notes=[
            'Shared verified-results object for Simple and Developer reports.',
            'Verification checks observable predicates; it does not semantically interpret arbitrary prose.',
        ],
    )
