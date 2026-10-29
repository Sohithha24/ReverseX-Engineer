"""Independent behavioral oracle: original app vs reconstruction.

No Meta API calls. No sample_app source reads. Pass/fail from executable assertions.
"""
from __future__ import annotations

import json
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from reversex.browser import SafeBrowser
from reversex.contracts import Decision
from reversex.preview import PREVIEW_PORT, prepare_preview, stop_preview, write_preview_status

DEFAULT_ORIGINAL = 'http://127.0.0.1:8001'
DEFAULT_RECONSTRUCTION = f'http://127.0.0.1:{PREVIEW_PORT}'
TEST_TIMEOUT_SECONDS = 45

ResultStatus = Literal['pass', 'fail', 'invalid']


class ObservedState(BaseModel):
    model_config = ConfigDict(extra='forbid')

    task_visible: bool | None = None
    tasks_visible: list[str] = Field(default_factory=list)
    validation_error_present: bool | None = None
    validation_message_normalized: str | None = None
    empty_state_visible: bool | None = None
    visible_text_excerpt: str = ''
    # Generic outcome fields used by non-TaskBoard suites (e.g. calculator).
    result_text: str | None = None
    contains_tokens: list[str] = Field(default_factory=list)


class SideObservation(BaseModel):
    model_config = ConfigDict(extra='forbid')

    origin: str
    observed_state: ObservedState
    screenshot: str | None = None
    error: str | None = None


class BehavioralCaseResult(BaseModel):
    model_config = ConfigDict(extra='forbid')

    test_id: str
    description: str
    input_values: dict[str, str | None]
    original: SideObservation
    reconstruction: SideObservation
    status: ResultStatus
    differences: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    error: str | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra='forbid')

    phase: Literal['3'] = '3'
    original_origin: str
    reconstruction_origin: str
    isolation: dict[str, Any]
    holdout_values: dict[str, str]
    tests: list[BehavioralCaseResult]
    total_valid: int
    passed: int
    failed: int
    invalid: int
    behavioral_match_rate_percent: float | None
    meta_api_requests: int = 0
    notes: list[str] = Field(default_factory=list)


_VALIDATION_PATTERNS = (
    re.compile(r'task name is required', re.I),
    re.compile(r'both numbers are required', re.I),
    re.compile(r'required', re.I),
)
_EMPTY_STATE_PATTERNS = (
    re.compile(r'no tasks yet', re.I),
)


def normalize_visible_text(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip())


def extract_validation_message(visible_text: str) -> str | None:
    text = visible_text or ''
    for pattern in _VALIDATION_PATTERNS:
        match = pattern.search(text)
        if match:
            # Prefer the known Phase 1B phrase when present.
            if 'task name is required' in text.lower():
                return 'task name is required'
            return match.group(0).lower()
    return None


def build_observed_state(visible_text: str, *, expected_tasks: list[str] | None = None) -> ObservedState:
    text = visible_text or ''
    normalized = normalize_visible_text(text)
    validation = extract_validation_message(text)
    empty = any(p.search(text) for p in _EMPTY_STATE_PATTERNS)
    found: list[str] = []
    for name in expected_tasks or []:
        if name and name in text:
            found.append(name)
    primary = expected_tasks[0] if expected_tasks else None
    task_visible = (primary in text) if primary else (None if expected_tasks is None else False)
    return ObservedState(
        task_visible=task_visible,
        tasks_visible=found,
        validation_error_present=bool(validation),
        validation_message_normalized=validation,
        empty_state_visible=bool(empty),
        visible_text_excerpt=normalized[:400],
    )


