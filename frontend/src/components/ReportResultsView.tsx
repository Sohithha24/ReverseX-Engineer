import { ChevronDown, ChevronRight, Download, FileText } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type {
  EvidenceGraph,
  FailureExplanation,
  HumanReportResponse,
  ScreenshotItem,
  TimelineItem,
  ValidationResultsFile,
  VerificationStatus,
  VerifiedFinding,
} from '../api/types'
import { EvidenceGraphView } from './EvidenceGraphView'
import { EmptyState, Mono, Panel, StatCard, StatusPill, cx } from './ui'

type ReportTab = 'simple' | 'developer'

function appName(target?: string | null) {
  if (target === 'calculator') return 'MiniCalc'
  if (target === 'taskboard') return 'TaskBoard'
  if (target === 'contactpad') return 'ContactPad'
  if (target === 'it-tools') return 'IT-Tools'
  return target || 'Unknown application'
}

function verificationTone(status: VerificationStatus) {
  if (status === 'verified') return 'border-rx-sage/25 bg-rx-sage-soft text-rx-sage'
  if (status === 'partially_verified') return 'border-rx-warn/25 bg-[#fff7ed] text-rx-warn'
  if (status === 'contradicted') return 'border-rx-danger/25 bg-[#fef3f2] text-rx-danger'
  if (status === 'requires_review') return 'border-rx-blue/20 bg-rx-blue-soft text-rx-blue'
  return 'border-rx-line bg-rx-beige text-rx-muted'
}

function VerificationBadge({
  status,
  labels,
}: {
  status: VerificationStatus
  labels: Record<string, string>
}) {
  return (
    <span className={cx('inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium', verificationTone(status))}>
      {labels[status] || status}
    </span>
  )
}

function Expandable({
  title,
  children,
  defaultOpen = false,
}: {
  title: string
  children: ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-[12px] border border-rx-line bg-white">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm font-medium text-rx-text"
        onClick={() => setOpen((v) => !v)}
      >
        <span>{title}</span>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      {open && <div className="border-t border-rx-line bg-rx-beige/50 px-3 py-3 text-sm text-rx-muted">{children}</div>}
    </div>
  )
}

