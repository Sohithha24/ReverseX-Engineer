"""Run real browser exploration; --mode muse calls Meta, --mode scripted does not."""
import argparse
import json
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from reversex.browser import SafeBrowser
from reversex.contracts import Action, Decision
from reversex.targets import AppTarget, get_target

DEFAULT_ORIGIN = 'http://127.0.0.1:8001'

# Default TaskBoard keys (kept for existing unit tests).
OBJECTIVE_KEYS = (
    'empty_task_submission',
    'valid_task_submission',
    'reload_persistence',
)

_VALIDATION_RE = re.compile(r'task name is required', re.IGNORECASE)
_EMPTY_HINT_RE = re.compile(r'no tasks yet', re.IGNORECASE)
_CALC_EMPTY_RE = re.compile(r'(both numbers are required|required|enter|empty|missing|invalid)', re.I)
_NUMERIC_RE = re.compile(r'^-?\d+(?:\.\d+)?$')


def scripted_decision(snapshot, step: int):
    """Deterministic TaskBoard smoke test only. NOT an autonomous AI agent."""
    task = next((el.element_id for el in snapshot.elements if el.kind == 'input'), None)
    add = next((el.element_id for el in snapshot.elements if el.kind == 'button' and 'add task' in el.label.lower()), None)
    if step == 0 and task:
        return Decision(action='fill', element_id=task, value='', reason='Offline scripted empty input test')
    if step == 1 and add:
        return Decision(action='click', element_id=add, reason='Offline scripted empty submission')
    if step == 2 and task:
        return Decision(action='fill', element_id=task, value='Review PR', reason='Offline scripted valid input')
    if step == 3 and add:
        return Decision(action='click', element_id=add, reason='Offline scripted valid submission')
    if step == 4:
        return Decision(action='reload', reason='Offline scripted persistence check')
    return Decision(action='stop', reason='Offline scripted tests finished')


def scripted_calculator_decision(snapshot, step: int):
    """Deterministic calculator smoke test only. NOT an autonomous AI agent."""
    inputs = [el for el in snapshot.elements if el.kind == 'input']
    buttons = {el.label.lower(): el.element_id for el in snapshot.elements if el.kind == 'button'}
    add = buttons.get('add')
    sub = buttons.get('subtract')
    reset = buttons.get('reset')
    if step == 0 and add:
        return Decision(action='click', element_id=add, reason='Offline scripted empty add')
    if step == 1 and len(inputs) >= 2:
        return Decision(action='fill', element_id=inputs[0].element_id, value='4', reason='Offline fill A')
    if step == 2 and len(inputs) >= 2:
        return Decision(action='fill', element_id=inputs[1].element_id, value='2', reason='Offline fill B')
    if step == 3 and add:
        return Decision(action='click', element_id=add, reason='Offline add')
    if step == 4 and len(inputs) >= 2:
        return Decision(action='fill', element_id=inputs[0].element_id, value='9', reason='Offline fill A sub')
    if step == 5 and len(inputs) >= 2:
        return Decision(action='fill', element_id=inputs[1].element_id, value='3', reason='Offline fill B sub')
    if step == 6 and sub:
        return Decision(action='click', element_id=sub, reason='Offline subtract')
    if step == 7 and reset:
        return Decision(action='click', element_id=reset, reason='Offline reset')
    return Decision(action='stop', reason='Offline calculator scripted finished')


def _visible(event: dict, which: str) -> str:
    snap = event.get(which) or {}
    return snap.get('visible_text') or ''


def _filled_values_before_submit(events: list[dict], upto: int) -> list[str]:
    """Non-empty fill values since the previous click/reload/stop (same form attempt)."""
    values: list[str] = []
    for prior in events[:upto]:
        if prior.get('status') != 'ok':
            continue
        decision = prior.get('decision') or {}
        action = decision.get('action')
        if action in ('click', 'reload', 'stop'):
            values.clear()
        elif action == 'fill':
            values.append(decision.get('value') if decision.get('value') is not None else '')
    return values


def _button_label_for_click(event: dict) -> str:
    decision = event.get('decision') or {}
    eid = decision.get('element_id')
    before = event.get('before') or {}
    for el in before.get('elements') or []:
        if el.get('element_id') == eid:
            return str(el.get('label') or '').lower()
    return ''