def compare_observed_states(
    original: ObservedState,
    reconstruction: ObservedState,
    *,
    compare_validation: bool = False,
    compare_tasks: bool = False,
    compare_empty: bool = False,
    compare_result: bool = False,
    compare_tokens: bool = False,
) -> list[str]:
    diffs: list[str] = []
    if compare_validation:
        if original.validation_error_present != reconstruction.validation_error_present:
            diffs.append(
                f'validation_error_present original={original.validation_error_present} '
                f'reconstruction={reconstruction.validation_error_present}'
            )
        elif (
            original.validation_message_normalized
            and reconstruction.validation_message_normalized
            and original.validation_message_normalized != reconstruction.validation_message_normalized
        ):
            # Soft: both present but wording differs — still a difference if normalized phrases differ.
            if not (
                original.validation_message_normalized in reconstruction.validation_message_normalized
                or reconstruction.validation_message_normalized in original.validation_message_normalized
            ):
                diffs.append(
                    f'validation_message original={original.validation_message_normalized!r} '
                    f'reconstruction={reconstruction.validation_message_normalized!r}'
                )
    if compare_tasks:
        if original.task_visible != reconstruction.task_visible:
            diffs.append(
                f'task_visible original={original.task_visible} reconstruction={reconstruction.task_visible}'
            )
        o_set, r_set = set(original.tasks_visible), set(reconstruction.tasks_visible)
        if o_set != r_set:
            diffs.append(f'tasks_visible original={sorted(o_set)} reconstruction={sorted(r_set)}')
    if compare_empty:
        if original.empty_state_visible != reconstruction.empty_state_visible:
            diffs.append(
                f'empty_state_visible original={original.empty_state_visible} '
                f'reconstruction={reconstruction.empty_state_visible}'
            )
    if compare_result:
        o_res = (original.result_text or '').strip()
        r_res = (reconstruction.result_text or '').strip()
        if o_res != r_res:
            diffs.append(f'result_text original={o_res!r} reconstruction={r_res!r}')
    if compare_tokens:
        o_tok = set(original.contains_tokens)
        r_tok = set(reconstruction.contains_tokens)
        if o_tok != r_tok:
            diffs.append(f'contains_tokens original={sorted(o_tok)} reconstruction={sorted(r_tok)}')
    return diffs


def calculate_match_rate(results: list[BehavioralCaseResult]) -> tuple[int, int, int, int, float | None]:
    valid = [r for r in results if r.status in ('pass', 'fail')]
    passed = sum(1 for r in valid if r.status == 'pass')
    failed = sum(1 for r in valid if r.status == 'fail')
    invalid = sum(1 for r in results if r.status == 'invalid')
    total_valid = len(valid)
    rate = None if total_valid == 0 else round(100.0 * passed / total_valid, 2)
    return total_valid, passed, failed, invalid, rate


def make_holdout_values() -> dict[str, str]:
    """Fresh TaskBoard values chosen at validation time — never sent to Muse."""
    token = secrets.token_hex(4)
    return {
        'task_a': f'Holdout Briefing {token}',
        'task_b': f'Holdout Followup {token}',
        'whitespace': '   \t  ',
    }


def make_calculator_holdouts() -> dict[str, str]:
    """Fresh numeric holdouts chosen at validation time — never sent to Muse."""
    # Avoid tiny constants that commonly appear in demos (1,2,3).
    a = 10 + secrets.randbelow(40)  # 10..49
    b = 10 + secrets.randbelow(40)
    if a == b:
        b = a + 7
    neg_a = -(10 + secrets.randbelow(20))
    neg_b = 5 + secrets.randbelow(15)
    return {
        'add_a': str(a),
        'add_b': str(b),
        'sub_a': str(a + 3),
        'sub_b': str(b),
        'neg_a': str(neg_a),
        'neg_b': str(neg_b),
    }


def extract_result_text(visible_text: str) -> str | None:
    """Best-effort visible result extraction without requiring identical DOM ids."""
    text = visible_text or ''
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        if line.lower() in ('result', 'result:'):
            if idx + 1 < len(lines):
                candidate = lines[idx + 1]
                if re.fullmatch(r'-?\d+(?:\.\d+)?', candidate):
                    return candidate
        if line.lower().startswith('result:'):
            rest = line.split(':', 1)[1].strip()
            if re.fullmatch(r'-?\d+(?:\.\d+)?', rest):
                return rest
    # Fallback: last standalone number-like token in the page.
    nums = re.findall(r'(?m)^-?\d+(?:\.\d+)?$', text)
    if nums:
        return nums[-1]
    return None


