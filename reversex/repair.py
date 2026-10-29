"""Bounded, evidence-driven reconstruction repair.

Runs only after real differential validation failures (or a clearly labeled
controlled fault-injection evaluation). Muse never scores its own repair.
Original fixture source is never included in model context.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from reversex.reconstruct import (
    ALLOWED_FILENAMES,
    MuseReconstructor,
    ReconstructionPayload,
    assert_no_original_source_in_context,
    ensure_sample_app_paths_not_read,
    observation_only_spec_for_model,
    validate_reconstruction_response,
    verify_original_app_untouched,
    write_reconstructed_app,
    snapshot_sample_app_hashes,
)
from reversex.spec import BehaviorSpec, load_frozen_spec
from reversex.targets import AppTarget, get_target
from reversex.validate import ValidationReport, run_phase3_validation

MAX_REPAIR_ATTEMPTS = 2
MAX_REPAIR_API_CALLS = 2

REPAIR_SYSTEM = """You repair ONE static web reconstruction so its visible browser behavior better matches
the independent oracle observations and the frozen behavioral specification.
You receive: frozen observation requirements, the current reconstruction source files, failed test
descriptions, and browser-visible original vs reconstruction outcomes for those failed tests.
You do NOT receive original application source code.
Return the full repaired app as exactly three files: index.html, style.css, script.js.
Fix only behaviors evidenced by the failures. Do not invent unobserved features.
Do not include secrets, external network calls, or shell commands.
Hypotheses are not requirements.
"""


class FailedScenario(BaseModel):
    model_config = ConfigDict(extra='forbid')

    test_id: str
    description: str = ''
    input_values: dict[str, str | None] = Field(default_factory=dict)
    differences: list[str] = Field(default_factory=list)
    original_observed: dict[str, Any] = Field(default_factory=dict)
    reconstruction_observed: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class RepairAttemptRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    attempt: int
    failed_scenarios_addressed: list[str]
    meta_api_requests: int = 0
    changed_files: list[str] = Field(default_factory=list)
    candidate_dir: str
    validation_artifact: str | None = None
    prior_match_rate_percent: float | None = None
    new_match_rate_percent: float | None = None
    newly_passed_tests: list[str] = Field(default_factory=list)
    regressed_tests: list[str] = Field(default_factory=list)
    remaining_failures: list[str] = Field(default_factory=list)
    runtime_seconds: float | None = None
    status: Literal['improved', 'unchanged', 'regressed', 'error', 'perfect'] = 'unchanged'
    error: str | None = None
    accepted_as_best: bool = False


class RepairReport(BaseModel):
    model_config = ConfigDict(extra='forbid')

    evaluation_kind: Literal['pipeline_repair', 'controlled_fault_injection']
    label: str
    target_id: str
    max_attempts: int = MAX_REPAIR_ATTEMPTS
    initial_match_rate_percent: float | None
    final_match_rate_percent: float | None
    initial_failed: list[str] = Field(default_factory=list)
    attempts: list[RepairAttemptRecord] = Field(default_factory=list)
    best_candidate_dir: str | None = None
    best_match_rate_percent: float | None = None
    meta_api_requests_total: int = 0
    stopped_reason: str = ''
    original_fixture_untouched: bool = True
    notes: list[str] = Field(default_factory=list)


def collect_failed_scenarios(validation: ValidationReport | dict[str, Any]) -> list[FailedScenario]:
    data = validation.model_dump(mode='json') if isinstance(validation, ValidationReport) else validation
    failed: list[FailedScenario] = []
    for test in data.get('tests') or []:
        if test.get('status') != 'fail':
            continue
        orig = (test.get('original') or {}).get('observed_state') or {}
        recon = (test.get('reconstruction') or {}).get('observed_state') or {}
        failed.append(FailedScenario(
            test_id=str(test.get('test_id') or 'unknown'),
            description=str(test.get('description') or ''),
            input_values=dict(test.get('input_values') or {}),
            differences=list(test.get('differences') or []),
            original_observed=dict(orig),
            reconstruction_observed=dict(recon),
            error=test.get('error'),
        ))
    return failed


def read_reconstruction_files(recon_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in sorted(ALLOWED_FILENAMES):
        path = recon_dir / name
        if not path.is_file():
            raise FileNotFoundError(f'missing reconstruction file: {name}')
        files[name] = path.read_text(encoding='utf-8')
    return files


def file_hashes(recon_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in sorted(ALLOWED_FILENAMES):
        path = recon_dir / name
        if path.is_file():
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def changed_filenames(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed = []
    for name in sorted(ALLOWED_FILENAMES):
        if before.get(name) != after.get(name):
            changed.append(name)
    return changed


def build_repair_model_context(
    *,
    frozen_spec: BehaviorSpec,
    current_files: dict[str, str],
    failures: list[FailedScenario],
) -> dict[str, Any]:
    """Assemble Muse repair input with code-enforced exclusion of original source."""
    spec_ctx = observation_only_spec_for_model(frozen_spec)
    context = {
        'task': 'bounded_reconstruction_repair',
        'frozen_behavior_spec': spec_ctx,
        'current_reconstruction_files': [
            {'filename': name, 'content': current_files[name]} for name in sorted(ALLOWED_FILENAMES)
        ],
        'failed_scenarios': [f.model_dump(mode='json') for f in failures],
        'instructions': [
            'Repair visible behavioral mismatches listed in failed_scenarios.',
            'Match original_observed outcomes where evidenced.',
            'Return complete index.html, style.css, and script.js.',
            'Do not request or assume access to original application source.',
        ],
        'excluded_from_model_context': list(frozen_spec.excluded_from_model_context),
    }
    assert_repair_context_safe(context)
    ensure_sample_app_paths_not_read([])
    return context


def assert_repair_context_safe(context: dict[str, Any]) -> None:
    """Reject original-source fingerprints anywhere in the repair payload."""
    # Reuse reconstruction marker check on the spec portion.
    frozen = context.get('frozen_behavior_spec') or {}
    assert_no_original_source_in_context(frozen)

    blob = json.dumps(context, ensure_ascii=True).lower()
    # Do not scan reconstruction file contents for markers that Muse itself may
    # have generated — only reject known *original fixture* fingerprints that
    # must never appear in the repair prompt outside reconstruction files.
    scanned = {
        'failed_scenarios': context.get('failed_scenarios'),
        'instructions': context.get('instructions'),
        'task': context.get('task'),
        'excluded_from_model_context': context.get('excluded_from_model_context'),
        'frozen_behavior_spec': {
            'observation_requirements': frozen.get('observation_requirements'),
            'hypotheses_not_requirements': frozen.get('hypotheses_not_requirements'),
            'feature': frozen.get('feature'),
            'global_uncertainties': frozen.get('global_uncertainties'),
        },
    }
    scanned_blob = json.dumps(scanned, ensure_ascii=True).lower()
    forbidden = (
        'data-reversex-original="calculator-v1"',
        'reversex_fixture_tasks_v1',
        "getelementbyid('task-form')",
        'getelementbyid("task-form")',
        "getelementbyid('num-a')",
        "getelementbyid('btn-add')",
        'localstorage.setitem',
    )
    for marker in forbidden:
        if marker in scanned_blob:
            raise RuntimeError(f'repair context contains forbidden original-source marker: {marker}')

    # Credentials must never appear in non-file repair fields.
    sensitive = json.dumps({
        'failed_scenarios': context.get('failed_scenarios'),
        'instructions': context.get('instructions'),
        'task': context.get('task'),
    }, ensure_ascii=True).lower()
    for secret_key in ('model_api_key', 'authorization: bearer', 'api_key='):
        if secret_key in sensitive:
            raise RuntimeError('repair context must not include API credentials')


def calculate_improvement(
    *,
    prior: ValidationReport | dict[str, Any],
    new: ValidationReport | dict[str, Any],
) -> tuple[list[str], list[str], list[str], float | None, float | None]:
    prior_d = prior.model_dump(mode='json') if isinstance(prior, ValidationReport) else prior
    new_d = new.model_dump(mode='json') if isinstance(new, ValidationReport) else new
    prior_status = {t['test_id']: t['status'] for t in prior_d.get('tests') or [] if t.get('test_id')}
    new_status = {t['test_id']: t['status'] for t in new_d.get('tests') or [] if t.get('test_id')}
    newly_passed = [
        tid for tid, st in new_status.items()
        if st == 'pass' and prior_status.get(tid) == 'fail'
    ]
    regressed = [
        tid for tid, st in new_status.items()
        if st == 'fail' and prior_status.get(tid) == 'pass'
    ]
    remaining = [tid for tid, st in new_status.items() if st == 'fail']
    return (
        newly_passed,
        regressed,
        remaining,
        prior_d.get('behavioral_match_rate_percent'),
        new_d.get('behavioral_match_rate_percent'),
    )


class MuseRepairClient(MuseReconstructor):
    """httpx Muse client for repair; reuses reconstruction schema/validation."""

    def generate_repair(self, context: dict[str, Any]) -> tuple[ReconstructionPayload, dict]:
        if self.request_count >= MAX_REPAIR_API_CALLS:
            raise RuntimeError('repair API budget exhausted')
        assert_repair_context_safe(context)
        user_content = (
            'REPAIR_CONTEXT_JSON (failed oracle evidence + current reconstruction; not original source):\n'
            + json.dumps(context)
        )
        self.request_count += 1
        response = self._http.post(
            '/chat/completions',
            json={
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': REPAIR_SYSTEM},
                    {'role': 'user', 'content': user_content},
                ],
                'response_format': {
                    'type': 'json_schema',
                    'json_schema': {
                        'name': 'ReverseXReconstruction',
                        'strict': True,
                        'schema': {
                            'type': 'object',
                            'properties': {
                                'files': {
                                    'type': 'array',
                                    'minItems': 3,
                                    'maxItems': 3,
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'filename': {
                                                'type': 'string',
                                                'enum': ['index.html', 'style.css', 'script.js'],
                                            },
                                            'content': {'type': 'string'},
                                        },
                                        'required': ['filename', 'content'],
                                        'additionalProperties': False,
                                    },
                                },
                                'notes': {'type': 'string'},
                            },
                            'required': ['files', 'notes'],
                            'additionalProperties': False,
                        },
                    },
                },
            },
        )
        summary = {
            'http_status': response.status_code,
            'model': self.model,
            'request_index': self.request_count,
        }
        if response.status_code >= 400:
            raise ValueError(f'Meta API error {response.status_code}: {response.text[:240]}')
        data = response.json()
        message = data['choices'][0]['message']
        content = message.get('content')
        if not content and isinstance(message.get('parsed'), dict):
            payload = validate_reconstruction_response(message['parsed'])
        elif content:
            payload = validate_reconstruction_response(content)
        else:
            raise ValueError('Meta returned an empty repair')
        usage = data.get('usage') or {}
        summary['usage'] = {
            'prompt_tokens': usage.get('prompt_tokens'),
            'completion_tokens': usage.get('completion_tokens'),
            'total_tokens': usage.get('total_tokens'),
        }
        summary['filenames'] = [f.filename for f in payload.files]
        return payload, summary


def _rate(report: ValidationReport | dict | None) -> float | None:
    if report is None:
        return None
    if isinstance(report, ValidationReport):
        return report.behavioral_match_rate_percent
    return report.get('behavioral_match_rate_percent')


def run_bounded_repair(
    *,
    output_root: Path,
    frozen_spec_path: Path,
    initial_recon_dir: Path,
    initial_validation: ValidationReport | dict[str, Any],
    target: AppTarget,
    evaluation_kind: Literal['pipeline_repair', 'controlled_fault_injection'] = 'pipeline_repair',
    label: str = 'Bounded reconstruction repair',
    max_attempts: int = MAX_REPAIR_ATTEMPTS,
    client: MuseRepairClient | None = None,
) -> RepairReport:
    """Attempt up to max_attempts Muse repairs; never replaces best with worse."""
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    fixture_hashes = snapshot_sample_app_hashes(target.fixture_dir)
    failures = collect_failed_scenarios(initial_validation)
    initial_rate = _rate(initial_validation)
    report = RepairReport(
        evaluation_kind=evaluation_kind,
        label=label,
        target_id=target.id,
        max_attempts=max_attempts,
        initial_match_rate_percent=initial_rate,
        final_match_rate_percent=initial_rate,
        initial_failed=[f.test_id for f in failures],
        best_candidate_dir=str(initial_recon_dir),
        best_match_rate_percent=initial_rate,
        notes=[],
    )

    if not failures:
        report.stopped_reason = 'no_failed_scenarios'
        report.notes.append('Repair skipped: validation had no failed tests.')
        _write_repair_report(output_root, report)
        return report

    if initial_rate is None:
        report.stopped_reason = 'validation_unavailable'
        report.notes.append('Repair skipped: initial match rate unavailable (validation blocked).')
        _write_repair_report(output_root, report)
        return report

    sha_path = frozen_spec_path.parent / 'behavior_spec.sha256'
    expected = sha_path.read_text(encoding='utf-8').strip() if sha_path.is_file() else None
    frozen = load_frozen_spec(frozen_spec_path, expected_sha256=expected)
    working_dir = initial_recon_dir
    working_validation: ValidationReport | dict[str, Any] = initial_validation
    repairer = client or MuseRepairClient()
    best_rate = initial_rate if initial_rate is not None else -1.0

    for attempt in range(1, max_attempts + 1):
        started = time.monotonic()
        attempt_dir = output_root / f'attempt_{attempt}'
        candidate_dir = attempt_dir / 'reconstructed-app'
        val_dir = attempt_dir / 'validation'
        attempt_failures = collect_failed_scenarios(working_validation)
        record = RepairAttemptRecord(
            attempt=attempt,
            failed_scenarios_addressed=[f.test_id for f in attempt_failures],
            candidate_dir=str(candidate_dir),
            prior_match_rate_percent=_rate(working_validation),
        )
        try:
            current_files = read_reconstruction_files(working_dir)
            before_hashes = file_hashes(working_dir)
            context = build_repair_model_context(
                frozen_spec=frozen,
                current_files=current_files,
                failures=attempt_failures,
            )
            payload, meta_summary = repairer.generate_repair(context)
            record.meta_api_requests = 1
            report.meta_api_requests_total += 1
            write_reconstructed_app(payload, candidate_dir)
            after_hashes = file_hashes(candidate_dir)
            record.changed_files = changed_filenames(before_hashes, after_hashes)
            if not verify_original_app_untouched(target.fixture_dir, fixture_hashes):
                raise RuntimeError('original fixture changed during repair — aborting')

            # Fresh holdouts: run_phase3_validation regenerates holdouts each call.
            new_validation = run_phase3_validation(
                reconstructed_dir=candidate_dir,
                output_dir=val_dir,
                original_origin=target.origin,
                suite=target.validation_suite,
            )
            record.validation_artifact = str(val_dir / 'validation_results.json')
            newly_passed, regressed, remaining, prior_rate, new_rate = calculate_improvement(
                prior=working_validation,
                new=new_validation,
            )
            record.newly_passed_tests = newly_passed
            record.regressed_tests = regressed
            record.remaining_failures = remaining
            record.prior_match_rate_percent = prior_rate
            record.new_match_rate_percent = new_rate
            record.runtime_seconds = round(time.monotonic() - started, 2)

            if new_rate is None:
                record.status = 'error'
                record.error = 'revalidation blocked or unavailable'
                report.attempts.append(record)
                report.stopped_reason = 'revalidation_blocked'
                break

            if new_rate >= 100.0 and not remaining:
                record.status = 'perfect'
            elif regressed or (new_rate is not None and new_rate < best_rate):
                record.status = 'regressed'
            elif newly_passed and (new_rate is not None and new_rate > (prior_rate or -1)):
                record.status = 'improved'
            elif new_rate is not None and new_rate > best_rate:
                record.status = 'improved'
            else:
                record.status = 'unchanged'

            # Never replace the best candidate with a worse result.
            if new_rate is not None and new_rate >= best_rate and record.status != 'regressed':
                best_rate = new_rate
                report.best_candidate_dir = str(candidate_dir)
                report.best_match_rate_percent = new_rate
                record.accepted_as_best = True
                working_dir = candidate_dir
                working_validation = new_validation
            else:
                record.accepted_as_best = False

            report.attempts.append(record)
            if record.status == 'perfect':
                report.stopped_reason = 'all_valid_tests_passed'
                break
            if repairer.request_count >= MAX_REPAIR_API_CALLS:
                report.stopped_reason = 'repair_api_budget_reached'
                break
        except Exception as exc:
            record.status = 'error'
            record.error = str(exc)[:400]
            record.runtime_seconds = round(time.monotonic() - started, 2)
            report.attempts.append(record)
            report.stopped_reason = 'nonrecoverable_error'
            report.notes.append(f'attempt {attempt} error: {exc!s}'[:300])
            break
    else:
        report.stopped_reason = 'max_attempts_reached'

    report.final_match_rate_percent = report.best_match_rate_percent
    report.original_fixture_untouched = verify_original_app_untouched(target.fixture_dir, fixture_hashes)
    # Copy best candidate aside for stable reference (never overwrite initial recon).
    if report.best_candidate_dir and Path(report.best_candidate_dir).resolve() != initial_recon_dir.resolve():
        best_copy = output_root / 'best_candidate'
        if best_copy.exists():
            shutil.rmtree(best_copy)
        shutil.copytree(report.best_candidate_dir, best_copy)
        report.notes.append(f'Best candidate copied to {best_copy}')
    _write_repair_report(output_root, report)
    return report


def _write_repair_report(output_root: Path, report: RepairReport) -> None:
    (output_root / 'repair_report.json').write_text(
        json.dumps(report.model_dump(mode='json'), indent=2),
        encoding='utf-8',
    )


def introduce_controlled_defect(source_dir: Path, dest_dir: Path, *, defect_id: str = 'calc_add_off_by_one') -> dict[str, str]:
    """Copy a reconstruction and inject one documented behavioral defect.

    Does not modify the source reconstruction directory.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in ALLOWED_FILENAMES:
        src = source_dir / name
        if not src.is_file():
            raise FileNotFoundError(src)
        shutil.copy2(src, dest_dir / name)

    script = dest_dir / 'script.js'
    text = script.read_text(encoding='utf-8')
    # Prefer a surgical off-by-one on addition when an add expression exists.
    defect_note = {
        'defect_id': defect_id,
        'description': 'Addition returns left+right+1 (off-by-one) to trigger oracle failure',
        'file': 'script.js',
    }
    patched = text
    replacements = [
        ('var out = parsed.a + parsed.b;', 'var out = parsed.a + parsed.b + 1; /* CONTROLLED_DEFECT_OFF_BY_ONE */'),
        ('parsed.a + parsed.b', 'parsed.a + parsed.b + 1 /* CONTROLLED_DEFECT_OFF_BY_ONE */'),
        ('left.value + right.value', 'left.value + right.value + 1 /* CONTROLLED_DEFECT_OFF_BY_ONE */'),
        ('a + b', 'a + b + 1 /* CONTROLLED_DEFECT_OFF_BY_ONE */'),
    ]
    for old, new in replacements:
        if old in patched and 'CONTROLLED_DEFECT_OFF_BY_ONE' not in patched:
            patched = patched.replace(old, new, 1)
            break
    if 'CONTROLLED_DEFECT_OFF_BY_ONE' not in patched:
        # Last resort: replace Add click result assignment after the fact (bubble phase).
        patched = text + (
            '\n/* CONTROLLED_DEFECT_OFF_BY_ONE */\n'
            '(function(){\n'
            '  document.querySelectorAll("button").forEach(btn => {\n'
            '    const label=(btn.getAttribute("aria-label")||btn.textContent||"").trim().toLowerCase();\n'
            '    if(label!=="add") return;\n'
            '    btn.addEventListener("click", function(){\n'
            '      setTimeout(function(){\n'
            '        const inputs=[...document.querySelectorAll("input")];\n'
            '        if(inputs.length<2) return;\n'
            '        const a=Number(inputs[0].value), b=Number(inputs[1].value);\n'
            '        if(!Number.isFinite(a)||!Number.isFinite(b)) return;\n'
            '        const r=document.querySelector("#result,[data-testid=result],.result");\n'
            '        if(r) r.textContent="Result: "+String(a+b+1);\n'
            '      }, 0);\n'
            '    });\n'
            '  });\n'
            '})();\n'
        )
    script.write_text(patched, encoding='utf-8', newline='\n')
    (dest_dir / 'CONTROLLED_DEFECT.json').write_text(json.dumps(defect_note, indent=2), encoding='utf-8')
    return defect_note