def evaluate_taskboard_objectives(events: list[dict]) -> dict:
    """Derive TaskBoard investigation goals from recorded browser observations."""
    objectives = {
        'empty_task_submission': {
            'supported': False,
            'evidence': None,
        },
        'valid_task_submission': {
            'supported': False,
            'evidence': None,
            'task_name': None,
        },
        'reload_persistence': {
            'supported': False,
            'evidence': None,
            'task_name': None,
        },
    }
    created_task: str | None = None

    for idx, event in enumerate(events):
        if event.get('status') != 'ok':
            continue
        decision = event.get('decision') or {}
        action = decision.get('action')
        after = _visible(event, 'after')
        if not after:
            continue

        if action == 'click':
            fills = _filled_values_before_submit(events, idx)
            last_fill = fills[-1] if fills else None
            if (last_fill is None or last_fill.strip() == '') and _VALIDATION_RE.search(after):
                objectives['empty_task_submission'] = {
                    'supported': True,
                    'evidence': f'step {event.get("step")}: after click, page showed validation text',
                }
            if last_fill and last_fill.strip():
                name = last_fill.strip()
                if name in after and not _EMPTY_HINT_RE.search(after):
                    created_task = name
                    objectives['valid_task_submission'] = {
                        'supported': True,
                        'evidence': f'step {event.get("step")}: after click, task text was visible',
                        'task_name': name,
                    }

        if action == 'reload' and created_task and created_task in after:
            objectives['reload_persistence'] = {
                'supported': True,
                'evidence': f'step {event.get("step")}: after reload, task text remained visible',
                'task_name': created_task,
            }

    return objectives


def evaluate_calculator_objectives(events: list[dict]) -> dict:
    """Observation-backed calculator goals — does not assume arithmetic answers."""
    objectives = {
        'empty_input_handling': {'supported': False, 'evidence': None},
        'addition_operation': {'supported': False, 'evidence': None, 'operands': None},
        'subtraction_operation': {'supported': False, 'evidence': None, 'operands': None},
        'reset_behavior': {'supported': False, 'evidence': None},
        'negative_number_handling': {'supported': False, 'evidence': None, 'operands': None},
    }
    had_result_text = False
    last_numeric_operands: list[str] = []

    for idx, event in enumerate(events):
        if event.get('status') != 'ok':
            continue
        decision = event.get('decision') or {}
        action = decision.get('action')
        before = _visible(event, 'before')
        after = _visible(event, 'after')
        if action != 'click' or not after:
            continue

        label = _button_label_for_click(event)
        fills = [v.strip() for v in _filled_values_before_submit(events, idx)]
        numeric_fills = [v for v in fills if _NUMERIC_RE.match(v)]
        if len(numeric_fills) >= 2:
            last_numeric_operands = numeric_fills[-2:]
        # Operand values often remain in the UI after a prior operation click; allow
        # using the last observed numeric pair when the model clicks another op without re-filling.
        operands = numeric_fills[-2:] if len(numeric_fills) >= 2 else list(last_numeric_operands)
        emptyish = (not fills) and not last_numeric_operands

        if (emptyish or (fills and all(not v for v in fills))) and _CALC_EMPTY_RE.search(after):
            objectives['empty_input_handling'] = {
                'supported': True,
                'evidence': f'step {event.get("step")}: empty/incomplete inputs produced a required/empty message',
            }

        trailing_nums = re.findall(r'-?\d+(?:\.\d+)?', after)
        showed_result = bool(trailing_nums) and after != before and not _CALC_EMPTY_RE.search(after)

        if 'add' in label and len(operands) >= 2 and showed_result:
            objectives['addition_operation'] = {
                'supported': True,
                'evidence': f'step {event.get("step")}: Add click changed visible output after numeric fills',
                'operands': operands,
            }
            had_result_text = True
            if any(v.startswith('-') for v in operands):
                objectives['negative_number_handling'] = {
                    'supported': True,
                    'evidence': f'step {event.get("step")}: negative operand used with Add',
                    'operands': operands,
                }

        if 'subtract' in label and len(operands) >= 2 and showed_result:
            objectives['subtraction_operation'] = {
                'supported': True,
                'evidence': f'step {event.get("step")}: Subtract click changed visible output after numeric fills',
                'operands': operands,
            }
            had_result_text = True
            if any(v.startswith('-') for v in operands):
                objectives['negative_number_handling'] = {
                    'supported': True,
                    'evidence': f'step {event.get("step")}: negative operand used with Subtract',
                    'operands': operands,
                }

        if 'reset' in label:
            before_has_result = bool(re.search(r'-?\d+(?:\.\d+)?', before)) or had_result_text
            if before_has_result or 'result' in before.lower():
                prev_nums = set(re.findall(r'-?\d+(?:\.\d+)?', before))
                after_nums = set(re.findall(r'-?\d+(?:\.\d+)?', after))
                if not prev_nums.issubset(after_nums) or after != before:
                    objectives['reset_behavior'] = {
                        'supported': True,
                        'evidence': f'step {event.get("step")}: Reset click altered/cleared visible calculator state',
                    }
            last_numeric_operands = []

    return objectives