def build_calculator_state(visible_text: str, *, expect_tokens: list[str] | None = None) -> ObservedState:
    text = visible_text or ''
    validation = extract_validation_message(text)
    result = extract_result_text(text)
    tokens = [t for t in (expect_tokens or []) if t and t in text]
    return ObservedState(
        validation_error_present=bool(validation),
        validation_message_normalized=validation,
        result_text=result,
        contains_tokens=tokens,
        visible_text_excerpt=normalize_visible_text(text)[:400],
    )


@dataclass
class _Targets:
    original: str
    reconstruction: str


def _find_controls(browser: SafeBrowser):
    snap = browser.snapshot()
    task_input = next((e for e in snap.elements if e.kind in ('input', 'textarea')), None)
    add_btn = next(
        (e for e in snap.elements if e.kind == 'button' and 'add' in e.label.lower()),
        next((e for e in snap.elements if e.kind == 'button'), None),
    )
    return snap, task_input, add_btn


def _run_on_origin(
    origin: str,
    *,
    screenshot_path: Path | None,
    timeout_s: float,
    actions: Callable[[SafeBrowser], ObservedState],
) -> SideObservation:
    started = time.monotonic()
    try:
        with SafeBrowser(origin) as browser:
            browser.goto(origin)
            if time.monotonic() - started > timeout_s:
                raise TimeoutError(f'origin setup exceeded {timeout_s}s')
            state = actions(browser)
            shot = None
            if screenshot_path is not None:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                browser.screenshot(str(screenshot_path))
                shot = str(screenshot_path)
            return SideObservation(origin=origin, observed_state=state, screenshot=shot)
    except Exception as exc:
        return SideObservation(
            origin=origin,
            observed_state=ObservedState(visible_text_excerpt=''),
            screenshot=None,
            error=str(exc)[:400],
        )


def _submit_empty(browser: SafeBrowser) -> ObservedState:
    snap, task_input, add_btn = _find_controls(browser)
    if not task_input or not add_btn:
        raise RuntimeError('missing input or add control')
    browser.act(Decision(action='fill', element_id=task_input.element_id, value='', reason='empty submit'))
    _, _, add_btn2 = _find_controls(browser)
    if not add_btn2:
        raise RuntimeError('missing add control after fill')
    after = browser.act(Decision(action='click', element_id=add_btn2.element_id, reason='empty submit click'))
    return build_observed_state(after.visible_text if after else '', expected_tasks=[])


def _create_task(browser: SafeBrowser, name: str) -> ObservedState:
    _, task_input, add_btn = _find_controls(browser)
    if not task_input or not add_btn:
        raise RuntimeError('missing input or add control')
    browser.act(Decision(action='fill', element_id=task_input.element_id, value=name, reason='create task'))
    _, _, add_btn2 = _find_controls(browser)
    if not add_btn2:
        raise RuntimeError('missing add control after fill')
    after = browser.act(Decision(action='click', element_id=add_btn2.element_id, reason='submit task'))
    return build_observed_state(after.visible_text if after else '', expected_tasks=[name])


def _create_and_persist(browser: SafeBrowser, name: str) -> ObservedState:
    created = _create_task(browser, name)
    if not created.task_visible:
        return created
    after = browser.act(Decision(action='reload', reason='persistence check'))
    return build_observed_state(after.visible_text if after else '', expected_tasks=[name])


def _create_two(browser: SafeBrowser, a: str, b: str) -> ObservedState:
    _create_task(browser, a)
    after = _create_task(browser, b)
    # Re-read full state for both names.
    snap = browser.snapshot()
    return build_observed_state(snap.visible_text, expected_tasks=[a, b])


