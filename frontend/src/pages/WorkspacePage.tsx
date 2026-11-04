import {
  Activity,
  ChevronDown,
  ChevronUp,
  FileText,
  GitBranch,
  Hammer,
  MonitorPlay,
  ShieldCheck,
  Wand2,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { useInvestigation } from '../hooks/useInvestigation'
import type { InvestigationSummary } from '../api/types'
import { EvidenceGraphView } from '../components/EvidenceGraphView'
import { RepairPanel } from '../components/RepairPanel'
import { ReportResultsView } from '../components/ReportResultsView'
import { ValidationPanel } from '../components/ValidationPanel'
import { Button, EmptyState, Mono, Panel, StatusPill, StatCard, cx } from '../components/ui'
import { TERMINAL_STATUSES, api } from '../api/client'

export type WorkspaceTab = 'reports' | 'progress' | 'live' | 'reconstruction' | 'validation' | 'evidence' | 'repair'

type Inv = ReturnType<typeof useInvestigation>
type DevTool = 'live' | 'reconstruction' | 'validation' | 'evidence' | 'repair'

const HUMAN_STAGES: Array<{ key: string; label: string; match: RegExp }> = [
  { key: 'exploring', label: 'Exploring', match: /^investigation$/i },
  { key: 'discovering', label: 'Discovering', match: /^specification$/i },
  { key: 'reconstructing', label: 'Reconstructing', match: /^reconstruction$/i },
  { key: 'testing', label: 'Testing', match: /^validation$/i },
  { key: 'repairing', label: 'Repairing', match: /^repair$/i },
]

function stageStatus(value: unknown): string {
  if (value && typeof value === 'object' && 'status' in value) {
    return String((value as { status: unknown }).status)
  }
  return String(value ?? '')
}

function stageExecuted(value: unknown): boolean {
  if (value && typeof value === 'object' && 'executed' in value) {
    return Boolean((value as { executed?: unknown }).executed)
  }
  return false
}

export function WorkspacePage({
  inv,
  tab,
  onTab,
  onOpenResults,
  onLoadControlledRepair,
}: {
  inv: Inv
  tab: WorkspaceTab
  onTab: (t: WorkspaceTab) => void
  onOpenResults: () => void
  onLoadControlledRepair: () => void
}) {
  const [devOpen, setDevOpen] = useState(false)
  const [devTool, setDevTool] = useState<DevTool>('live')
  const [history, setHistory] = useState<InvestigationSummary[]>([])
  const [historyNote, setHistoryNote] = useState<string | null>(null)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyBusyId, setHistoryBusyId] = useState<string | null>(null)
  const jobDone = Boolean(inv.job && TERMINAL_STATUSES.has(inv.job.status))
  const primaryTab = tab === 'reports' ? 'reports' : 'progress'

  useEffect(() => {
    let cancelled = false
    void api
      .listInvestigations(24)
      .then((res) => {
        if (cancelled) return
        setHistory(res.investigations || [])
        setHistoryNote(res.note || null)
        setHistoryError(null)
      })
      .catch((e) => {
        if (cancelled) return
        setHistoryError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      cancelled = true
    }
  }, [inv.job?.id, inv.job?.status])

  async function openSavedInvestigation(id: string) {
    setHistoryBusyId(id)
    try {
      const url = new URL(window.location.href)
      url.searchParams.set('job', id)
      window.history.replaceState({}, '', url.toString())
      await inv.watchExisting(id)
      onTab('reports')
    } finally {
      setHistoryBusyId(null)
    }
  }

  const humanStages = useMemo(() => {
    const stages = inv.job?.stages || {}
    const pipeline = String(inv.job?.pipeline || 'full')
    return HUMAN_STAGES.filter((item) => {
      if (item.key === 'repairing') {
        const repair = stages.repair
        return stageExecuted(repair) || /fail|running|attempt/i.test(stageStatus(repair))
      }
      if (pipeline === 'investigate_only') {
        // Understand-only: do not surface skipped specification/recon/validation as “Discovering”.
        return item.key === 'exploring'
      }
      return Object.keys(stages).some((k) => item.match.test(k)) || item.key === 'exploring'
    }).map((item) => {
      const entry = Object.entries(stages).find(([k]) => item.match.test(k))
      const status = entry ? stageStatus(entry[1]) : inv.busy ? 'pending' : '—'
      return { ...item, status }
    })
  }, [inv.job, inv.busy])

  if (inv.showingControlledRepairExample) {
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Controlled Repair Example</h2>
            <p className="mt-1 max-w-3xl text-sm text-rx-muted">
              This example deliberately introduces a defect into a reconstruction so ReverseX can demonstrate
              detecting and correcting it. It is separate from any investigation you currently have open.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {inv.job && (
              <Button
                variant="secondary"
                onClick={() => {
                  inv.exitControlledRepairExample()
                  onOpenResults()
                }}
              >
                Back to investigation results
              </Button>
            )}
            <Button variant="ghost" onClick={() => inv.exitControlledRepairExample()}>
              Close example
            </Button>
          </div>
        </div>
        {inv.error && (
          <p className="rounded-xl border border-rx-danger/40 bg-rx-danger/10 px-3 py-2 text-sm text-rx-danger">
            {inv.error}
          </p>
        )}
        <Panel title="Before and after">
          <RepairPanel repair={inv.demoRepair} controlledExample />
        </Panel>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">
            {primaryTab === 'reports' ? 'Results' : 'Current investigation'}
          </h2>
          <p className="mt-1 text-sm text-rx-muted">
            {inv.job
              ? primaryTab === 'reports'
                ? 'Readable findings from the open investigation. Switch to the Developer Report for technical detail.'
                : 'Follow what ReverseX is doing. Open Results when the investigation finishes.'
              : 'No investigation is open in this browser session. Start one, open a completed example, or use a saved job link.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={onLoadControlledRepair}>
            Controlled Repair Example
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-rx-line pb-3">
        <button
          type="button"
          onClick={() => onTab('reports')}
          className={cx(
            'inline-flex items-center gap-2 rounded-[12px] border px-3 py-2 text-sm transition',
            primaryTab === 'reports'
              ? 'border-rx-blue/30 bg-rx-blue-soft font-medium text-rx-blue'
              : 'border-rx-line bg-white text-rx-muted hover:text-rx-text',
          )}
        >
          <FileText size={14} />
          Results
        </button>
        <button
          type="button"
          onClick={() => onTab('progress')}
          className={cx(
            'inline-flex items-center gap-2 rounded-[12px] border px-3 py-2 text-sm transition',
            primaryTab === 'progress'
              ? 'border-rx-blue/30 bg-rx-blue-soft font-medium text-rx-blue'
              : 'border-rx-line bg-white text-rx-muted hover:text-rx-text',
          )}
        >
          <MonitorPlay size={14} />
          Progress
        </button>
      </div>

      {inv.error && (
        <p className="rounded-xl border border-rx-danger/40 bg-rx-danger/10 px-3 py-2 text-sm text-rx-danger">
          {plainError(inv.error)}
        </p>
      )}

      {tab === 'reports' && (
        <div className="space-y-4">
          {!inv.job && !inv.humanReport && (
            <Panel>
              <EmptyState>
                Results appear here after you finish an investigation, reopen a saved job below, or open Explore
                Completed Example from Home.
              </EmptyState>
            </Panel>
          )}
          {(inv.job || inv.humanReport) && (
            <ReportResultsView
              report={inv.humanReport}
              graph={inv.graph}
              validation={inv.validation}
              screenshots={inv.screenshots}
              investigationId={inv.job?.id || null}
            />
          )}
          <Panel title="Saved investigations">
            {historyError && <p className="mb-2 text-sm text-rx-danger">{plainError(historyError)}</p>}
            {!history.length && !historyError && (
              <EmptyState>No saved investigations found in local artifacts yet.</EmptyState>
            )}
            {!!history.length && (
              <ul className="space-y-2">
                {history.slice(0, 12).map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-rx-line bg-white px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusPill status={item.status} />
                        <span className="text-sm font-medium text-rx-text">
                          {item.target_id || 'unknown'} · {item.feature || 'feature'}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-rx-muted">
                        <Mono>{item.id.slice(0, 8)}…</Mono>
                        {item.updated_at ? ` · ${item.updated_at}` : ''}
                      </p>
                    </div>
                    <Button
                      variant="secondary"
                      disabled={historyBusyId === item.id}
                      onClick={() => void openSavedInvestigation(item.id)}
                    >
                      {historyBusyId === item.id ? 'Opening…' : 'Open'}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            {historyNote && <p className="mt-3 text-xs text-rx-muted">{historyNote}</p>}
          </Panel>
        </div>
      )}

      {tab !== 'reports' && (
        <div className="space-y-4">
          <ProgressPanel
            inv={inv}
            humanStages={humanStages}
            jobDone={jobDone}
            onOpenResults={onOpenResults}
          />

          <Panel
            title="Developer tools"
            action={
              <Button variant="ghost" onClick={() => setDevOpen((v) => !v)}>
                {devOpen ? (
                  <>
                    Hide <ChevronUp size={14} />
                  </>
                ) : (
                  <>
                    Show <ChevronDown size={14} />
                  </>
                )}
              </Button>
            }
          >
            {!devOpen && (
              <EmptyState>
                Browser evidence, reconstruction files, validation details, How We Know (evidence graph), and
                repair records.
              </EmptyState>
            )}
            {devOpen && (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {(
                    [
                      { id: 'live', label: 'Browser & events', icon: MonitorPlay },
                      { id: 'reconstruction', label: 'Reconstruction', icon: Wand2 },
                      { id: 'validation', label: 'Validation details', icon: ShieldCheck },
                      { id: 'evidence', label: 'How We Know', icon: GitBranch },
                      { id: 'repair', label: 'Repair details', icon: Hammer },
                    ] as const
                  ).map((item) => {
                    const Icon = item.icon
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => setDevTool(item.id)}
                        className={cx(
                          'inline-flex items-center gap-2 rounded-[12px] border px-3 py-2 text-sm transition',
                          devTool === item.id
                            ? 'border-rx-blue/30 bg-rx-blue-soft font-medium text-rx-blue'
                            : 'border-rx-line bg-white text-rx-muted hover:text-rx-text',
                        )}
                      >
                        <Icon size={14} />
                        {item.label}
                      </button>
                    )
                  })}
                </div>

                {devTool === 'live' && <LiveInvestigation inv={inv} />}
                {devTool === 'reconstruction' && <ReconstructionView inv={inv} />}
                {devTool === 'validation' && (
                  <ValidationPanel
                    validation={inv.validation}
                    investigationId={inv.job?.id || null}
                    screenshots={inv.screenshots}
                  />
                )}
                {devTool === 'evidence' && (
                  <div className="space-y-3">
                    <p className="text-sm text-rx-muted">
                      Interactive evidence graph for developers. The Simple Report includes a plain-language
                      “How We Know” section.
                    </p>
                    <EvidenceGraphView graph={inv.graph} />
                  </div>
                )}
                {devTool === 'repair' && <RepairPanel repair={inv.repair} />}
              </div>
            )}
          </Panel>
        </div>
      )}
    </div>
  )
}

function plainError(message: string): string {
  if (/404/i.test(message) && /investigation|job|repair/i.test(message)) {
    return 'That investigation could not be opened. If it finished successfully, try Saved investigations or Explore Completed Example. Incomplete in-memory jobs may disappear after an API restart.'
  }
  if (/Failed to fetch|NetworkError|ECONNREFUSED/i.test(message)) {
    return 'Cannot reach the ReverseX backend. Confirm the local API is running, then try again.'
  }
  return message
}

function ProgressPanel({
  inv,
  humanStages,
  jobDone,
  onOpenResults,
}: {
  inv: Inv
  humanStages: Array<{ key: string; label: string; status: string }>
  jobDone: boolean
  onOpenResults: () => void
}) {
  if (!inv.job) {
    return (
      <Panel title="Progress">
        <EmptyState>
          Start an investigation from New Investigation, reopen a saved job from Results, or open Explore
          Completed Example from Home.
        </EmptyState>
      </Panel>
    )
  }

  const preparing =
    jobDone || humanStages.every((s) => /completed|skipped|reused|frozen|perfect|pass/i.test(s.status))

  return (
    <div className="space-y-4">
      <Panel title="What ReverseX is doing">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <StatusPill status={String(inv.job.status)} />
          <span className="text-sm text-rx-muted">
            App: <span className="text-rx-text">{inv.job.target_id}</span>
            {inv.job.feature ? (
              <>
                {' · '}
                Feature: <span className="text-rx-text">{inv.job.feature}</span>
              </>
            ) : null}
            {' · '}
            Mode: <span className="text-rx-text">{inv.job.mode === 'muse' ? 'Fresh AI' : 'Guided Demo'}</span>
            {inv.job.application_url ? (
              <>
                {' · '}
                URL: <span className="text-rx-text">{inv.job.application_url}</span>
              </>
            ) : null}
          </span>
        </div>
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {humanStages.map((stage) => (
            <li key={stage.key} className="rounded-[12px] border border-rx-line bg-white px-3 py-3">
              <p className="text-sm font-medium text-rx-text">{stage.label}</p>
              <div className="mt-2">
                <StatusPill status={stage.status || 'pending'} />
              </div>
            </li>
          ))}
          <li className="rounded-[12px] border border-rx-line bg-white px-3 py-3">
            <p className="text-sm font-medium text-rx-text">Preparing results</p>
            <div className="mt-2">
              <StatusPill status={preparing ? (jobDone ? 'ready' : 'running') : 'pending'} />
            </div>
          </li>
        </ol>
        {jobDone && (
          <div className="mt-4">
            <Button variant="primary" onClick={onOpenResults}>
              View results
            </Button>
          </div>
        )}
        {!!inv.job.errors?.length && (
          <div className="mt-4 rounded-xl border border-rx-danger/30 bg-rx-danger/10 p-3 text-sm text-rx-danger">
            {inv.job.errors.map(plainError).join(' · ')}
          </div>
        )}
      </Panel>

      <details className="rounded-[12px] border border-rx-line bg-white p-4">
        <summary className="cursor-pointer text-sm font-medium text-rx-text">Technical event details</summary>
        <div className="mt-3 space-y-2 text-xs text-rx-muted">
          <p>
            Job ID: <Mono>{inv.job.id}</Mono>
          </p>
          <p>Meta API requests recorded: {inv.job.meta_api_requests_total ?? 0}</p>
          <p>Pipeline: {inv.job.pipeline || '—'}</p>
        </div>
      </details>
    </div>
  )
}

function LiveInvestigation({ inv }: { inv: Inv }) {
  const events = inv.events?.events || []
  const shots = inv.screenshots

  return (
    <div className="grid gap-4 xl:grid-cols-12">
      <Panel className="xl:col-span-3" title="Configuration">
        {inv.job ? (
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="text-rx-muted">Status</span>
              <StatusPill status={String(inv.job.status)} />
            </div>
            <div>
              <p className="text-rx-muted">Job</p>
              <Mono className="break-all text-rx-text">{inv.job.id}</Mono>
            </div>
            <div>
              <p className="text-rx-muted">Target</p>
              <p>{inv.job.target_id || '—'}</p>
            </div>
            <div>
              <p className="text-rx-muted">Mode</p>
              <p>{inv.job.mode || '—'}</p>
            </div>
            <div>
              <p className="text-rx-muted">Meta API requests</p>
              <p className="tabular-nums">{inv.job.meta_api_requests_total ?? 0}</p>
            </div>
          </div>
        ) : (
          <EmptyState>No open investigation.</EmptyState>
        )}
      </Panel>

      <Panel className="xl:col-span-5" title="Browser evidence">
        {!shots.length && !events.length && (
          <EmptyState>Screenshots and observations appear as the backend records them.</EmptyState>
        )}
        {!!shots.length && (
          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            {shots.slice(0, 8).map((shot) => (
              <figure key={shot.id} className="overflow-hidden rounded-xl border border-rx-line bg-rx-bg">
                {inv.job?.id && (
                  <img
                    src={api.screenshotUrl(inv.job.id, shot.filename)}
                    alt={shot.filename}
                    className="max-h-40 w-full object-cover object-top"
                  />
                )}
                <figcaption className="truncate px-2 py-1.5 text-[11px] text-rx-muted">{shot.filename}</figcaption>
              </figure>
            ))}
          </div>
        )}
      </Panel>

      <Panel className="xl:col-span-4" title="Action timeline">
        {!events.length && <EmptyState>Recorded actions appear here during and after investigation.</EmptyState>}
        <ol className="max-h-[560px] space-y-2 overflow-y-auto">
          {events.slice(-40).map((ev, idx) => {
            const decision =
              ev.decision && typeof ev.decision === 'object'
                ? (ev.decision as Record<string, unknown>)
                : null
            const title = String(decision?.action || ev.type || ev.event || `Step ${ev.step ?? idx + 1}`)
            const detail = String(
              decision?.reason || ev.description || ev.message || ev.action || JSON.stringify(ev).slice(0, 160),
            )
            return (
              <li key={idx} className="rounded-[12px] border border-rx-line bg-white p-3 text-xs">
                <div className="mb-1 flex items-center gap-2">
                  <Activity size={12} className="text-rx-blue" />
                  <span className="font-medium capitalize">{title}</span>
                </div>
                <p className="text-rx-muted">{detail}</p>
              </li>
            )
          })}
        </ol>
      </Panel>
    </div>
  )
}

function ReconstructionView({ inv }: { inv: Inv }) {
  const recon = inv.results?.reconstruction_reused_or_generated
  const reconObj = recon && typeof recon === 'object' ? (recon as Record<string, unknown>) : null
  const files = Array.isArray(reconObj?.files)
    ? (reconObj.files as unknown[])
    : Array.isArray(reconObj?.generated_files)
      ? (reconObj.generated_files as unknown[])
      : []

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Specification" value={inv.results?.specification_present ? 'Present' : 'Pending'} />
        <StatCard
          label="Reconstruction"
          value={reconObj ? String(reconObj.status || reconObj.source || 'Ready') : inv.results ? 'See details' : '—'}
        />
        <StatCard label="Job status" value={inv.job?.status || '—'} />
        <StatCard
          label="Screenshots"
          value={inv.screenshots.length}
          hint="Recorded evidence only — apps are not continuously live"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Original application evidence">
          {!inv.screenshots.length && <EmptyState>No screenshots recorded yet.</EmptyState>}
          <div className="grid gap-3 sm:grid-cols-2">
            {inv.screenshots
              .filter((s) => /orig|target|fixture|app/i.test(s.filename) || !/recon/i.test(s.filename))
              .slice(0, 6)
              .map((shot) => (
                <figure key={shot.id} className="overflow-hidden rounded-xl border border-rx-line">
                  {inv.job?.id && (
                    <img
                      src={api.screenshotUrl(inv.job.id, shot.filename)}
                      alt={shot.filename}
                      className="max-h-44 w-full object-cover object-top"
                    />
                  )}
                  <figcaption className="truncate px-2 py-1 text-[11px] text-rx-muted">{shot.filename}</figcaption>
                </figure>
              ))}
          </div>
        </Panel>

        <Panel title="Generated reconstruction evidence">
          <p className="mb-3 text-sm text-rx-muted">
            Screenshots below are recorded outputs. They do not imply the reconstructed app is continuously
            running here.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {inv.screenshots
              .filter((s) => /recon/i.test(s.filename))
              .slice(0, 6)
              .map((shot) => (
                <figure key={shot.id} className="overflow-hidden rounded-xl border border-rx-line">
                  {inv.job?.id && (
                    <img
                      src={api.screenshotUrl(inv.job.id, shot.filename)}
                      alt={shot.filename}
                      className="max-h-44 w-full object-cover object-top"
                    />
                  )}
                  <figcaption className="truncate px-2 py-1 text-[11px] text-rx-muted">{shot.filename}</figcaption>
                </figure>
              ))}
            {!inv.screenshots.some((s) => /recon/i.test(s.filename)) && (
              <EmptyState>No reconstruction-labeled screenshots in this job yet.</EmptyState>
            )}
          </div>
        </Panel>
      </div>

      <Panel title="Generated files">
        {!!files.length ? (
          <ul className="space-y-1 text-sm">
            {files.map((f, i) => (
              <li key={i} className="rounded-[12px] border border-rx-line bg-rx-beige px-3 py-2 font-mono text-xs">
                {typeof f === 'string' ? f : JSON.stringify(f)}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState>Reconstruction files appear here when available.</EmptyState>
        )}
      </Panel>
    </div>
  )
}
