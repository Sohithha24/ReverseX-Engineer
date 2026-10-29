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


def evaluate_objectives(events: list[dict], target: AppTarget | None = None) -> dict:
    profile = target or get_target('taskboard')
    if profile.id == 'calculator':
        return evaluate_calculator_objectives(events)
    return evaluate_taskboard_objectives(events)


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
):
    load_dotenv()
    from reversex.browser import validate_target
    if mode not in ('scripted', 'muse'):
        raise ValueError('mode must be scripted or muse')
    if max_actions < 1 or max_actions > 20:
        raise ValueError('max_actions must be between 1 and 20')
    target = get_target(target_id)
    origin = target.origin
    # Optional env override only when investigating the default taskboard target.
    if target.id == 'taskboard':
        origin = os.getenv('REVERSEX_ALLOWED_ORIGIN', origin)
    dest = url or origin
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
                    else:
                        decision = scripted_decision(snapshot, step)
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
                    # Do not auto-retry state-changing actions after ambiguous failure.
                    errored = True
                    history.append({'step': step + 1, 'status': 'error', 'error': str(exc)[:240]})
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
        'note': ('Offline scripted browser smoke test — not AI-led investigation' if mode == 'scripted'
                 else 'Live Muse Spark requested; review event logs to verify model behavior'),
        'target': dest,
        'status': final_status,
        'duration_seconds': round(time.monotonic() - started, 2),
        'max_actions': max_actions,
        'api_request_count': api_requests if mode == 'muse' else 0,
        'objectives': objectives,
        'events': history,
        'not_implemented': ['behavioral specification', 'code reconstruction', 'oracle-based validation'],
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description='ReverseX Engineer Phase 1b browser explorer')
    parser.add_argument('--mode', choices=['scripted', 'muse'], default='scripted')
    parser.add_argument('--url', default=None)
    parser.add_argument('--target', default='taskboard', choices=['taskboard', 'calculator'])
    parser.add_argument('--max-actions', type=int, default=12)
    parser.add_argument('--output-dir', default='artifacts')
    args = parser.parse_args()
    report = explore(args.mode, args.url, args.output_dir, args.max_actions, target_id=args.target)
    summary = {k: v for k, v in report.items() if k != 'events'}
    print(json.dumps(summary, indent=2))
    print(f"Steps recorded: {len(report['events'])}. Full report: {args.output_dir}/report.json")
    if report['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