function FindingCard({
  finding,
  labels,
  help,
}: {
  finding: VerifiedFinding
  labels: Record<string, string>
  help: Record<string, string>
}) {
  return (
    <article
      className={cx(
        'rounded-[12px] border p-4',
        finding.verification_status === 'verified'
          ? 'border-rx-sage/20 bg-rx-sage-soft'
          : finding.verification_status === 'contradicted' || finding.verification_status === 'not_verified'
            ? 'border-rx-line bg-rx-beige'
            : 'border-rx-blue/15 bg-rx-blue-soft',
      )}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <VerificationBadge status={finding.verification_status} labels={labels} />
        <span className="text-[11px] text-rx-muted">{finding.claim_category}</span>
      </div>
      <p className="text-sm leading-relaxed text-rx-text">{finding.claim_text}</p>
      <p className="mt-2 text-xs text-rx-muted">Scope: {finding.verification_scope}</p>
      <p className="mt-1 text-xs text-rx-muted">{help[finding.verification_status]}</p>
      {!!finding.limitations.length && (
        <ul className="mt-2 space-y-1 text-xs text-rx-warn">
          {finding.limitations.map((lim) => (
            <li key={lim}>• {lim}</li>
          ))}
        </ul>
      )}
      <Expandable title="Supporting evidence">
        {!finding.supporting_evidence.length && <EmptyState>No supporting evidence references.</EmptyState>}
        <ul className="space-y-1 text-xs">
          {finding.supporting_evidence.map((ref) => (
            <li key={ref.ref_id}>
              <Mono className="text-rx-text">{ref.location}</Mono>
              {ref.note ? <span className="text-rx-muted"> — {ref.note}</span> : null}
            </li>
          ))}
        </ul>
        {!!finding.contradictory_evidence.length && (
          <div className="mt-3">
            <p className="mb-1 text-xs font-medium text-rx-danger">Contradictory evidence</p>
            <ul className="space-y-1 text-xs">
              {finding.contradictory_evidence.map((ref) => (
                <li key={ref.ref_id}>
                  <Mono>{ref.location}</Mono>
                  {ref.note ? ` — ${ref.note}` : ''}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Expandable>
    </article>
  )
}

function TimelineCard({
  item,
  investigationId,
  screenshots,
}: {
  item: TimelineItem
  investigationId: string | null
  screenshots: ScreenshotItem[]
}) {
  const shot = screenshots.find((s) =>
    item.step ? s.filename.includes(`step`) && s.filename.includes(String(item.step)) : false,
  )
  return (
    <article className="rounded-[12px] border border-rx-line bg-white p-4 shadow-[0_1px_2px_rgba(38,50,56,0.04)]">
      <p className="text-xs font-medium uppercase tracking-wide text-rx-blue">
        Step {item.step || '—'} · {item.action}
      </p>
      <div className="mt-3 space-y-2 text-sm">
        <p>
          <span className="font-medium text-rx-text">What ReverseX did: </span>
          <span className="text-rx-muted">{item.what_reversex_did}</span>
        </p>
        <p>
          <span className="font-medium text-rx-text">What happened: </span>
          <span className="text-rx-muted">{item.what_happened}</span>
        </p>
        <p>
          <span className="font-medium text-rx-text">What that shows: </span>
          <span className="text-rx-muted">{item.what_that_shows}</span>
        </p>
        {item.recorded_purpose ? (
          <p>
            <span className="font-medium text-rx-text">Recorded purpose: </span>
            <span className="text-rx-muted">{item.recorded_purpose}</span>
          </p>
        ) : (
          <p className="text-xs text-rx-muted">No recorded purpose was stored for this action.</p>
        )}
      </div>
      {investigationId && shot && (
        <img
          src={api.screenshotUrl(investigationId, shot.filename)}
          alt={shot.filename}
          className="mt-3 max-h-40 w-full rounded-xl border border-rx-line object-cover object-top"
        />
      )}
      <div className="mt-3">
        <Expandable title="Technical event details">
          <pre className="overflow-x-auto text-xs text-rx-muted">{JSON.stringify(item, null, 2)}</pre>
        </Expandable>
      </div>
    </article>
  )
}

function FailureCard({ fail }: { fail: FailureExplanation }) {
  return (
    <article className="rounded-[12px] border border-rx-danger/25 bg-[#fef3f2] p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-semibold text-rx-text">{fail.test_id}</h4>
        <StatusPill status={fail.status} />
      </div>
      <dl className="space-y-2 text-sm">
        <div>
          <dt className="text-xs uppercase tracking-wide text-rx-muted">What we tested</dt>
          <dd className="text-rx-text">{fail.what_we_tested}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-rx-muted">Original application</dt>
          <dd className="text-rx-text">{fail.original_did}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-rx-muted">Reconstructed application</dt>
          <dd className="text-rx-text">{fail.reconstruction_did}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-rx-muted">What was different</dt>
          <dd className="text-rx-text">{fail.what_was_different}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-rx-muted">Why it matters</dt>
          <dd className="text-rx-muted">{fail.why_it_matters}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-rx-muted">Repair</dt>
          <dd className="text-rx-muted">
            {fail.repair_attempted === 'yes'
              ? `Attempted. ${fail.repair_result || ''}`
              : fail.repair_result || 'No repair recorded.'}
          </dd>
        </div>
      </dl>
    </article>
  )
}

export function ReportResultsView({
  report,
  graph,
  validation,
  screenshots,
  investigationId,
}: {
  report: HumanReportResponse | null
  graph: EvidenceGraph | null
  validation: ValidationResultsFile | null
  screenshots: ScreenshotItem[]
  investigationId: string | null
}) {
  const [tab, setTab] = useState<ReportTab>('simple')

  const verified = report?.verified
  const labels = report?.status_labels || {}
  const help = report?.status_help || {}

  const outcome = useMemo(() => {
    if (!verified) return 'Open a completed investigation to view reports.'
    const app = appName(verified.target_application)
    const feature = verified.feature_investigated || 'the selected feature'
    const status = verified.investigation_status || 'unknown'
    const vs = verified.validation_summary
    const understandOnly =
      verified.pipeline === 'investigate_only' ||
      String(verified.reconstruction_status?.status || '').toLowerCase() === 'skipped'
    if (status === 'completed' && vs && (vs.failed || 0) === 0 && (vs.passed || 0) > 0) {
      return `ReverseX finished investigating ${app} (${feature}). The recreation matched the original in ${vs.passed} tested scenario(s).`
    }
    if (status === 'completed' && vs && (vs.failed || 0) > 0) {
      return `ReverseX finished investigating ${app}, but the recreation differed in ${vs.failed} tested scenario(s).`
    }
    if (status === 'completed' && understandOnly) {
      return `ReverseX finished investigating ${app} (${feature}). Reconstruction was not requested, so there are no original-vs-recreation test scores.`
    }
    if (status === 'incomplete' || status === 'budget_exhausted') {
      return `The investigation of ${app} ended before all goals were completed (${status.replace(/_/g, ' ')}).`
    }
    if (status === 'failed') {
      return `The investigation of ${app} did not complete successfully.`
    }
    if (verified.availability === 'partial') {
      return `Results for ${app} are only partially available.`
    }
    return `ReverseX recorded an investigation of ${app} with status “${status}”.`
  }, [verified])

  if (!investigationId) {
    return <EmptyState>Start an investigation or open a deep link with ?job=… to view reports.</EmptyState>
  }

  if (!report || !verified) {
    return (
      <EmptyState>
        Investigation results are not ready yet. Reports appear after the job reaches a terminal state and verified
        findings can be loaded.
      </EmptyState>
    )
  }

  const vs = verified.validation_summary
  const rs = verified.repair_summary
  const recon = verified.reconstruction_status
  const understandOnly =
    verified.pipeline === 'investigate_only' ||
    String(recon?.status || '').toLowerCase() === 'skipped'

  return (
    <div className="space-y-5">
      <Panel>
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-rx-blue">Investigation results</p>
        <h3 className="mt-2 font-serif text-3xl font-medium tracking-tight text-rx-text">
          {appName(verified.target_application)}
        </h3>
        <p className="mt-1 text-sm text-rx-muted">{verified.feature_investigated || 'Feature not recorded'}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusPill status={String(verified.investigation_status || 'unknown')} />
          <span className="text-xs text-rx-muted">Availability: {verified.availability}</span>
          <Mono className="text-[11px]">{verified.investigation_id}</Mono>
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-rx-text">{outcome}</p>
        <div className="mt-5 flex flex-wrap gap-2">
          <a
            className="inline-flex items-center gap-2 rounded-[12px] border border-rx-line bg-rx-beige px-4 py-2.5 text-sm text-rx-text hover:bg-white"
            href={api.simpleReportUrl(verified.investigation_id)}
            download
          >
            <Download size={14} /> Download Simple Report
          </a>
          <a
            className="inline-flex items-center gap-2 rounded-[12px] border border-rx-line bg-rx-beige px-4 py-2.5 text-sm text-rx-text hover:bg-white"
            href={api.developerReportUrl(verified.investigation_id)}
            download
          >
            <Download size={14} /> Download Developer Report
          </a>
        </div>
      </Panel>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ['simple', 'Simple Report'],
            ['developer', 'Developer Report'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cx(
              'inline-flex items-center gap-2 rounded-[12px] border px-4 py-2.5 text-sm transition',
              tab === id
                ? 'border-rx-blue/30 bg-rx-blue-soft font-medium text-rx-blue'
                : 'border-rx-line bg-white text-rx-muted hover:text-rx-text',
            )}
          >
            <FileText size={14} />
            {label}
          </button>
        ))}
      </div>

      {tab === 'simple' && (
        <div className="mx-auto max-w-3xl space-y-8 rounded-[14px] border border-rx-line bg-white px-5 py-8 shadow-[0_1px_2px_rgba(38,50,56,0.04)] sm:px-10">
          <header className="border-b border-rx-beige pb-6">
            <h3 className="font-serif text-3xl font-medium tracking-tight text-rx-text">Simple Report</h3>
            <p className="mt-2 text-sm leading-relaxed text-rx-muted">
              A readable summary of what ReverseX investigated, discovered, reconstructed, and verified.
            </p>
          </header>

          <section className="space-y-3">
            <h4 className="text-xl font-semibold text-rx-text">Investigation Summary</h4>
            <div className="rounded-[12px] border border-rx-line bg-rx-beige p-4 text-sm leading-relaxed text-rx-text">
              {outcome}
            </div>
            {understandOnly ? (
              <div className="rounded-[12px] border border-rx-line bg-rx-blue-soft p-4 text-sm leading-relaxed text-rx-text">
                Reconstruction was not requested. Independent original-vs-recreation scoring was not run for this
                investigation.
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Passed tests" value={vs?.passed ?? '—'} />
                <StatCard label="Failed tests" value={vs?.failed ?? '—'} />
                <StatCard label="Invalid tests" value={vs?.invalid ?? '—'} />
                <StatCard
                  label="Match rate"
                  value={vs?.behavioral_match_rate_percent == null ? '—' : `${vs.behavioral_match_rate_percent}%`}
                />
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h4 className="text-xl font-semibold text-rx-text">What ReverseX Tested</h4>
            {!report.timeline.length && <EmptyState>No recorded browser actions are available.</EmptyState>}
            <div className="space-y-3">
              {report.timeline.map((item, idx) => (
                <TimelineCard
                  key={`${item.step}-${idx}`}
                  item={item}
                  investigationId={investigationId}
                  screenshots={screenshots}
                />
              ))}
            </div>
          </section>

          <section className="space-y-3 border-t border-rx-beige pt-6">
            <h4 className="text-xl font-semibold text-rx-text">What It Discovered</h4>
            <p className="text-xs text-rx-muted">
              Only findings with status “Verified for tested behavior” are listed as established.
            </p>
            {!verified.verified_findings.length && <EmptyState>No fully verified findings.</EmptyState>}
            <div className="space-y-3">
              {verified.verified_findings.map((f) => (
                <FindingCard key={f.claim_id} finding={f} labels={labels} help={help} />
              ))}
            </div>
            {!!verified.partially_verified_findings.length && (
              <div className="space-y-3 pt-2">
                <h5 className="text-sm font-semibold text-rx-text">Partially verified</h5>
                {verified.partially_verified_findings.map((f) => (
                  <FindingCard key={f.claim_id} finding={f} labels={labels} help={help} />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3 border-t border-rx-beige pt-6">
            <h4 className="text-xl font-semibold text-rx-text">What Remains Unknown</h4>
            <p className="text-xs text-rx-muted">
              These are not presented as facts. They include unsupported, contradicted, and needs-review claims.
            </p>
            <div className="space-y-3">
              {[
                ...verified.unsupported_findings,
                ...verified.contradicted_findings,
                ...verified.requires_review_findings,
              ].map((f) => (
                <FindingCard key={f.claim_id} finding={f} labels={labels} help={help} />
              ))}
              {!verified.unsupported_findings.length &&
                !verified.contradicted_findings.length &&
                !verified.requires_review_findings.length && <EmptyState>None listed.</EmptyState>}
            </div>
            <ul className="space-y-1 pt-2 text-sm text-rx-muted">
              {verified.untested_behaviors.map((u) => (
                <li key={u}>• {u}</li>
              ))}
              {verified.coverage_limitations.map((u) => (
                <li key={u}>• {u}</li>
              ))}
            </ul>
          </section>

          <section className="space-y-3 border-t border-rx-beige pt-6">
            <h4 className="text-xl font-semibold text-rx-text">How We Know</h4>
            <p className="text-sm text-rx-muted">
              A readable chain from verified findings to supporting evidence and related tests.
            </p>
            {!report.how_we_know.length && <EmptyState>No readable evidence chain available yet.</EmptyState>}
            <ol className="space-y-3">
              {report.how_we_know.map((item, idx) => (
                <li key={`${item.title}-${idx}`} className="rounded-[12px] border border-rx-line bg-rx-blue-soft p-3 text-sm">
                  <p className="font-medium text-rx-text">{item.title}</p>
                  <p className="mt-1 text-xs font-medium text-rx-blue">{item.status}</p>
                  <p className="mt-2 text-xs text-rx-muted">Evidence: {item.evidence}</p>
                  <p className="text-xs text-rx-muted">Related tests: {item.tests}</p>
                  <p className="text-xs text-rx-muted">Scope: {item.scope}</p>
                </li>
              ))}
            </ol>
          </section>

          <section className="space-y-3 border-t border-rx-beige pt-6">
            <h4 className="text-xl font-semibold text-rx-text">What Was Reconstructed</h4>
            {understandOnly ? (
              <p className="text-sm leading-relaxed text-rx-muted">
                Reconstruction was not requested for this investigation. ReverseX recorded observations only.
              </p>
            ) : (
              <ul className="space-y-1 text-sm text-rx-muted">
                <li>Reconstruction status: {String(recon?.status ?? '—')}</li>
                <li>
                  Files:{' '}
                  {Array.isArray(recon?.files) && recon.files.length
                    ? (recon.files as string[]).join(', ')
                    : '—'}
                </li>
                <li>Testing used independent browser comparisons against the original authorized demo app.</li>
              </ul>
            )}
          </section>

          <section className="space-y-3 border-t border-rx-beige pt-6">
            <h4 className="text-xl font-semibold text-rx-text">Test Results & Problems Found</h4>
            {understandOnly ? (
              <EmptyState>
                Independent validation was not requested, so there are no original-vs-recreation comparison tests.
              </EmptyState>
            ) : (
              <>
                {!report.failures.length && (
                  <EmptyState>No failed or invalid comparison tests were recorded for this investigation.</EmptyState>
                )}
                <div className="space-y-3">
                  {report.failures.map((fail) => (
                    <FailureCard key={fail.test_id} fail={fail} />
                  ))}
                </div>
              </>
            )}
          </section>

          <section className="space-y-3 border-t border-rx-beige pt-6">
            <h4 className="text-xl font-semibold text-rx-text">Repairs</h4>
            {rs ? (
              <div className="rounded-[12px] border border-rx-line bg-rx-beige p-4 text-sm text-rx-muted">
                <p className="font-medium text-rx-text">
                  {rs.evaluation_kind === 'controlled_fault_injection'
                    ? 'Controlled Fault-Injection Evaluation'
                    : 'Pipeline repair'}
                </p>
                <p className="mt-2">
                  Match rate: {rs.initial_match_rate_percent ?? '—'}% → {rs.final_match_rate_percent ?? '—'}%
                </p>
                <p>Attempts: {rs.attempts ?? 0}</p>
                <p>Stopped reason: {rs.stopped_reason || '—'}</p>
                {rs.evaluation_kind === 'controlled_fault_injection' && (
                  <p className="mt-2 text-rx-warn">
                    This is a deliberate fault-injection evaluation, not an organic Muse failure.
                  </p>
                )}
              </div>
            ) : (
              <EmptyState>No repair was recorded for this investigation.</EmptyState>
            )}
          </section>
        </div>
      )}

      {tab === 'developer' && (
        <div className="space-y-5">
          <Panel title="Investigation metadata">
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-rx-muted">Investigation ID</dt>
                <dd>
                  <Mono className="break-all text-rx-text">{verified.investigation_id}</Mono>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-rx-muted">Target</dt>
                <dd>{verified.target_application}</dd>
              </div>
              <div>
                <dt className="text-xs text-rx-muted">Mode</dt>
                <dd>{verified.investigation_mode || '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-rx-muted">Pipeline</dt>
                <dd>{verified.pipeline || '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-rx-muted">API request count</dt>
                <dd>{report.api_request_count ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-rx-muted">Investigation note</dt>
                <dd className="text-rx-muted">{report.investigation_note || '—'}</dd>
              </div>
            </dl>
          </Panel>

          <Panel title="Verification status legend">
            <ul className="space-y-2 text-sm">
              {Object.entries(labels).map(([key]) => (
                <li key={key} className="flex flex-wrap items-start gap-2">
                  <VerificationBadge status={key as VerificationStatus} labels={labels} />
                  <span className="text-rx-muted">{help[key]}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Verified findings (same VerifiedResults)">
            <div className="space-y-3">
              {verified.verified_findings.map((f) => (
                <FindingCard key={f.claim_id} finding={f} labels={labels} help={help} />
              ))}
            </div>
          </Panel>

          <Expandable title="Partially verified / unsupported / contradicted / needs review" defaultOpen>
            <div className="space-y-3">
              {[
                ...verified.partially_verified_findings,
                ...verified.unsupported_findings,
                ...verified.contradicted_findings,
                ...verified.requires_review_findings,
              ].map((f) => (
                <FindingCard key={f.claim_id} finding={f} labels={labels} help={help} />
              ))}
            </div>
          </Expandable>

          <Expandable title="Contradictions & problems">
            {!verified.contradictions.length && !verified.problems.length && (
              <EmptyState>No structured contradictions or problem records.</EmptyState>
            )}
            <ul className="space-y-2 text-xs">
              {verified.contradictions.map((c) => (
                <li key={c.contradiction_id} className="rounded-lg border border-rx-danger/30 p-2">
                  <p className="font-medium text-rx-text">{c.description}</p>
                  <p className="text-rx-muted">Expected: {c.expected}</p>
                  <p className="text-rx-muted">Observed: {c.observed}</p>
                </li>
              ))}
              {verified.problems.map((p) => (
                <li key={p.problem_id} className="rounded-lg border border-rx-line p-2">
                  <p className="font-medium text-rx-text">{p.category}</p>
                  <p className="text-rx-muted">{p.description}</p>
                </li>
              ))}
            </ul>
          </Expandable>

          <Expandable title="Behavioral requirements & hypotheses">
            {!report.requirements?.length && <EmptyState>Specification not available.</EmptyState>}
            <ul className="space-y-1 text-xs">
              {(report.requirements || []).map((r) => (
                <li key={r.id}>
                  <Mono>{r.id}</Mono> ({r.kind}) — {r.observed_result || r.action_performed || '—'}
                </li>
              ))}
            </ul>
          </Expandable>

          <Expandable title="Reconstruction metadata">
            <pre className="overflow-x-auto text-xs">{JSON.stringify(recon || {}, null, 2)}</pre>
          </Expandable>

          <Expandable title="Validation scenarios (original vs reconstruction)">
            {!validation?.tests?.length && <EmptyState>No validation tests loaded.</EmptyState>}
            <div className="space-y-3">
              {(validation?.tests || []).map((t) => (
                <div key={t.test_id} className="rounded-xl border border-rx-line p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="font-medium">{t.test_id}</span>
                    <StatusPill status={t.status} />
                  </div>
                  <p className="mb-2 text-xs text-rx-muted">{t.description}</p>
                  <div className="grid gap-2 md:grid-cols-2">
                    <pre className="max-h-40 overflow-auto rounded-lg bg-rx-bg/60 p-2 text-[11px]">
                      {JSON.stringify(t.original?.observed_state || {}, null, 2)}
                    </pre>
                    <pre className="max-h-40 overflow-auto rounded-lg bg-rx-bg/60 p-2 text-[11px]">
                      {JSON.stringify(t.reconstruction?.observed_state || {}, null, 2)}
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          </Expandable>

          <Expandable title="Repair & revalidation">
            <pre className="overflow-x-auto text-xs">{JSON.stringify(rs || {}, null, 2)}</pre>
          </Expandable>

          <Panel title="Interactive EvidenceGraph">
            <EvidenceGraphView graph={graph} />
          </Panel>

          <Expandable title="Raw VerifiedResults (technical)">
            <pre className="max-h-96 overflow-auto text-xs">{JSON.stringify(verified, null, 2)}</pre>
          </Expandable>
        </div>
      )}
    </div>
  )
}