def _whitespace_submit(browser: SafeBrowser, whitespace: str) -> ObservedState:
    _, task_input, add_btn = _find_controls(browser)
    if not task_input or not add_btn:
        raise RuntimeError('missing input or add control')
    browser.act(Decision(action='fill', element_id=task_input.element_id, value=whitespace, reason='whitespace'))
    _, _, add_btn2 = _find_controls(browser)
    if not add_btn2:
        raise RuntimeError('missing add control after fill')
    after = browser.act(Decision(action='click', element_id=add_btn2.element_id, reason='whitespace submit'))
    # Do not assume validation vs create — only record observables.
    return build_observed_state(after.visible_text if after else '', expected_tasks=[])


def _finalize_pair(
    *,
    test_id: str,
    description: str,
    input_values: dict[str, str | None],
    original: SideObservation,
    reconstruction: SideObservation,
    diffs: list[str],
    evidence_refs: list[str],
) -> BehavioralCaseResult:
    if original.error:
        return BehavioralCaseResult(
            test_id=test_id,
            description=description,
            input_values=input_values,
            original=original,
            reconstruction=reconstruction,
            status='invalid',
            differences=diffs,
            evidence_refs=evidence_refs,
            error=f'oracle failed: {original.error}',
        )
    if reconstruction.error:
        return BehavioralCaseResult(
            test_id=test_id,
            description=description,
            input_values=input_values,
            original=original,
            reconstruction=reconstruction,
            status='fail',
            differences=diffs + [f'reconstruction error: {reconstruction.error}'],
            evidence_refs=evidence_refs,
            error=reconstruction.error,
        )
    status: ResultStatus = 'pass' if not diffs else 'fail'
    return BehavioralCaseResult(
        test_id=test_id,
        description=description,
        input_values=input_values,
        original=original,
        reconstruction=reconstruction,
        status=status,
        differences=diffs,
        evidence_refs=evidence_refs,
    )


def _find_calc_controls(browser: SafeBrowser):
    snap = browser.snapshot()
    inputs = [e for e in snap.elements if e.kind in ('input', 'textarea')]
    buttons = {e.label.lower(): e for e in snap.elements if e.kind == 'button'}
    add = buttons.get('add') or next((e for e in snap.elements if e.kind == 'button' and 'add' in e.label.lower()), None)
    sub = buttons.get('subtract') or next(
        (e for e in snap.elements if e.kind == 'button' and 'sub' in e.label.lower()), None
    )
    reset = buttons.get('reset') or next(
        (e for e in snap.elements if e.kind == 'button' and 'reset' in e.label.lower()), None
    )
    return snap, inputs, add, sub, reset


def _calc_fill_operands(browser: SafeBrowser, a: str, b: str) -> None:
    _, inputs, _, _, _ = _find_calc_controls(browser)
    if len(inputs) < 2:
        raise RuntimeError('calculator missing two inputs')
    browser.act(Decision(action='fill', element_id=inputs[0].element_id, value=a, reason='fill A'))
    _, inputs2, _, _, _ = _find_calc_controls(browser)
    if len(inputs2) < 2:
        raise RuntimeError('calculator missing two inputs after first fill')
    browser.act(Decision(action='fill', element_id=inputs2[1].element_id, value=b, reason='fill B'))


def _calc_empty_op(browser: SafeBrowser) -> ObservedState:
    _, _, add, _, _ = _find_calc_controls(browser)
    if not add:
        raise RuntimeError('missing Add control')
    after = browser.act(Decision(action='click', element_id=add.element_id, reason='empty add'))
    return build_calculator_state(after.visible_text if after else '')


