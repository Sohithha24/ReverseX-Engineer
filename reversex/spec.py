"""Build a behavioral specification from investigation observations only.

Never reads original fixture source. Never invents unobserved behavior as fact.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from reversex.targets import get_target


class EvidenceKind(str, Enum):
    OBSERVATION = 'observation'
    HYPOTHESIS = 'hypothesis'


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra='forbid')

    report_path: str
    step: int | None = None
    objective_key: str | None = None
    note: str = Field(min_length=1, max_length=400)


class BehaviorRequirement(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str = Field(min_length=1, max_length=80)
    kind: EvidenceKind
    feature: str = Field(min_length=1, max_length=120)
    preconditions: list[str] = Field(min_length=1)
    action_performed: str = Field(min_length=1, max_length=200)
    input_values: dict[str, str | None] = Field(default_factory=dict)
    observed_result: str = Field(min_length=1, max_length=800)
    evidence: list[EvidenceRef] = Field(min_length=1)
    uncertainties: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def observations_need_step_evidence(self):
        if self.kind == EvidenceKind.OBSERVATION:
            if not any(ref.step is not None for ref in self.evidence):
                raise ValueError(f'observation requirement {self.id} needs a step evidence reference')
        return self


class BehaviorSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')

    project: str = 'ReverseX Engineer'
    phase: Literal['2'] = '2'
    source_report: str
    source_report_sha256: str = Field(min_length=64, max_length=64)
    feature: str = Field(min_length=1, max_length=200)
    status: Literal['draft', 'frozen'] = 'draft'
    requirements: list[BehaviorRequirement] = Field(min_length=1)
    global_uncertainties: list[str] = Field(default_factory=list)
    excluded_from_model_context: list[str] = Field(default_factory=list)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _visible(event: dict, which: str) -> str:
    snap = event.get(which) or {}
    return snap.get('visible_text') or ''


def _ok_events(report: dict) -> list[dict]:
    return [e for e in report.get('events') or [] if e.get('status') == 'ok' and e.get('decision')]


def _find_supporting_step(events: list[dict], objective_key: str, objectives: dict) -> int | None:
    evidence = (objectives.get(objective_key) or {}).get('evidence') or ''
    # evidence strings look like: "step N: ..."
    if evidence.startswith('step '):
        try:
            return int(evidence.split(':', 1)[0].replace('step', '').strip())
        except ValueError:
            pass
    for event in events:
        if event.get('step') is None:
            continue
        # Fallback: first click after fills matching objective heuristics already marked supported.
        return event.get('step')
    return None


def build_taskboard_spec(report: dict, *, source_report: str, report_bytes: bytes) -> BehaviorSpec:
    """Derive TaskBoard requirements only from recorded events and objective flags."""
    events = _ok_events(report)
    by_step = {e.get('step'): e for e in events if e.get('step') is not None}
    objectives = report.get('objectives') or {}
    requirements: list[BehaviorRequirement] = []
    target = get_target('taskboard')

    empty_obj = objectives.get('empty_task_submission') or {}
    step1 = by_step.get(1)
    if empty_obj.get('supported') and step1:
        after = _visible(step1, 'after')
        before = _visible(step1, 'before')
        decision = step1.get('decision') or {}
        requirements.append(BehaviorRequirement(
            id='REQ-EMPTY-SUBMIT',
            kind=EvidenceKind.OBSERVATION,
            feature='add_task',
            preconditions=[
                'Page shows a task name input and an Add task control.',
                'Task list shows empty-state text (observed: "No tasks yet.").',
                'No non-empty task name was filled in this attempt before the submit click.',
            ],
            action_performed=f"{decision.get('action')} on element {decision.get('element_id')}",
            input_values={'task_name': None},
            observed_result=(
                'After the action, visible text included validation message '
                '"Task name is required." and the empty-state remained.'
                if 'Task name is required.' in after
                else f'After the action, visible text changed. Snippet: {after[:240]}'
            ),
            evidence=[
                EvidenceRef(
                    report_path=source_report,
                    step=1,
                    objective_key='empty_task_submission',
                    note=empty_obj.get('evidence') or 'empty submission observation',
                ),
            ],
            uncertainties=[
                'Exact input widget type beyond snapshot kind=input is not asserted.',
                'Whether whitespace-only names are rejected was not separately tested.',
            ],
        ))
        if 'No tasks yet.' not in before:
            requirements[-1].uncertainties.append('Initial empty-state phrasing differed from common fixture text.')

    valid_obj = objectives.get('valid_task_submission') or {}
    step2 = by_step.get(2)
    step3 = by_step.get(3)
    task_name = valid_obj.get('task_name')
    if valid_obj.get('supported') and step2 and step3 and task_name:
        fill = step2.get('decision') or {}
        click = step3.get('decision') or {}
        after3 = _visible(step3, 'after')
        requirements.append(BehaviorRequirement(
            id='REQ-VALID-CREATE',
            kind=EvidenceKind.OBSERVATION,
            feature='add_task',
            preconditions=[
                'A non-empty task name can be entered into the visible text input.',
                f'Task name used in investigation: "{task_name}".',
            ],
            action_performed=(
                f"{fill.get('action')} value then {click.get('action')} on "
                f"{click.get('element_id')}"
            ),
            input_values={'task_name': task_name},
            observed_result=(
                f'After submit, visible text included the task name "{task_name}" under the task list '
                f'and no longer showed "No tasks yet."'
                if task_name in after3 and 'No tasks yet.' not in after3
                else f'After submit, visible text: {after3[:240]}'
            ),
            evidence=[
                EvidenceRef(
                    report_path=source_report,
                    step=2,
                    objective_key='valid_task_submission',
                    note='fill with non-empty task name',
                ),
                EvidenceRef(
                    report_path=source_report,
                    step=3,
                    objective_key='valid_task_submission',
                    note=valid_obj.get('evidence') or 'valid submit observation',
                ),
            ],
            uncertainties=[
                'Maximum task name length was not observed in this investigation.',
                'Duplicate-task behavior was not observed.',
            ],
        ))

    persist_obj = objectives.get('reload_persistence') or {}
    step4 = by_step.get(4)
    persist_name = persist_obj.get('task_name') or task_name
    if persist_obj.get('supported') and step4 and persist_name:
        after4 = _visible(step4, 'after')
        decision = step4.get('decision') or {}
        requirements.append(BehaviorRequirement(
            id='REQ-RELOAD-PERSIST',
            kind=EvidenceKind.OBSERVATION,
            feature='add_task',
            preconditions=[
                f'A task named "{persist_name}" was visible in the list before reload.',
            ],
            action_performed=str(decision.get('action') or 'reload'),
            input_values={},
            observed_result=(
                f'After reload, visible text still included "{persist_name}".'
                if persist_name in after4
                else f'After reload, visible text: {after4[:240]}'
            ),
            evidence=[
                EvidenceRef(
                    report_path=source_report,
                    step=4,
                    objective_key='reload_persistence',
                    note=persist_obj.get('evidence') or 'reload persistence observation',
                ),
            ],
            uncertainties=[
                'Persistence mechanism (e.g. memory, localStorage, cookie, server) was NOT observed.',
                'Cross-tab or cross-browser persistence was not tested.',
            ],
        ))

    requirements.append(BehaviorRequirement(
        id='HYP-STORAGE-UNKNOWN',
        kind=EvidenceKind.HYPOTHESIS,
        feature='add_task',
        preconditions=['A task survives page reload in the same browser context.'],
        action_performed='(none — interpretive note)',
        input_values={},
        observed_result=(
            'Hypothesis only: some client- or server-side retention exists. '
            'No storage API, network write, or file write was observed in Phase 1B.'
        ),
        evidence=[
            EvidenceRef(
                report_path=source_report,
                step=4,
                objective_key='reload_persistence',
                note='persistence observed; mechanism unknown',
            ),
        ],
        uncertainties=[
            'Do not treat any specific storage technology as a requirement.',
        ],
    ))

    if not any(r.kind == EvidenceKind.OBSERVATION for r in requirements):
        raise ValueError('No observation-backed requirements could be derived from the report')

    return BehaviorSpec(
        source_report=source_report,
        source_report_sha256=_sha256_bytes(report_bytes),
        feature=target.feature_label,
        status='draft',
        requirements=requirements,
        global_uncertainties=[
            'UI chrome, styling, and exact labels beyond observed visible_text are not required.',
            'Only behaviors evidenced in the investigation report are observation requirements.',
            'Original application source must not be used as reconstruction input.',
        ],
        excluded_from_model_context=list(target.excluded_from_model_context),
    )


def build_calculator_spec(report: dict, *, source_report: str, report_bytes: bytes) -> BehaviorSpec:
    """Derive calculator requirements from supported objectives + actual event snippets."""
    events = _ok_events(report)
    by_step = {e.get('step'): e for e in events if e.get('step') is not None}
    objectives = report.get('objectives') or {}
    requirements: list[BehaviorRequirement] = []
    target = get_target('calculator')

    def add_obs(req_id: str, objective_key: str, feature: str, preconditions: list[str],
                input_values: dict, action_performed: str, observed_result: str, uncertainties: list[str]):
        obj = objectives.get(objective_key) or {}
        if not obj.get('supported'):
            return
        step = None
        evidence = obj.get('evidence') or ''
        if evidence.startswith('step '):
            try:
                step = int(evidence.split(':', 1)[0].replace('step', '').strip())
            except ValueError:
                step = None
        event = by_step.get(step) if step is not None else None
        if event is None:
            # Find any ok click event as weak fallback only if objective marked supported.
            for e in events:
                if (e.get('decision') or {}).get('action') == 'click':
                    event = e
                    step = e.get('step')
                    break
        if event is None or step is None:
            return
        decision = event.get('decision') or {}
        after = _visible(event, 'after')
        requirements.append(BehaviorRequirement(
            id=req_id,
            kind=EvidenceKind.OBSERVATION,
            feature=feature,
            preconditions=preconditions,
            action_performed=action_performed or f"{decision.get('action')} on {decision.get('element_id')}",
            input_values=input_values,
            observed_result=observed_result if observed_result else f'Visible text after action: {after[:240]}',
            evidence=[
                EvidenceRef(
                    report_path=source_report,
                    step=int(step),
                    objective_key=objective_key,
                    note=obj.get('evidence') or objective_key,
                ),
            ],
            uncertainties=uncertainties,
        ))

    empty = objectives.get('empty_input_handling') or {}
    if empty.get('supported'):
        add_obs(
            'REQ-CALC-EMPTY',
            'empty_input_handling',
            'calculator_empty_input',
            [
                'Calculator shows two numeric inputs and operation controls.',
                'An operation was attempted without both numbers filled.',
            ],
            {'num_a': None, 'num_b': None},
            'click an operation control with empty/incomplete inputs',
            'Page showed a required/empty-input style message (exact wording as observed in the investigation event).',
            ['Exact wording may vary; presence of an empty-input response is the requirement.'],
        )

    add_obj = objectives.get('addition_operation') or {}
    if add_obj.get('supported'):
        ops = add_obj.get('operands') or []
        add_obs(
            'REQ-CALC-ADD',
            'addition_operation',
            'calculator_addition',
            [
                'Two numeric values can be entered into the visible inputs.',
                'An Add control is available.',
            ],
            {'num_a': ops[0] if len(ops) > 0 else None, 'num_b': ops[1] if len(ops) > 1 else None},
            'fill two numbers then click Add',
            (
                f'After Add, the page displayed a visible numeric result for operands {ops}.'
                if ops else 'After Add, the page displayed a visible numeric result.'
            ),
            [
                'Holdout operands used later in validation are not part of this investigation evidence.',
                'Formatting of the result (spacing, labels) is not strictly required beyond a correct visible outcome.',
            ],
        )

    sub_obj = objectives.get('subtraction_operation') or {}
    if sub_obj.get('supported'):
        ops = sub_obj.get('operands') or []
        add_obs(
            'REQ-CALC-SUB',
            'subtraction_operation',
            'calculator_subtraction',
            [
                'Two numeric values can be entered into the visible inputs.',
                'A Subtract control is available.',
            ],
            {'num_a': ops[0] if len(ops) > 0 else None, 'num_b': ops[1] if len(ops) > 1 else None},
            'fill two numbers then click Subtract',
            (
                f'After Subtract, the page displayed a visible numeric result for operands {ops}.'
                if ops else 'After Subtract, the page displayed a visible numeric result.'
            ),
            ['Cross-checks with holdout values happen only in independent validation.'],
        )

    reset_obj = objectives.get('reset_behavior') or {}
    if reset_obj.get('supported'):
        add_obs(
            'REQ-CALC-RESET',
            'reset_behavior',
            'calculator_reset',
            ['Calculator had prior visible state (inputs and/or result).'],
            {},
            'click Reset',
            'After Reset, prior result/state was cleared or altered as observed.',
            ['Whether inputs are also cleared vs only the result is taken from observations.'],
        )

    neg_obj = objectives.get('negative_number_handling') or {}
    if neg_obj.get('supported'):
        ops = neg_obj.get('operands') or []
        add_obs(
            'REQ-CALC-NEG',
            'negative_number_handling',
            'calculator_negative',
            ['At least one operand was a negative number during an observed operation.'],
            {'num_a': ops[0] if len(ops) > 0 else None, 'num_b': ops[1] if len(ops) > 1 else None},
            'operate with a negative operand',
            'Page still produced a visible numeric result after the operation.',
            ['Only the observed negative case is required; other sign combinations are uncertain.'],
        )

    # Hypothesis: arithmetic meaning (do not elevate to observation without proof language).
    if any(r.kind == EvidenceKind.OBSERVATION for r in requirements):
        step_for_hyp = next((r.evidence[0].step for r in requirements if r.evidence), 1)
        requirements.append(BehaviorRequirement(
            id='HYP-CALC-ARITHMETIC',
            kind=EvidenceKind.HYPOTHESIS,
            feature='calculator',
            preconditions=['Numeric results appeared after Add/Subtract clicks.'],
            action_performed='(none — interpretive note)',
            input_values={},
            observed_result=(
                'Hypothesis only: Add/Subtract correspond to ordinary arithmetic. '
                'Independent validation must confirm with holdout inputs against the original oracle.'
            ),
            evidence=[
                EvidenceRef(
                    report_path=source_report,
                    step=int(step_for_hyp or 1),
                    objective_key='addition_operation',
                    note='arithmetic semantics hypothesized from visible results',
                ),
            ],
            uncertainties=['Do not treat hypothesized formulas as proven without oracle comparison.'],
        ))

    if not any(r.kind == EvidenceKind.OBSERVATION for r in requirements):
        raise ValueError('No observation-backed calculator requirements could be derived from the report')

    return BehaviorSpec(
        source_report=source_report,
        source_report_sha256=_sha256_bytes(report_bytes),
        feature=target.feature_label,
        status='draft',
        requirements=requirements,
        global_uncertainties=[
            'UI chrome and exact copy beyond observed visible_text are not required.',
            'Only behaviors evidenced in the investigation report are observation requirements.',
            'Original calculator source must not be used as reconstruction input.',
            'Validation holdout numbers are chosen later and must not be supplied to the model here.',
        ],
        excluded_from_model_context=list(target.excluded_from_model_context),
    )


def build_behavior_spec(report: dict, *, source_report: str, report_bytes: bytes) -> BehaviorSpec:
    """Derive requirements only from recorded events and objective flags."""
    target_id = report.get('target_id') or 'taskboard'
    if target_id == 'calculator':
        return build_calculator_spec(report, source_report=source_report, report_bytes=report_bytes)
    return build_taskboard_spec(report, source_report=source_report, report_bytes=report_bytes)


def assert_observations_have_evidence(spec: BehaviorSpec) -> None:
    for req in spec.requirements:
        if req.kind != EvidenceKind.OBSERVATION:
            continue
        if not req.evidence:
            raise ValueError(f'{req.id} missing evidence')
        if not any(e.step is not None for e in req.evidence):
            raise ValueError(f'{req.id} observation lacks step reference')


def load_investigation_report(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict):
        raise ValueError('investigation report must be a JSON object')
    return data, raw


def generate_and_freeze_spec(
    report_path: Path,
    *,
    output_dir: Path,
) -> BehaviorSpec:
    """Write behavior_spec.json and an immutable frozen copy with checksum."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report, report_bytes = load_investigation_report(report_path)
    rel = str(report_path).replace('\\', '/')
    spec = build_behavior_spec(report, source_report=rel, report_bytes=report_bytes)
    assert_observations_have_evidence(spec)

    draft_path = output_dir / 'behavior_spec.json'
    draft_path.write_text(json.dumps(spec.model_dump(mode='json'), indent=2), encoding='utf-8')

    frozen = spec.model_copy(update={'status': 'frozen'})
    frozen_bytes = json.dumps(frozen.model_dump(mode='json'), indent=2, sort_keys=True).encode('utf-8')
    digest = _sha256_bytes(frozen_bytes)
    frozen_dir = output_dir / 'frozen'
    frozen_dir.mkdir(parents=True, exist_ok=True)
    frozen_path = frozen_dir / f'behavior_spec.{digest[:16]}.json'
    frozen_path.write_bytes(frozen_bytes)
    (output_dir / 'behavior_spec.frozen.json').write_bytes(frozen_bytes)
    (output_dir / 'behavior_spec.sha256').write_text(digest + '\n', encoding='utf-8')
    draft_path.write_bytes(frozen_bytes)
    return BehaviorSpec.model_validate_json(frozen_bytes)


def load_frozen_spec(path: Path, *, expected_sha256: str | None = None) -> BehaviorSpec:
    raw = path.read_bytes()
    digest = _sha256_bytes(raw)
    if expected_sha256 and digest != expected_sha256.strip():
        raise ValueError('frozen behavior spec checksum mismatch — refusing to proceed')
    spec = BehaviorSpec.model_validate_json(raw)
    if spec.status != 'frozen':
        raise ValueError('expected a frozen behavior specification')
    assert_observations_have_evidence(spec)
    return spec