def evaluate_generic_feature_objectives(events: list[dict], feature: str | None = None) -> dict:
    """Observation-backed goals for allowlisted unfamiliar apps (no invented success)."""
    objectives = {
        'feature_controls_observed': {
            'supported': False,
            'evidence': None,
            'feature': feature,
        },
        'feature_interaction_attempted': {
            'supported': False,
            'evidence': None,
        },
        'page_response_observed': {
            'supported': False,
            'evidence': None,
        },
    }
    for event in events:
        if event.get('status') != 'ok':
            continue
        before = event.get('before') or {}
        after = event.get('after') or {}
        decision = event.get('decision') or {}
        action = decision.get('action')
        elements = before.get('elements') or []
        if elements:
            objectives['feature_controls_observed'] = {
                'supported': True,
                'evidence': f'step {event.get("step")}: visible interactive controls were present',
                'feature': feature,
            }
        if action in ('fill', 'click') and event.get('status') == 'ok':
            objectives['feature_interaction_attempted'] = {
                'supported': True,
                'evidence': f'step {event.get("step")}: performed {action} on a visible control',
            }
        before_text = (before.get('visible_text') or '')
        after_text = (after.get('visible_text') or '')
        control_changes = after.get('control_changes') or event.get('control_changes') or []
        if after_text and after_text != before_text:
            objectives['page_response_observed'] = {
                'supported': True,
                'evidence': f'step {event.get("step")}: page text changed after the action',
            }
        elif control_changes:
            objectives['page_response_observed'] = {
                'supported': True,
                'evidence': (
                    f'step {event.get("step")}: {len(control_changes)} control value/state '
                    f'change(s) recorded after the action'
                ),
            }
        else:
            # Fallback: compare structured element values when control_changes absent (older artifacts).
            def _vals(snap: dict) -> set[tuple[str, str, str]]:
                out: set[tuple[str, str, str]] = set()
                for el in snap.get('elements') or []:
                    if el.get('value_redacted'):
                        continue
                    out.add(
                        (
                            str(el.get('kind') or ''),
                            str(el.get('label') or ''),
                            str(el.get('value') if el.get('value') is not None else el.get('selected') or ''),
                        )
                    )
                return out

            if after.get('elements') and _vals(before) != _vals(after):
                objectives['page_response_observed'] = {
                    'supported': True,
                    'evidence': f'step {event.get("step")}: structured control values changed after the action',
                }
    return objectives


def evaluate_objectives(events: list[dict], target: AppTarget | None = None) -> dict:
    profile = target or get_target('taskboard')
    if profile.id == 'calculator':
        return evaluate_calculator_objectives(events)
    if profile.id == 'taskboard':
        return evaluate_taskboard_objectives(events)
    return evaluate_generic_feature_objectives(events, feature=profile.feature_label)


