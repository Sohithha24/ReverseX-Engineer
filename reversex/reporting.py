"""Human-readable Simple/Developer report builders from VerifiedResults + artifacts.

Does not call Meta/Muse. Does not invent evidence. Reuses build_verified_results().
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from reversex.verification import (
    JOB_ID_RE,
    VerifiedFinding,
    VerifiedResults,
    VerificationStatus,
    build_verified_results,
    load_artifact_bundle,
)

STATUS_LABELS = {
    VerificationStatus.verified.value: 'Verified for tested behavior',
    VerificationStatus.partially_verified.value: 'Partially verified',
    VerificationStatus.not_verified.value: 'Not verified',
    VerificationStatus.contradicted.value: 'Conflicting evidence',
    VerificationStatus.requires_review.value: 'Needs review',
}

STATUS_HELP = {
    VerificationStatus.verified.value: 'Supported by recorded observations or validation results for the tested scope.',
    VerificationStatus.partially_verified.value: 'Some required evidence is present, but the claim is incomplete or limited.',
    VerificationStatus.not_verified.value: 'Available evidence does not establish this claim.',
    VerificationStatus.contradicted.value: 'Recorded evidence conflicts with the claim.',
    VerificationStatus.requires_review.value: 'Evidence exists but cannot be evaluated reliably without human review.',
}


def _safe_json(job_root: Path, *parts: str) -> dict[str, Any] | list[Any] | None:
    root = job_root.resolve()
    path = root.joinpath(*parts).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def app_display_name(target_id: str | None) -> str:
    if target_id == 'calculator':
        return 'MiniCalc'
    if target_id == 'taskboard':
        return 'TaskBoard'
    if target_id == 'contactpad':
        return 'ContactPad'
    if target_id == 'it-tools':
        return 'IT-Tools'
    try:
        from reversex.targets import get_target

        return get_target(target_id).label or (target_id or 'Unknown application')
    except Exception:
        return target_id or 'Unknown application'


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def outcome_blurb(verified: VerifiedResults) -> str:
    status = (verified.investigation_status or 'unknown').lower()
    app = app_display_name(verified.target_application)
    feature = verified.feature_investigated or 'the selected feature'
    vs = verified.validation_summary or {}
    pipeline = str(verified.pipeline or '').lower()
    recon = verified.reconstruction_status or {}
    understand_only = pipeline == 'investigate_only' or str(recon.get('status') or '').lower() == 'skipped'
    if status == 'completed' and vs.get('failed') == 0 and (vs.get('passed') or 0) > 0:
        return (
            f'ReverseX finished investigating {app} ({feature}). '
            f'The recreation matched the original in {vs.get("passed")} tested scenario(s).'
        )
    if status == 'completed' and (vs.get('failed') or 0) > 0:
        return (
            f'ReverseX finished investigating {app}, but the recreation differed from the original '
            f'in {vs.get("failed")} tested scenario(s).'
        )
    if status == 'completed' and understand_only:
        return (
            f'ReverseX finished investigating {app} ({feature}). '
            f'Reconstruction was not requested, so there are no original-vs-recreation test scores.'
        )
    if status in ('incomplete', 'budget_exhausted'):
        return (
            f'The investigation of {app} ended before all goals were completed '
            f'({status.replace("_", " ")}). Some findings may be incomplete.'
        )
    if status == 'failed':
        return f'The investigation of {app} did not complete successfully. See limitations and errors below.'
    if verified.availability == 'partial':
        return f'Results for {app} are only partially available. Treat unfinished sections as incomplete.'
    return f'ReverseX recorded an investigation of {app} with status “{status}”.'


def narrate_error_event(event: dict[str, Any]) -> dict[str, str]:
    """Plain-English card for investigation errors (Muse parse failures, startup, etc.)."""
    from reversex.meta import humanize_muse_error

    status = str(event.get('status') or 'error')
    kind = str(event.get('error_kind') or '') or (
        'startup_error' if status == 'startup_error' else ''
    )
    explanation = humanize_muse_error(kind or None, event.get('error'))
    step = event.get('step')
    preview = ''
    diag = event.get('error_diagnostics') or {}
    if isinstance(diag, dict) and diag.get('message_preview'):
        preview = str(diag.get('message_preview'))[:120]
    happened = explanation
    if preview:
        happened = f'{explanation} Reply preview: “{preview}”'
    return {
        'step': str(step) if step is not None else '',
        'action': 'error',
        'what_reversex_did': 'Stopped without performing another browser action.',
        'what_happened': happened,
        'what_that_shows': (
            'The investigation ended early so ReverseX would not invent an unsafe or guessed action.'
        ),
        'recorded_purpose': f'error_kind={kind}' if kind else status,
    }


def narrate_event(event: dict[str, Any]) -> dict[str, str]:
    """Plain-English timeline card from a recorded event — no invented intent."""
    status = str(event.get('status') or '')
    if status in ('error', 'startup_error') or (
        event.get('error') and not (event.get('decision') or {}).get('action')
    ):
        return narrate_error_event(event)

    decision = event.get('decision') or {}
    action = str(decision.get('action') or 'unknown')
    reason = decision.get('reason')
    value = decision.get('value')
    after = ((event.get('after') or {}).get('visible_text') or '')
    before = ((event.get('before') or {}).get('visible_text') or '')
    step = event.get('step')

    if action == 'fill':
        shown = 'empty text' if value in (None, '') else f'“{value}”'
        did = f'Entered {shown} into a form field.'
    elif action == 'click':
        did = 'Clicked a button on the page.'
        if value is not None:
            did = f'Clicked a control (associated value: {value}).'
    elif action == 'reload':
        did = 'Refreshed the page.'
    elif action == 'stop':
        did = 'Stopped the investigation.'
    else:
        did = f'Performed a recorded “{action}” action.'

    # Prefer newly appeared lines after a change; otherwise a short after/before snippet.
    before_lines = {ln.strip() for ln in before.splitlines() if ln.strip()}
    new_lines = [ln.strip() for ln in after.splitlines() if ln.strip() and ln.strip() not in before_lines]
    control_changes = list((event.get('after') or {}).get('control_changes') or event.get('control_changes') or [])
    change_bits = []
    for ch in control_changes[:3]:
        if not isinstance(ch, dict):
            continue
        label = ch.get('label') or 'control'
        field = ch.get('field') or 'value'
        after_v = ch.get('after')
        change_bits.append(f'{label} {field}→{after_v!r}')
    if change_bits:
        obs_source = 'Control changes: ' + ' · '.join(change_bits)
    elif new_lines:
        obs_source = ' · '.join(new_lines[:3])
    elif after and after != before:
        obs_source = after
    else:
        obs_source = after or before or '(no visible text recorded)'
    obs = re.sub(r'\s+', ' ', obs_source).strip()
    if len(obs) > 220:
        obs = obs[:217] + '…'

    shows = 'A page change was recorded after this action.'
    if action == 'reload':
        shows = 'The page state after refresh was recorded for comparison.'
    elif control_changes:
        shows = 'One or more form control values/states changed after this action.'
    elif action == 'fill' and value in (None, ''):
        shows = 'An empty input was prepared for submission.'
    elif action == 'fill':
        shows = 'A specific input value was prepared for later actions.'
    elif action == 'click' and after:
        if re.search(r'task name is required', after, re.I):
            shows = 'The application showed a required-field message for the tested empty submission.'
        elif re.search(r'no tasks yet', after, re.I) and value in (None, ''):
            shows = 'The empty-task list hint was still visible after this click.'
        elif new_lines:
            shows = 'New visible content appeared after the click.'
        elif after != before:
            shows = 'The visible page content changed after the click.'

    purpose = str(reason) if reason else ''
    return {
        'step': str(step) if step is not None else '',
        'action': action,
        'what_reversex_did': did,
        'what_happened': obs,
        'what_that_shows': shows,
        'recorded_purpose': purpose,
    }


def explain_failed_test(test: dict[str, Any]) -> dict[str, str]:
    """Failure explanation from a validation test record — no root-cause invention."""
    status = str(test.get('status') or '')
    test_id = str(test.get('test_id') or 'unknown')
    description = str(test.get('description') or test_id)
    original = (test.get('original') or {}).get('observed_state') or {}
    recon = (test.get('reconstruction') or {}).get('observed_state') or {}
    diffs = test.get('differences') or []
    orig_err = (test.get('original') or {}).get('error')
    recon_err = (test.get('reconstruction') or {}).get('error')

    def summarize_state(state: dict[str, Any]) -> str:
        if not state:
            return 'No structured observation was recorded.'
        parts: list[str] = []
        if 'result_text' in state and state.get('result_text') is not None:
            parts.append(f'result text “{state.get("result_text")}”')
        if state.get('validation_message_normalized'):
            parts.append(f'validation message “{state.get("validation_message_normalized")}”')
        if state.get('task_visible') is True:
            parts.append('task visible')
        if state.get('task_visible') is False:
            parts.append('task not visible')
        tasks = state.get('tasks_visible') or []
        if tasks:
            parts.append('tasks: ' + ', '.join(str(t) for t in tasks[:5]))
        if state.get('contains_tokens'):
            parts.append('tokens: ' + ', '.join(str(t) for t in state.get('contains_tokens')[:5]))
        excerpt = state.get('visible_text_excerpt')
        if not parts and excerpt:
            text = re.sub(r'\s+', ' ', str(excerpt)).strip()
            return text[:180] + ('…' if len(text) > 180 else '')
        return '; '.join(parts) if parts else 'Observed state recorded without a short summary field.'

    if status == 'invalid':
        why = 'This comparison could not be executed reliably, so it is not counted as a behavioral pass or fail.'
        if orig_err or recon_err:
            why += f' Details: {orig_err or recon_err}'
        return {
            'test_id': test_id,
            'status': status,
            'what_we_tested': description,
            'original_did': summarize_state(original) if not orig_err else f'Could not observe original ({orig_err})',
            'reconstruction_did': summarize_state(recon) if not recon_err else f'Could not observe reconstruction ({recon_err})',
            'what_was_different': 'Not applicable — the test was invalid.',
            'why_it_matters': why,
        }

    diff_text = '; '.join(str(d) for d in diffs) if diffs else 'Recorded observations differed under the same actions.'
    return {
        'test_id': test_id,
        'status': status,
        'what_we_tested': description,
        'original_did': summarize_state(original),
        'reconstruction_did': summarize_state(recon),
        'what_was_different': diff_text,
        'why_it_matters': (
            'The recreated feature produced a different observable result than the original under this test. '
            'This is a reconstruction mismatch, not proof that the original application is defective.'
        ),
    }


def build_timeline(investigation_report: dict[str, Any] | None) -> list[dict[str, str]]:
    if not investigation_report:
        return []
    out: list[dict[str, str]] = []
    for event in investigation_report.get('events') or []:
        if not isinstance(event, dict):
            continue
        status = str(event.get('status') or '')
        if status in ('error', 'startup_error'):
            out.append(narrate_error_event(event))
            continue
        if status != 'ok':
            # Preserve unexpected statuses only when a decision was recorded.
            if not (event.get('decision') or {}).get('action'):
                continue
        if not (event.get('decision') or {}).get('action'):
            continue
        out.append(narrate_event(event))
    return out


def how_we_know_chain(verified: VerifiedResults, graph: dict[str, Any] | None) -> list[dict[str, str]]:
    """Readable observation → finding → test chain for nontechnical users."""
    chain: list[dict[str, str]] = []
    for f in verified.verified_findings:
        evidence_notes = [e.note or e.location for e in f.supporting_evidence[:3] if e.available]
        chain.append(
            {
                'title': f.claim_text,
                'status': status_label(f.verification_status.value),
                'scope': f.verification_scope,
                'evidence': '; '.join(evidence_notes) if evidence_notes else 'See supporting evidence references.',
                'tests': ', '.join(f.related_test_ids) if f.related_test_ids else '—',
            }
        )
    if graph and not chain:
        for node in (graph.get('nodes') or [])[:12]:
            if node.get('type') in ('observation', 'validation_outcome', 'requirement'):
                chain.append(
                    {
                        'title': str(node.get('description') or node.get('id')),
                        'status': str(node.get('status') or node.get('type')),
                        'scope': 'EvidenceGraph node',
                        'evidence': str(node.get('evidence_ref') or '—'),
                        'tests': '—',
                    }
                )
    return chain


def _md_findings(title: str, findings: list[VerifiedFinding]) -> list[str]:
    lines = [f'## {title}', '']
    if not findings:
        lines.append('_None._')
        lines.append('')
        return lines
    for f in findings:
        lines.append(f'### {f.claim_text}')
        lines.append('')
        lines.append(f'- **Status:** {status_label(f.verification_status.value)}')
        lines.append(f'- **Scope:** {f.verification_scope}')
        if f.limitations:
            lines.append('- **Limitations:**')
            for lim in f.limitations:
                lines.append(f'  - {lim}')
        if f.supporting_evidence:
            lines.append('- **Supporting evidence:**')
            for ref in f.supporting_evidence:
                note = f' — {ref.note}' if ref.note else ''
                lines.append(f'  - `{ref.location}`{note}')
        if f.contradictory_evidence:
            lines.append('- **Contradictory evidence:**')
            for ref in f.contradictory_evidence:
                note = f' — {ref.note}' if ref.note else ''
                lines.append(f'  - `{ref.location}`{note}')
        lines.append('')
    return lines


def render_simple_markdown(
    verified: VerifiedResults,
    *,
    timeline: list[dict[str, str]],
    failures: list[dict[str, str]],
    how_we_know: list[dict[str, str]],
) -> str:
    app = app_display_name(verified.target_application)
    vs = verified.validation_summary or {}
    rs = verified.repair_summary or {}
    recon = verified.reconstruction_status or {}
    lines = [
        '# ReverseX Simple Report',
        '',
        f'**Investigation ID:** `{verified.investigation_id}`',
        f'**Application:** {app}',
        f'**Feature:** {verified.feature_investigated or "—"}',
        f'**Status:** {verified.investigation_status or "—"}',
        f'**Availability:** {verified.availability}',
        '',
        '## Outcome',
        '',
        outcome_blurb(verified),
        '',
        '## What ReverseX did',
        '',
    ]
    if timeline:
        for item in timeline:
            purpose = f' (recorded note: {item["recorded_purpose"]})' if item.get('recorded_purpose') else ''
            lines.append(f'1. **{item["what_reversex_did"]}**{purpose}')
            lines.append(f'   - What happened: {item["what_happened"]}')
            lines.append(f'   - What that shows: {item["what_that_shows"]}')
    else:
        lines.append('_No recorded browser actions are available for this investigation._')

    if verified.problems:
        lines.extend(['', '## Why the investigation had problems', ''])
        for p in verified.problems:
            lines.append(f'- {p.description}')
            for note in p.notes[:2]:
                lines.append(f'  - Note: {note}')

    lines.extend(['', '## What we discovered (verified)', ''])
    if verified.verified_findings:
        for f in verified.verified_findings:
            lines.append(f'- {f.claim_text}')
            lines.append(f'  - Scope: {f.verification_scope}')
            for lim in f.limitations[:2]:
                lines.append(f'  - Limitation: {lim}')
    else:
        lines.append('_No fully verified findings._')

    lines.extend(['', '## Partially verified', ''])
    if verified.partially_verified_findings:
        for f in verified.partially_verified_findings:
            lines.append(f'- {f.claim_text} ({status_label(f.verification_status.value)})')
            for lim in f.limitations[:2]:
                lines.append(f'  - {lim}')
    else:
        lines.append('_None._')

    lines.extend(['', '## Unverified / uncertain', ''])
    uncertain = verified.unsupported_findings + verified.requires_review_findings + verified.contradicted_findings
    if uncertain:
        for f in uncertain:
            lines.append(f'- [{status_label(f.verification_status.value)}] {f.claim_text}')
    else:
        lines.append('_None listed._')

    lines.extend(
        [
            '',
            '## How we know',
            '',
        ]
    )
    if how_we_know:
        for item in how_we_know:
            lines.append(f'- **{item["title"]}** ({item["status"]})')
            lines.append(f'  - Evidence: {item["evidence"]}')
            lines.append(f'  - Related tests: {item["tests"]}')
    else:
        lines.append('_No readable evidence chain available yet._')

    lines.extend(['', '## Recreation & testing', ''])
    recon_status = str(recon.get('status') or '').lower()
    if verified.pipeline == 'investigate_only' or recon_status == 'skipped':
        lines.append('- Reconstruction was not requested.')
        lines.append('- Independent validation was not requested for this investigation.')
    else:
        lines.append(f'- Reconstruction status: {recon.get("status") or "—"}')
        lines.append(f'- Files: {", ".join(recon.get("files") or []) or "—"}')
        lines.append(f'- Tests passed: {vs.get("passed", "—")}')
        lines.append(f'- Tests failed: {vs.get("failed", "—")}')
        lines.append(f'- Tests invalid: {vs.get("invalid", "—")}')
        if vs.get('behavioral_match_rate_percent') is not None:
            lines.append(f'- Behavioral match: {vs.get("behavioral_match_rate_percent")}%')
        else:
            lines.append('- Behavioral match: —')
    lines.append('')

    if failures:
        lines.extend(['## What went wrong in testing', ''])
        for fail in failures:
            lines.append(f'### {fail["test_id"]} ({fail["status"]})')
            lines.append(f'- What we tested: {fail["what_we_tested"]}')
            lines.append(f'- Original: {fail["original_did"]}')
            lines.append(f'- Recreation: {fail["reconstruction_did"]}')
            lines.append(f'- Difference: {fail["what_was_different"]}')
            lines.append(f'- Why it matters: {fail["why_it_matters"]}')
            lines.append('')

    lines.extend(['## Repair', ''])
    if rs:
        kind = rs.get('evaluation_kind')
        label = 'Controlled Fault-Injection Evaluation' if kind == 'controlled_fault_injection' else 'Pipeline repair'
        lines.append(f'- {label}')
        lines.append(
            f'- Match rate: {rs.get("initial_match_rate_percent")}% → {rs.get("final_match_rate_percent")}%'
        )
        lines.append(f'- Attempts: {rs.get("attempts")}')
        lines.append(f'- Stopped reason: {rs.get("stopped_reason")}')
        if kind == 'controlled_fault_injection':
            lines.append('- Note: This is a deliberate fault-injection evaluation, not an organic Muse failure.')
    else:
        lines.append('_No repair was recorded for this investigation._')

    lines.extend(['', '## What remains uncertain', ''])
    for item in verified.untested_behaviors[:8]:
        lines.append(f'- {item}')
    for lim in verified.coverage_limitations:
        lines.append(f'- {lim}')
    lines.append('')
    lines.append('_This report uses the shared VerifiedResults object. It does not invent discoveries._')
    lines.append('')
    return '\n'.join(lines)


def render_developer_markdown(
    verified: VerifiedResults,
    *,
    timeline: list[dict[str, str]],
    failures: list[dict[str, str]],
    investigation_report: dict[str, Any] | None,
    behavior_spec: dict[str, Any] | None,
    validation: dict[str, Any] | None,
) -> str:
    app = app_display_name(verified.target_application)
    vs = verified.validation_summary or {}
    lines = [
        '# ReverseX Developer Report',
        '',
        f'- Investigation ID: `{verified.investigation_id}`',
        f'- Target: `{verified.target_application}` ({app})',
        f'- Feature: {verified.feature_investigated or "—"}',
        f'- Mode: {verified.investigation_mode or "—"}',
        f'- Pipeline: {verified.pipeline or "—"}',
        f'- Status: {verified.investigation_status or "—"}',
        f'- Availability: {verified.availability}',
        f'- Generated at: {verified.generated_at}',
    ]
    if investigation_report:
        lines.append(f'- Investigation API request count: {investigation_report.get("api_request_count", "—")}')
        lines.append(f'- Model/note: {investigation_report.get("note") or "—"}')
    lines.append('')
    lines.extend(_md_findings('Verified findings', verified.verified_findings))
    lines.extend(_md_findings('Partially verified findings', verified.partially_verified_findings))
    lines.extend(_md_findings('Unsupported findings', verified.unsupported_findings))
    lines.extend(_md_findings('Contradicted findings', verified.contradicted_findings))
    lines.extend(_md_findings('Needs review', verified.requires_review_findings))

    lines.extend(['## Contradictions', ''])
    if verified.contradictions:
        for c in verified.contradictions:
            lines.append(f'- **{c.contradiction_id}:** {c.description}')
            lines.append(f'  - Claim: {c.claim_text}')
            lines.append(f'  - Expected: {c.expected}')
            lines.append(f'  - Observed: {c.observed}')
    else:
        lines.append('_None._')
    lines.append('')

    lines.extend(['## Problems', ''])
    if verified.problems:
        for p in verified.problems:
            lines.append(f'- **{p.category.value}:** {p.description}')
    else:
        lines.append('_None._')
    lines.append('')

    lines.extend(['## Timeline (recorded events)', ''])
    for item in timeline:
        lines.append(f'- Step {item.get("step") or "?"} / `{item.get("action")}`: {item["what_reversex_did"]}')
        if item.get('recorded_purpose'):
            lines.append(f'  - Recorded purpose: {item["recorded_purpose"]}')
        lines.append(f'  - Observation excerpt: {item["what_happened"]}')
    if not timeline:
        lines.append('_No events._')
    lines.append('')

    lines.extend(['## Behavioral requirements & hypotheses', ''])
    if behavior_spec:
        for req in behavior_spec.get('requirements') or []:
            lines.append(
                f'- `{req.get("id")}` ({req.get("kind")}): {req.get("observed_result") or req.get("action_performed")}'
            )
    else:
        lines.append('_Specification not available._')
    lines.append('')

    lines.extend(
        [
            '## Reconstruction',
            '',
            f'```json\n{json.dumps(verified.reconstruction_status, indent=2)}\n```'
            if verified.reconstruction_status
            else '_Not available._',
            '',
            '## Validation summary',
            '',
            f'```json\n{json.dumps(vs, indent=2)}\n```' if vs else '_Not available._',
            '',
        ]
    )

    if validation:
        lines.extend(['## Validation tests', ''])
        for t in validation.get('tests') or []:
            lines.append(f'- `{t.get("test_id")}` → `{t.get("status")}`')
            if t.get('differences'):
                lines.append(f'  - differences: {t.get("differences")}')
        lines.append('')

    if failures:
        lines.extend(['## Failure explanations', ''])
        for fail in failures:
            lines.append(f'### {fail["test_id"]}')
            for key in (
                'what_we_tested',
                'original_did',
                'reconstruction_did',
                'what_was_different',
                'why_it_matters',
            ):
                lines.append(f'- {key}: {fail[key]}')
            lines.append('')

    lines.extend(
        [
            '## Repair summary',
            '',
            f'```json\n{json.dumps(verified.repair_summary, indent=2)}\n```'
            if verified.repair_summary
            else '_No repair report._',
            '',
            '## Coverage limitations',
            '',
        ]
    )
    for lim in verified.coverage_limitations:
        lines.append(f'- {lim}')
    lines.append('')
    lines.append('_Developer and Simple reports share the same VerifiedResults conclusions._')
    lines.append('')
    return '\n'.join(lines)


def build_report_package(artifacts_root: Path, investigation_id: str) -> dict[str, Any]:
    if not JOB_ID_RE.match(investigation_id):
        raise ValueError('Invalid investigation id')
    verified = build_verified_results(artifacts_root, investigation_id)
    if verified.availability == 'unavailable':
        return {
            'verified': verified,
            'timeline': [],
            'failures': [],
            'how_we_know': [],
            'simple_markdown': render_simple_markdown(verified, timeline=[], failures=[], how_we_know=[]),
            'developer_markdown': render_developer_markdown(
                verified,
                timeline=[],
                failures=[],
                investigation_report=None,
                behavior_spec=None,
                validation=None,
            ),
        }

    bundle = load_artifact_bundle(artifacts_root, investigation_id)
    timeline = build_timeline(bundle.investigation_report)
    failures: list[dict[str, str]] = []
    if bundle.validation:
        for test in bundle.validation.get('tests') or []:
            if test.get('status') in ('fail', 'invalid'):
                failures.append(explain_failed_test(test))
    graph = _safe_json(bundle.job_root, 'evidence_graph.json')
    how = how_we_know_chain(verified, graph if isinstance(graph, dict) else None)

    # Repair narrative for failures when repair exists
    if verified.repair_summary and failures:
        rs = verified.repair_summary
        for fail in failures:
            fail['repair_attempted'] = 'yes'
            fail['repair_result'] = (
                f"{rs.get('initial_match_rate_percent')}% → {rs.get('final_match_rate_percent')}% "
                f"(stopped: {rs.get('stopped_reason')})"
            )
    else:
        for fail in failures:
            fail['repair_attempted'] = 'no'
            fail['repair_result'] = 'No repair recorded for this investigation.'

    return {
        'verified': verified,
        'timeline': timeline,
        'failures': failures,
        'how_we_know': how,
        'investigation_report': bundle.investigation_report,
        'behavior_spec': bundle.behavior_spec,
        'validation': bundle.validation,
        'simple_markdown': render_simple_markdown(
            verified, timeline=timeline, failures=failures, how_we_know=how
        ),
        'developer_markdown': render_developer_markdown(
            verified,
            timeline=timeline,
            failures=failures,
            investigation_report=bundle.investigation_report,
            behavior_spec=bundle.behavior_spec,
            validation=bundle.validation,
        ),
    }
