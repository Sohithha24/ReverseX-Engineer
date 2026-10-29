import { useEffect, useMemo, useState } from 'react'
import { api, apiBaseUrl } from './api/client'
import type {
  AuthorizedTarget,
  HealthResponse,
  InvestigationMode,
  Pipeline,
  TargetId,
} from './api/types'
import { EvidenceGraphView } from './components/EvidenceGraphView'
import { RepairPanel } from './components/RepairPanel'
import { ValidationPanel } from './components/ValidationPanel'
import { useInvestigation } from './hooks/useInvestigation'
import './App.css'

const STAGES = [
  'queued',
  'investigating',
  'specifying',
  'reconstructing',
  'validating',
  'completed',
  'incomplete',
  'failed',
] as const

const FALLBACK_TARGETS: AuthorizedTarget[] = [
  {
    id: 'taskboard',
    label: 'TaskBoard',
    origin: 'http://127.0.0.1:8001',
    description: 'Add task / TaskBoard visible behavior',
    validation_suite: 'taskboard',
    reuse_reconstruction_allowed: true,
  },
  {
    id: 'calculator',
    label: 'MiniCalc',
    origin: 'http://127.0.0.1:8003',
    description: 'MiniCalc visible arithmetic behavior',
    validation_suite: 'calculator',
    reuse_reconstruction_allowed: false,
  },
]

