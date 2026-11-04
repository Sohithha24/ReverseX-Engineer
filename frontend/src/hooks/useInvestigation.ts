import { useCallback, useEffect, useRef, useState } from 'react'
import { TERMINAL_STATUSES, api } from '../api/client'
import type {
  CreateInvestigationRequest,
  EvidenceGraph,
  EventsResponse,
  HumanReportResponse,
  InvestigationSummary,
  ResultsResponse,
  RepairReport,
  ScreenshotItem,
  ValidationResultsFile,
} from '../api/types'

const POLL_MS = 1500

/** Known completed TaskBoard artifacts that may still be served by a warm backend. */
export const COMPLETED_EXAMPLE_CANDIDATES = [
  '69f0a4845ee347c8831d691aac18951a',
  'ee5bd9ec1a3246f7ba187102ac07bd85',
  '7ae1600203bf4135aebf5fe9090afa24',
  'd447aef7c8f5455d91937d4201601a95',
  'e54e5a1e9be441839c88d5aa12b1e9f6',
]

export function useInvestigation() {
  const [job, setJob] = useState<InvestigationSummary | null>(null)
  const [events, setEvents] = useState<EventsResponse | null>(null)
  const [results, setResults] = useState<ResultsResponse | null>(null)
  const [validation, setValidation] = useState<ValidationResultsFile | null>(null)
  const [repair, setRepair] = useState<RepairReport | null>(null)
  /** Isolated from job repair so the controlled example never fights poll updates. */
  const [demoRepair, setDemoRepair] = useState<RepairReport | null>(null)
  const [showingControlledRepairExample, setShowingControlledRepairExample] = useState(false)
  const [graph, setGraph] = useState<EvidenceGraph | null>(null)
  const [screenshots, setScreenshots] = useState<ScreenshotItem[]>([])
  const [humanReport, setHumanReport] = useState<HumanReportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef<number | null>(null)

  const clearTimer = () => {
    if (timer.current != null) {
      window.clearInterval(timer.current)
      timer.current = null
    }
  }

  const refreshExtras = useCallback(async (id: string, status: string) => {
    try {
      const ev = await api.getEvents(id)
      setEvents(ev)
    } catch {
      /* events may not exist yet */
    }
    if (TERMINAL_STATUSES.has(status)) {
      try {
        setResults(await api.getResults(id))
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      }
      try {
        setValidation(await api.getValidation(id))
      } catch {
        setValidation(null)
      }
      try {
        setRepair(await api.getRepair(id))
      } catch {
        setRepair(null)
      }
      try {
        setGraph(await api.getEvidenceGraph(id))
      } catch {
        /* graph may be partial */
      }
      try {
        const shots = await api.listScreenshots(id)
        setScreenshots(shots.screenshots)
      } catch {
        setScreenshots([])
      }
      try {
        setHumanReport(await api.getHumanReport(id))
      } catch {
        setHumanReport(null)
      }
    }
  }, [])

  const pollOnce = useCallback(
    async (id: string) => {
      const summary = await api.getInvestigation(id)
      setJob(summary)
      await refreshExtras(id, summary.status)
      if (TERMINAL_STATUSES.has(summary.status)) {
        clearTimer()
        setBusy(false)
      }
    },
    [refreshExtras],
  )

  const start = useCallback(
    async (body: CreateInvestigationRequest) => {
      clearTimer()
      setError(null)
      setBusy(true)
      setShowingControlledRepairExample(false)
      setEvents(null)
      setResults(null)
      setValidation(null)
      setRepair(null)
      setGraph(null)
      setScreenshots([])
      setHumanReport(null)
      try {
        const created = await api.createInvestigation(body)
        setJob(created)
        const url = new URL(window.location.href)
        url.searchParams.set('job', created.id)
        window.history.replaceState({}, '', url.toString())
        timer.current = window.setInterval(() => {
          void pollOnce(created.id).catch((e) => {
            setError(e instanceof Error ? e.message : String(e))
            clearTimer()
            setBusy(false)
          })
        }, POLL_MS)
        await pollOnce(created.id)
    } catch (e) {
      setBusy(false)
      setError(e instanceof Error ? e.message : String(e))
      throw e
    }
  },
  [pollOnce],
)

  const loadDemoGraph = useCallback(async () => {
    try {
      setGraph(await api.getDemoEvidenceGraph())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const loadControlledRepairDemo = useCallback(async () => {
    try {
      setError(null)
      const report = await api.getDemoControlledRepair()
      setDemoRepair(report)
      setShowingControlledRepairExample(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setShowingControlledRepairExample(false)
    }
  }, [])

  const exitControlledRepairExample = useCallback(() => {
    setShowingControlledRepairExample(false)
  }, [])

  const watchExisting = useCallback(
    async (id: string) => {
      clearTimer()
      setError(null)
      setBusy(true)
      setShowingControlledRepairExample(false)
      setEvents(null)
      setResults(null)
      setValidation(null)
      setRepair(null)
      setGraph(null)
      setScreenshots([])
      setHumanReport(null)
      try {
        await pollOnce(id)
        const summary = await api.getInvestigation(id)
        if (!TERMINAL_STATUSES.has(summary.status)) {
          timer.current = window.setInterval(() => {
            void pollOnce(id).catch((e) => {
              setError(e instanceof Error ? e.message : String(e))
              clearTimer()
              setBusy(false)
            })
          }, POLL_MS)
        } else {
          setBusy(false)
        }
      } catch (e) {
        setBusy(false)
        setError(e instanceof Error ? e.message : String(e))
        throw e
      }
    },
    [pollOnce],
  )

  /** Prefer a recorded completed job; otherwise run Guided Demo with reconstruction reuse (no Muse investigation). */
  const openCompletedExample = useCallback(async () => {
    setError(null)
    setShowingControlledRepairExample(false)
    for (const id of COMPLETED_EXAMPLE_CANDIDATES) {
      try {
        const summary = await api.getInvestigation(id)
        if (TERMINAL_STATUSES.has(summary.status)) {
          const url = new URL(window.location.href)
          url.searchParams.set('job', id)
          window.history.replaceState({}, '', url.toString())
          await watchExisting(id)
          return { kind: 'existing' as const, id }
        }
      } catch {
        /* try next candidate */
      }
    }
    try {
      await start({
        target_id: 'taskboard',
        mode: 'scripted',
        pipeline: 'full',
        reuse_reconstruction: true,
        max_actions: 10,
      })
      return { kind: 'launched' as const, id: null }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setError(message)
      throw e
    }
  }, [start, watchExisting])

  useEffect(() => () => clearTimer(), [])

  return {
    job,
    events,
    results,
    validation,
    repair,
    demoRepair,
    showingControlledRepairExample,
    graph,
    screenshots,
    humanReport,
    error,
    busy,
    start,
    loadDemoGraph,
    loadControlledRepairDemo,
    exitControlledRepairExample,
    watchExisting,
    openCompletedExample,
  }
}
