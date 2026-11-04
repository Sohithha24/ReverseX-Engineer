import { useEffect, useRef, useState } from 'react'
import { TERMINAL_STATUSES, api } from './api/client'
import type { AuthorizedTarget, CreateInvestigationRequest, HealthResponse } from './api/types'
import { Shell, type AppView } from './components/ui'
import { useInvestigation } from './hooks/useInvestigation'
import { OverviewPage } from './pages/OverviewPage'
import { SetupPage } from './pages/SetupPage'
import { WorkspacePage, type WorkspaceTab } from './pages/WorkspacePage'

const FALLBACK_TARGETS: AuthorizedTarget[] = [
  {
    id: 'taskboard',
    label: 'TaskBoard',
    origin: 'http://127.0.0.1:8001',
    description: 'Add task / TaskBoard visible behavior',
    validation_suite: 'taskboard',
    reuse_reconstruction_allowed: true,
    independent_validation_available: true,
  },
  {
    id: 'calculator',
    label: 'MiniCalc',
    origin: 'http://127.0.0.1:8003',
    description: 'MiniCalc visible arithmetic behavior',
    validation_suite: 'calculator',
    reuse_reconstruction_allowed: false,
    independent_validation_available: true,
  },
  {
    id: 'contactpad',
    label: 'ContactPad',
    origin: 'http://127.0.0.1:8005',
    description: 'Submit a contact message and view confirmation',
    validation_suite: null,
    reuse_reconstruction_allowed: false,
    independent_validation_available: false,
    kind: 'allowlisted_custom',
  },
  {
    id: 'it-tools',
    label: 'IT-Tools',
    origin: 'http://127.0.0.1:8010',
    description: 'Base64 text encoding and decoding',
    validation_suite: null,
    reuse_reconstruction_allowed: false,
    independent_validation_available: false,
    kind: 'allowlisted_custom',
  },
]

function normalizeTab(raw?: string): WorkspaceTab {
  if (raw === 'reports') return 'reports'
  if (raw === 'progress' || raw === 'live') return 'progress'
  if (raw === 'reconstruction' || raw === 'validation' || raw === 'evidence' || raw === 'repair') {
    return 'progress'
  }
  return 'progress'
}

export default function App() {
  const [view, setView] = useState<AppView>('overview')
  const [tab, setTab] = useState<WorkspaceTab>('progress')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [targets, setTargets] = useState<AuthorizedTarget[]>(FALLBACK_TARGETS)
  const [targetsError, setTargetsError] = useState<string | null>(null)
  const [exploreBusy, setExploreBusy] = useState(false)
  const [exploreError, setExploreError] = useState<string | null>(null)
  const inv = useInvestigation()
  const wasBusy = useRef(false)

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
        if (res.targets?.length) {
          setTargets(res.targets)
          setTargetsError(null)
        }
      })
      .catch((e) => {
        setTargetsError(e instanceof Error ? e.message : String(e))
      })
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const jobId = params.get('job')
    if (jobId && /^[a-f0-9]{32}$/.test(jobId)) {
      setView('workspace')
      setTab('reports')
      void inv.watchExisting(jobId).catch(() => {
        setExploreError(
          'That investigation link is not available. The backend may have restarted. Use Explore Completed Example or start a Guided Demo.',
        )
      })
    }
    // Intentionally once on mount for deep-link verification.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (wasBusy.current && !inv.busy && inv.job && TERMINAL_STATUSES.has(inv.job.status)) {
      setView('workspace')
      setTab('reports')
    }
    wasBusy.current = inv.busy
  }, [inv.busy, inv.job])

  async function handleStart(payload: CreateInvestigationRequest) {
    setExploreError(null)
    setView('workspace')
    setTab('progress')
    await inv.start(payload)
  }

  async function exploreCompletedExample() {
    setExploreBusy(true)
    setExploreError(null)
    setView('workspace')
    setTab('reports')
    try {
      const result = await inv.openCompletedExample()
      if (result.kind === 'launched') {
        setTab('progress')
      } else {
        setTab('reports')
      }
      if (inv.error) {
        setExploreError(inv.error)
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setExploreError(
        `${message} No completed example could be loaded. Start a Guided Demo from New Investigation (TaskBoard + reconstruction reuse).`,
      )
      setView('overview')
    } finally {
      setExploreBusy(false)
    }
  }

  function onNavigate(next: AppView, opts?: { tab?: string }) {
    setView(next)
    if (next === 'workspace') {
      setTab(normalizeTab(opts?.tab))
    }
  }

  return (
    <Shell view={view} workspaceTab={tab} hasJob={Boolean(inv.job)} onNavigate={onNavigate}>
      {view === 'overview' && (
        <OverviewPage
          health={health}
          healthError={healthError}
          exploreBusy={exploreBusy || inv.busy}
          exploreError={exploreError}
          onStart={() => {
            setExploreError(null)
            setView('setup')
          }}
          onExploreDemo={() => void exploreCompletedExample()}
        />
      )}
      {view === 'setup' && (
        <SetupPage
          targets={targets}
          targetsError={targetsError}
          busy={inv.busy}
          onStart={(payload) => void handleStart(payload)}
        />
      )}
      {view === 'workspace' && (
        <WorkspacePage
          inv={inv}
          tab={tab}
          onTab={setTab}
          onOpenResults={() => setTab('reports')}
          onLoadControlledRepair={() => {
            void inv.loadControlledRepairDemo()
          }}
        />
      )}
    </Shell>
  )
}
