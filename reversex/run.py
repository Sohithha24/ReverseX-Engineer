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

DEFAULT_ORIGIN = 'http://127.0.0.1:8001'

# Investigation objectives inferred only from recorded browser observations.
OBJECTIVE_KEYS = (
    'empty_task_submission',
    'valid_task_submission',
    'reload_persistence',
)

_VALIDATION_RE = re.compile(r'task name is required', re.IGNORECASE)
_EMPTY_HINT_RE = re.compile(r'no tasks yet', re.IGNORECASE)


def scripted_decision(snapshot, step: int):
    """Deterministic smoke test only. NOT an autonomous AI agent."""
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


def evaluate_objectives(events: list[dict]) -> dict:
    """Derive which investigation goals have observation-backed evidence.

    Only uses recorded before/after visible text and executed decisions.
    Never invents outcomes the browser did not show.
    """
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
            # Empty submission: click Add with no non-empty fill in this attempt.
            if (last_fill is None or last_fill.strip() == '') and _VALIDATION_RE.search(after):
                objectives['empty_task_submission'] = {
                    'supported': True,
                    'evidence': f'step {event.get("step")}: after click, page showed validation text',
                }
            # Valid submission: non-empty fill then click; task text appears and empty-state gone.
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


def finalize_status(
    *,
    events: list[dict],
    objectives: dict,
    stopped: bool,
    budget_hit: bool,
    errored: bool,
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
    all_supported = all(objectives[key]['supported'] for key in OBJECTIVE_KEYS)
    if stopped and all_supported:
        return 'completed'
    if stopped:
        return 'incomplete'
    if budget_hit:
        return 'budget_exhausted'
    return 'incomplete'


def explore(mode: str, url: str | None = None, output_dir: str = 'artifacts', max_actions: int = 12):
    load_dotenv()
    from reversex.browser import validate_target
    if mode not in ('scripted', 'muse'):
        raise ValueError('mode must be scripted or muse')
    if max_actions < 1 or max_actions > 20:
        raise ValueError('max_actions must be between 1 and 20')
    origin = os.getenv('REVERSEX_ALLOWED_ORIGIN', DEFAULT_ORIGIN)
    target = url or origin
    validate_target(target, origin)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    started = time.monotonic()
    stopped = False
    budget_hit = False
    errored = False
    api_requests = 0
    planner = None
    try:
        if mode == 'muse':
            from reversex.meta import MusePlanner
            planner = MusePlanner()
        with SafeBrowser(origin) as browser:
            snapshot = browser.goto(target)
            try:
                browser.screenshot(str(output / 'original.png'))
            except Exception as exc:
                history.append({'status': 'screenshot_error', 'phase': 'original', 'error': str(exc)[:240]})
            for step in range(max_actions):
                if time.monotonic() - started > 90:
                    history.append({'status': 'budget_exhausted', 'error': '90-second wall-clock budget reached'})
                    budget_hit = True
                    break
                try:
                    decision = planner.decide(snapshot, history) if planner else scripted_decision(snapshot, step)
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

    objectives = evaluate_objectives(history)
    final_status = finalize_status(
        events=history,
        objectives=objectives,
        stopped=stopped,
        budget_hit=budget_hit,
        errored=errored,
    )
    report = {
        'project': 'ReverseX Engineer',
        'mode': mode,
        'note': ('Offline scripted browser smoke test — not AI-led investigation' if mode == 'scripted'
                 else 'Live Muse Spark requested; review event logs to verify model behavior'),
        'target': target,
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
    parser.add_argument('--max-actions', type=int, default=12)
    parser.add_argument('--output-dir', default='artifacts')
    args = parser.parse_args()
    report = explore(args.mode, args.url, args.output_dir, args.max_actions)
    summary = {k: v for k, v in report.items() if k != 'events'}
    print(json.dumps(summary, indent=2))
    print(f"Steps recorded: {len(report['events'])}. Full report: {args.output_dir}/report.json")
    if report['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