export default function App() {
  const [page, setPage] = useState<'landing' | 'workspace'>('landing')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [targets, setTargets] = useState<AuthorizedTarget[]>(FALLBACK_TARGETS)
  const [targetId, setTargetId] = useState<TargetId>('taskboard')
  const [mode, setMode] = useState<InvestigationMode>('scripted')
  const [pipeline, setPipeline] = useState<Pipeline>('full')
  const [reuse, setReuse] = useState(true)
  const [maxActions, setMaxActions] = useState(10)
  const inv = useInvestigation()

  const selected = useMemo(
    () => targets.find((t) => t.id === targetId) || FALLBACK_TARGETS[0],
    [targets, targetId],
  )

  useEffect(() => {
    void api
      .health()
      .then((h) => {
        setHealth(h)
        setHealthError(null)
      })
      .catch((e) => setHealthError(e instanceof Error ? e.message : String(e)))
    void api
      .listTargets()
      .then((res) => {
        if (res.targets?.length) setTargets(res.targets)
      })
      .catch(() => {
        /* keep fallback allowlist */
      })
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const jobId = params.get('job')
    if (jobId && /^[a-f0-9]{32}$/.test(jobId)) {
      setPage('workspace')
      void inv.watchExisting(jobId)
    }
    // Intentionally once on mount for deep-link verification.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!selected.reuse_reconstruction_allowed) {
      setReuse(false)
    }
  }, [selected])

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <p className="eyebrow">Meta Global AI Developer Hackathon</p>
          <h1>ReverseX Engineer</h1>
        </div>
        <nav>
          <button type="button" className={page === 'landing' ? 'active' : ''} onClick={() => setPage('landing')}>
            Overview
          </button>
          <button
            type="button"
            className={page === 'workspace' ? 'active' : ''}
            onClick={() => setPage('workspace')}
          >
            Workspace
          </button>
        </nav>
      </header>

      {page === 'landing' && (
        <section className="hero panel">
          <h2>Investigate. Specify. Reconstruct. Verify.</h2>
          <p>
            Authorized local behavioral investigation powered by Meta Muse Spark, with an independent
            Playwright oracle and an evidence graph grounded in recorded artifacts.
          </p>
          <div className="hero-actions">
            <button type="button" className="primary" onClick={() => setPage('workspace')}>
              Open investigation workspace
            </button>
            <button type="button" onClick={() => void inv.loadDemoGraph().then(() => setPage('workspace'))}>
              Load demo EvidenceGraph
            </button>
            <button
              type="button"
              onClick={() => void inv.loadControlledRepairDemo().then(() => setPage('workspace'))}
            >
              Load Controlled Repair Evaluation
            </button>
          </div>
          <div className="health-card">
            <h3>Backend health</h3>
            <p className="mono">API: {apiBaseUrl()}</p>
            {healthError && <p className="error-text">{healthError}</p>}
            {health && (
              <pre>{JSON.stringify(health, null, 2)}</pre>
            )}
          </div>
        </section>
      )}

      {page === 'workspace' && (
        <main className="workspace">
          <section className="panel controls">
            <h2>Investigation controls</h2>
            <label>
              Application
              <select
                value={targetId}
                onChange={(e) => setTargetId(e.target.value as TargetId)}
              >
                {targets.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <p className="small muted">
              Selected: <strong>{selected.label}</strong> · {selected.description}
            </p>
            <label>
              Authorized target origin
              <input value={selected.origin} readOnly />
            </label>
            <label>
              Mode
              <select value={mode} onChange={(e) => setMode(e.target.value as InvestigationMode)}>
                <option value="scripted">Scripted browser smoke test</option>
                <option value="muse">Live Muse Spark investigation</option>
              </select>
            </label>
            <label>
              Pipeline
              <select value={pipeline} onChange={(e) => setPipeline(e.target.value as Pipeline)}>
                <option value="full">Full (investigate → spec → reconstruct → validate)</option>
                <option value="investigate_only">Investigate only</option>
              </select>
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={reuse}
                disabled={!selected.reuse_reconstruction_allowed}
                onChange={(e) => setReuse(e.target.checked)}
              />
              Reuse existing Phase 2 reconstruction (TaskBoard only)
            </label>
            <label>
              Max actions
              <input
                type="number"
                min={1}
                max={20}
                value={maxActions}
                onChange={(e) => setMaxActions(Number(e.target.value))}
              />
            </label>
            <button
              type="button"
              className="primary"
              disabled={inv.busy}
              onClick={() =>
                void inv.start({
                  mode,
                  pipeline,
                  reuse_reconstruction: selected.reuse_reconstruction_allowed ? reuse : false,
                  max_actions: maxActions,
                  target_id: targetId,
                })
              }
            >
              {inv.busy ? 'Running…' : 'Start investigation'}
            </button>
            {inv.error && <p className="error-text">{inv.error}</p>}
          </section>

          <section className="panel">
            <h2>Live status</h2>
            <ol className="timeline">
              {STAGES.map((s) => {
                const current = inv.job?.status || ''
                const active = current === s
                return (
                  <li key={s} className={active ? 'active' : ''}>
                    {s}
                    {active ? ' ← current' : ''}
                  </li>
                )
              })}
            </ol>
            {inv.job && (
              <pre>{JSON.stringify({
                id: inv.job.id,
                status: inv.job.status,
                target_id: inv.job.target_id,
                stages: inv.job.stages,
                errors: inv.job.errors,
                meta_api_requests_total: inv.job.meta_api_requests_total,
              }, null, 2)}</pre>
            )}
          </section>

          <section className="panel">
            <h2>Recorded events</h2>
            {!inv.events?.events?.length && <p className="muted">No events yet.</p>}
            <div className="event-list">
              {(inv.events?.events || []).map((ev, idx) => (
                <pre key={idx}>{JSON.stringify(ev, null, 2)}</pre>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>Behavioral specification</h2>
            {inv.results?.specification_present ? (
              <p className="muted">Frozen specification present on backend for this job.</p>
            ) : (
              <p className="muted">Specification not available yet.</p>
            )}
            {inv.results && (
              <pre>{JSON.stringify({
                specification_present: inv.results.specification_present,
                reconstruction: inv.results.reconstruction_reused_or_generated,
                validation_summary: inv.results.validation,
              }, null, 2)}</pre>
            )}
          </section>

          <section className="panel">
            <h2>Validation results</h2>
            <ValidationPanel
              validation={inv.validation}
              investigationId={inv.job?.id || null}
              screenshots={inv.screenshots}
            />
          </section>

          <section className="panel">
            <h2>Repair results</h2>
            <RepairPanel repair={inv.repair} />
          </section>

          <section className="panel wide">
            <h2>EvidenceGraph</h2>
            <EvidenceGraphView graph={inv.graph} />
          </section>
        </main>
      )}
    </div>
  )
}