def _calc_operate(browser: SafeBrowser, a: str, b: str, op: str) -> ObservedState:
    _calc_fill_operands(browser, a, b)
    _, _, add, sub, _ = _find_calc_controls(browser)
    btn = add if op == 'add' else sub
    if not btn:
        raise RuntimeError(f'missing {op} control')
    after = browser.act(Decision(action='click', element_id=btn.element_id, reason=f'{op} holdout'))
    text = after.visible_text if after else ''
    return build_calculator_state(text, expect_tokens=[a, b])


def _calc_reset(browser: SafeBrowser, a: str, b: str) -> ObservedState:
    created = _calc_operate(browser, a, b, 'add')
    if not created.result_text:
        return created
    _, _, _, _, reset = _find_calc_controls(browser)
    if not reset:
        raise RuntimeError('missing Reset control')
    after = browser.act(Decision(action='click', element_id=reset.element_id, reason='reset'))
    return build_calculator_state(after.visible_text if after else '')


def _make_timed_pair(targets: _Targets, shots: Path, notes: list[str]):
    def timed_pair(test_id: str, description: str, inputs: dict, evidence: list[str],
                   orig_fn, recon_fn, compare_kwargs: dict) -> BehavioralCaseResult:
        started = time.monotonic()
        try:
            original = _run_on_origin(
                targets.original,
                screenshot_path=shots / f'{test_id}__original.png',
                timeout_s=TEST_TIMEOUT_SECONDS,
                actions=orig_fn,
            )
            reconstruction = _run_on_origin(
                targets.reconstruction,
                screenshot_path=shots / f'{test_id}__reconstruction.png',
                timeout_s=TEST_TIMEOUT_SECONDS,
                actions=recon_fn,
            )
            if time.monotonic() - started > TEST_TIMEOUT_SECONDS * 2 + 5:
                notes.append(f'{test_id}: wall-clock budget pressure')
            diffs: list[str] = []
            if not original.error and not reconstruction.error:
                diffs = compare_observed_states(
                    original.observed_state,
                    reconstruction.observed_state,
                    **compare_kwargs,
                )
            return _finalize_pair(
                test_id=test_id,
                description=description,
                input_values=inputs,
                original=original,
                reconstruction=reconstruction,
                diffs=diffs,
                evidence_refs=evidence,
            )
        except Exception as exc:
            empty = SideObservation(
                origin=targets.original,
                observed_state=ObservedState(),
                error=str(exc)[:400],
            )
            return BehavioralCaseResult(
                test_id=test_id,
                description=description,
                input_values=inputs,
                original=empty,
                reconstruction=SideObservation(
                    origin=targets.reconstruction,
                    observed_state=ObservedState(),
                    error=str(exc)[:400],
                ),
                status='invalid',
                differences=[],
                evidence_refs=evidence,
                error=str(exc)[:400],
            )

    return timed_pair