def scripted_generic_decision(snapshot, step: int, feature: str | None = None):
    """Deterministic exploration for allowlisted unfamiliar apps. NOT an autonomous AI agent."""
    inputs = [el for el in snapshot.elements if el.kind in ('input', 'textarea')]
    buttons = [el for el in snapshot.elements if el.kind == 'button']
    submit = next(
        (
            el.element_id
            for el in buttons
            if any(token in el.label.lower() for token in ('send', 'submit', 'save', 'create', 'add', 'ok'))
        ),
        buttons[0].element_id if buttons else None,
    )
    # Probe values — not application-specific oracles.
    probes = ['Alex Example', 'alex@example.com', 'Hello from ReverseX guided demo']
    if step == 0:
        return Decision(action='observe', reason=f'Observe page for feature: {feature or "selected feature"}')
    if step == 1 and inputs:
        return Decision(
            action='fill',
            element_id=inputs[0].element_id,
            value='',
            reason='Offline scripted empty first-field probe',
        )
    if step == 2 and submit:
        return Decision(action='click', element_id=submit, reason='Offline scripted submit with empty required fields')
    fill_index = step - 3
    if 0 <= fill_index < len(inputs):
        value = probes[fill_index] if fill_index < len(probes) else f'probe-{fill_index + 1}'
        return Decision(
            action='fill',
            element_id=inputs[fill_index].element_id,
            value=value,
            reason=f'Offline scripted fill field {fill_index + 1} for feature exploration',
        )
    if step == 3 + len(inputs) and submit:
        return Decision(action='click', element_id=submit, reason='Offline scripted submit after fills')
    if step == 4 + len(inputs):
        return Decision(action='reload', reason='Offline scripted reload persistence check')
    return Decision(action='stop', reason='Offline generic scripted exploration finished')


def finalize_status(
    *,
    events: list[dict],
    objectives: dict,
    stopped: bool,
    budget_hit: bool,
    errored: bool,
    objective_keys: tuple[str, ...] | None = None,
) -> str:
    """Map run outcome to a clear status.

    completed — model/script stopped AND all investigation objectives have evidence.
    incomplete — stopped, but required behavior was not fully observed.
    budget_exhausted — action or wall-clock budget reached before stop.
    error — execution / startup failure; observations may still be present.
    """
    if errored:
        return 'error'
    if budget_hit and not stopped:
        return 'budget_exhausted'
    keys = objective_keys or OBJECTIVE_KEYS
    all_supported = all((objectives.get(key) or {}).get('supported') for key in keys)
    if stopped and all_supported:
        return 'completed'
    if stopped:
        return 'incomplete'
    if budget_hit:
        return 'budget_exhausted'
    return 'incomplete'