def run_taskboard_validation(
    *,
    original_origin: str,
    reconstruction_origin: str,
    output_dir: Path,
    isolation: dict[str, Any] | None = None,
) -> ValidationReport:
    shots = output_dir / 'screenshots'
    shots.mkdir(parents=True, exist_ok=True)
    holdouts = make_holdout_values()
    targets = _Targets(original=original_origin, reconstruction=reconstruction_origin)
    results: list[BehavioralCaseResult] = []
    notes: list[str] = []
    timed_pair = _make_timed_pair(targets, shots, notes)

    results.append(timed_pair(
        'empty_input_validation',
        'Submit empty task name; compare validation visibility',
        {'task_name': ''},
        ['phase1b:empty_task_submission', 'REQ-EMPTY-SUBMIT'],
        _submit_empty,
        _submit_empty,
        {'compare_validation': True, 'compare_empty': True},
    ))

    task_a = holdouts['task_a']
    results.append(timed_pair(
        'valid_task_creation',
        'Create a fresh holdout task and compare visibility',
        {'task_name': task_a},
        ['phase1b:valid_task_submission', 'REQ-VALID-CREATE'],
        lambda b: _create_task(b, task_a),
        lambda b: _create_task(b, task_a),
        {'compare_tasks': True, 'compare_empty': True},
    ))

    results.append(timed_pair(
        'persistence_after_reload',
        'Create holdout task, reload, compare persistence',
        {'task_name': task_a},
        ['phase1b:reload_persistence', 'REQ-RELOAD-PERSIST'],
        lambda b: _create_and_persist(b, task_a),
        lambda b: _create_and_persist(b, task_a),
        {'compare_tasks': True},
    ))

    core_invalid = sum(1 for r in results if r.status == 'invalid')
    if core_invalid < 3:
        task_b = holdouts['task_b']
        results.append(timed_pair(
            'multiple_task_creation',
            'Create two distinct holdout tasks; compare both visible',
            {'task_a': task_a, 'task_b': task_b},
            ['phase3:extension'],
            lambda b: _create_two(b, task_a, task_b),
            lambda b: _create_two(b, task_a, task_b),
            {'compare_tasks': True},
        ))
        ws = holdouts['whitespace']
        results.append(timed_pair(
            'whitespace_input',
            'Submit whitespace-only name; compare observable outcomes without assumed oracle rule',
            {'task_name': ws},
            ['phase3:extension'],
            lambda b: _whitespace_submit(b, ws),
            lambda b: _whitespace_submit(b, ws),
            {'compare_validation': True, 'compare_empty': True, 'compare_tasks': False},
        ))

    total_valid, passed, failed, invalid, rate = calculate_match_rate(results)
    return ValidationReport(
        original_origin=original_origin,
        reconstruction_origin=reconstruction_origin,
        isolation=isolation or {},
        holdout_values={k: v for k, v in holdouts.items() if k != 'whitespace'} | {
            'whitespace': '[whitespace-only]'
        },
        tests=results,
        total_valid=total_valid,
        passed=passed,
        failed=failed,
        invalid=invalid,
        behavioral_match_rate_percent=rate,
        meta_api_requests=0,
        notes=notes,
    )


def run_calculator_validation(
    *,
    original_origin: str,
    reconstruction_origin: str,
    output_dir: Path,
    isolation: dict[str, Any] | None = None,
) -> ValidationReport:
    """Independent calculator oracle — original defines expected visible outcomes."""
    shots = output_dir / 'screenshots'
    shots.mkdir(parents=True, exist_ok=True)
    holdouts = make_calculator_holdouts()
    targets = _Targets(original=original_origin, reconstruction=reconstruction_origin)
    results: list[BehavioralCaseResult] = []
    notes: list[str] = []
    timed_pair = _make_timed_pair(targets, shots, notes)

    results.append(timed_pair(
        'calc_empty_input',
        'Operate with empty inputs; compare validation visibility',
        {'num_a': '', 'num_b': ''},
        ['calc:empty_input_handling', 'REQ-CALC-EMPTY'],
        _calc_empty_op,
        _calc_empty_op,
        {'compare_validation': True},
    ))

    aa, ab = holdouts['add_a'], holdouts['add_b']
    results.append(timed_pair(
        'calc_addition',
        'Add fresh holdout numbers; compare visible result',
        {'num_a': aa, 'num_b': ab},
        ['calc:addition_operation', 'REQ-CALC-ADD'],
        lambda b: _calc_operate(b, aa, ab, 'add'),
        lambda b: _calc_operate(b, aa, ab, 'add'),
        {'compare_result': True, 'compare_validation': True},
    ))

    sa, sb = holdouts['sub_a'], holdouts['sub_b']
    results.append(timed_pair(
        'calc_subtraction',
        'Subtract fresh holdout numbers; compare visible result',
        {'num_a': sa, 'num_b': sb},
        ['calc:subtraction_operation', 'REQ-CALC-SUB'],
        lambda b: _calc_operate(b, sa, sb, 'sub'),
        lambda b: _calc_operate(b, sa, sb, 'sub'),
        {'compare_result': True, 'compare_validation': True},
    ))

    na, nb = holdouts['neg_a'], holdouts['neg_b']
    results.append(timed_pair(
        'calc_negative',
        'Operate with a negative holdout operand; compare visible result',
        {'num_a': na, 'num_b': nb},
        ['calc:negative_number_handling', 'REQ-CALC-NEG'],
        lambda b: _calc_operate(b, na, nb, 'add'),
        lambda b: _calc_operate(b, na, nb, 'add'),
        {'compare_result': True, 'compare_validation': True},
    ))

    results.append(timed_pair(
        'calc_reset',
        'Compute then reset; compare cleared visible outcome',
        {'num_a': aa, 'num_b': ab},
        ['calc:reset_behavior', 'REQ-CALC-RESET'],
        lambda b: _calc_reset(b, aa, ab),
        lambda b: _calc_reset(b, aa, ab),
        {'compare_result': True, 'compare_validation': True},
    ))

    total_valid, passed, failed, invalid, rate = calculate_match_rate(results)
    return ValidationReport(
        original_origin=original_origin,
        reconstruction_origin=reconstruction_origin,
        isolation=isolation or {},
        holdout_values=dict(holdouts),
        tests=results,
        total_valid=total_valid,
        passed=passed,
        failed=failed,
        invalid=invalid,
        behavioral_match_rate_percent=rate,
        meta_api_requests=0,
        notes=notes + ['suite=calculator; holdouts chosen after reconstruction'],
    )


def run_validation(
    *,
    original_origin: str = DEFAULT_ORIGINAL,
    reconstruction_origin: str = DEFAULT_RECONSTRUCTION,
    reconstructed_dir: Path,
    output_dir: Path,
    isolation: dict[str, Any] | None = None,
    suite: Literal['taskboard', 'calculator'] = 'taskboard',
) -> ValidationReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    if suite == 'calculator':
        report = run_calculator_validation(
            original_origin=original_origin,
            reconstruction_origin=reconstruction_origin,
            output_dir=output_dir,
            isolation=isolation,
        )
    else:
        report = run_taskboard_validation(
            original_origin=original_origin,
            reconstruction_origin=reconstruction_origin,
            output_dir=output_dir,
            isolation=isolation,
        )
    (output_dir / 'validation_results.json').write_text(
        json.dumps(report.model_dump(mode='json'), indent=2),
        encoding='utf-8',
    )
    return report


def run_phase3_validation(
    *,
    reconstructed_dir: Path,
    output_dir: Path,
    original_origin: str = DEFAULT_ORIGINAL,
    suite: Literal['taskboard', 'calculator'] = 'taskboard',
) -> ValidationReport:
    """Start isolated preview if possible, run oracle comparisons, always write a report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    preview = prepare_preview(reconstructed_dir)
    write_preview_status(output_dir, preview)

    if preview.get('status') != 'running':
        # Do not fall back to host http.server. Emit blocked report.
        blocked = ValidationReport(
            original_origin=original_origin,
            reconstruction_origin=DEFAULT_RECONSTRUCTION,
            isolation=preview,
            holdout_values={},
            tests=[],
            total_valid=0,
            passed=0,
            failed=0,
            invalid=0,
            behavioral_match_rate_percent=None,
            meta_api_requests=0,
            notes=[
                'Executable behavioral validation blocked: isolated reconstruction preview unavailable.',
                preview.get('reason') or 'preview blocked',
            ],
        )
        (output_dir / 'validation_results.json').write_text(
            json.dumps(blocked.model_dump(mode='json'), indent=2),
            encoding='utf-8',
        )
        return blocked

    try:
        return run_validation(
            original_origin=original_origin,
            reconstruction_origin=preview.get('url') or DEFAULT_RECONSTRUCTION,
            reconstructed_dir=reconstructed_dir,
            output_dir=output_dir,
            isolation=preview,
            suite=suite,
        )
    finally:
        # Always attempt container cleanup after validation.
        try:
            stop_preview()
        except Exception:
            pass