def explore(
    mode: str,
    url: str | None = None,
    output_dir: str = 'artifacts',
    max_actions: int = 12,
    target_id: str | None = None,
    feature: str | None = None,
    target: AppTarget | None = None,
):
    load_dotenv()
    from reversex.browser import validate_target
    from reversex.targets import resolve_authorized_application

    if mode not in ('scripted', 'muse'):
        raise ValueError('mode must be scripted or muse')
    if max_actions < 1 or max_actions > 20:
        raise ValueError('max_actions must be between 1 and 20')

    if target is None:
        target, dest = resolve_authorized_application(
            application_url=url,
            target_id=target_id,
            feature=feature,
        )
    else:
        dest = url or (target.origin.rstrip('/') + '/')
    origin = target.origin.rstrip('/')
    # Optional env override only when investigating the default taskboard target without an explicit URL.
    if target.id == 'taskboard' and not url:
        env_origin = os.getenv('REVERSEX_ALLOWED_ORIGIN')
        if env_origin:
            from reversex.targets import normalize_origin

            origin = normalize_origin(env_origin)
            dest = origin + '/'
    validate_target(dest, origin)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    started = time.monotonic()
    stopped = False
    budget_hit = False
    errored = False
    api_requests = 0
    planner = None
    wall_budget = 180 if max_actions > 12 else 90
    try:
        if mode == 'muse':
            from reversex.meta import MusePlanner
            planner = MusePlanner(target=target)
        with SafeBrowser(origin) as browser:
            snapshot = browser.goto(dest)
            try:
                browser.screenshot(str(output / 'original.png'))
            except Exception as exc:
                history.append({'status': 'screenshot_error', 'phase': 'original', 'error': str(exc)[:240]})
            for step in range(max_actions):
                if time.monotonic() - started > wall_budget:
                    history.append({
                        'status': 'budget_exhausted',
                        'error': f'{wall_budget}-second wall-clock budget reached',
                    })
                    budget_hit = True
                    break
                try:
                    if planner:
                        decision = planner.decide(snapshot, history)
                    elif target.id == 'calculator':
                        decision = scripted_calculator_decision(snapshot, step)
                    elif target.id == 'taskboard':
                        decision = scripted_decision(snapshot, step)
                    else:
                        decision = scripted_generic_decision(snapshot, step, feature=target.feature_label)
                    if planner is not None:
                        api_requests = planner.request_count
                    record = {
                        'step': step + 1,
                        'decision': decision.model_dump(mode='json'),
                        'before': snapshot.model_dump(),
                    }
                    next_snapshot = browser.act(decision)
                    record['status'] = 'ok'
                    if next_snapshot is not None:
                        record['after'] = next_snapshot.model_dump()
                    history.append(record)
                    if decision.action == Action.STOP:
                        stopped = True
                        break
                    snapshot = next_snapshot
                except Exception as exc:
                    # Do not auto-retry state-changing browser actions after ambiguous failure.
                    # Previous successful history entries are preserved above.
                    errored = True
                    err_rec: dict = {
                        'step': step + 1,
                        'status': 'error',
                        'error': str(exc)[:240],
                    }
                    kind = getattr(exc, 'kind', None)
                    diag = getattr(exc, 'diagnostics', None)
                    if kind:
                        err_rec['error_kind'] = str(kind)[:80]
                    if isinstance(diag, dict) and diag:
                        # Already sanitized by MuseDecisionError path when present.
                        err_rec['error_diagnostics'] = {
                            k: diag[k] for k in list(diag)[:12] if k != 'Authorization'
                        }
                    history.append(err_rec)
                    break
            else:
                budget_hit = True
                history.append({'status': 'budget_exhausted', 'limit': max_actions})
            try:
                browser.screenshot(str(output / 'final.png'))
            except Exception as exc:
                history.append({'status': 'screenshot_error', 'phase': 'final', 'error': str(exc)[:240]})
            if planner is not None:
                api_requests = planner.request_count
    except Exception as exc:
        errored = True
        history.append({'status': 'startup_error', 'error': str(exc)[:240]})
        if planner is not None:
            api_requests = getattr(planner, 'request_count', api_requests)

    objectives = evaluate_objectives(history, target=target)
    final_status = finalize_status(
        events=history,
        objectives=objectives,
        stopped=stopped,
        budget_hit=budget_hit,
        errored=errored,
        objective_keys=target.objective_keys,
    )
    report = {
        'project': 'ReverseX Engineer',
        'mode': mode,
        'target_id': target.id,
        'feature': target.feature_label,
        'target_label': target.label or target.id,
        'validation_suite': target.validation_suite,
        'independent_validation_available': bool(
            target.supports_independent_validation and target.validation_suite
        ),
        'note': ('Offline scripted browser smoke test — not AI-led investigation' if mode == 'scripted'
                 else 'Live Muse Spark requested; review event logs to verify model behavior'),
        'target': dest,
        'status': final_status,
        'duration_seconds': round(time.monotonic() - started, 2),
        'max_actions': max_actions,
        'api_request_count': api_requests if mode == 'muse' else 0,
        'objectives': objectives,
        'events': history,
        'not_implemented': (
            []
            if target.supports_independent_validation
            else ['oracle-based independent validation for this custom application']
        ),
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description='ReverseX Engineer Phase 1b browser explorer')
    parser.add_argument('--mode', choices=['scripted', 'muse'], default='scripted')
    parser.add_argument('--url', default=None)
    parser.add_argument(
        '--target',
        default='taskboard',
        choices=['taskboard', 'calculator', 'contactpad', 'it-tools'],
    )
    parser.add_argument('--feature', default=None)
    parser.add_argument('--max-actions', type=int, default=12)
    parser.add_argument('--output-dir', default='artifacts')
    args = parser.parse_args()
    report = explore(
        args.mode,
        args.url,
        args.output_dir,
        args.max_actions,
        target_id=args.target,
        feature=args.feature,
    )
    summary = {k: v for k, v in report.items() if k != 'events'}
    print(json.dumps(summary, indent=2))
    print(f"Steps recorded: {len(report['events'])}. Full report: {args.output_dir}/report.json")
    if report['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
