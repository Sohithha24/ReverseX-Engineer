import { useCallback, useEffect, useRef, useState } from 'react'
import { TERMINAL_STATUSES, api } from '../api/client'
import type {
  CreateInvestigationRequest,
  EvidenceGraph,
  EventsResponse,
  InvestigationSummary,
  ResultsResponse,
  RepairReport,
  ScreenshotItem,
  ValidationResultsFile,
} from '../api/types'

const POLL_MS = 1500

export function useInvestigation() {
  const [job, setJob] = useState<InvestigationSummary | null>(null)
  const [events, setEvents] = useState<EventsResponse | null>(null)
  const [results, setResults] = useState<ResultsResponse | null>(null)
  const [validation, setValidation] = useState<ValidationResultsFile | null>(null)
  const [repair, setRepair] = useState<RepairReport | null>(null)
  const [graph, setGraph] = useState<EvidenceGraph | null>(null)
  const [screenshots, setScreenshots] = useState<ScreenshotItem[]>([])
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
    }
  }, [])

  const pollOnce = useCallback(async (id: string) => {
    const summary = await api.getInvestigation(id)
    setJob(summary)
    await refreshExtras(id, summary.status)
    if (TERMINAL_STATUSES.has(summary.status)) {
      clearTimer()
      setBusy(false)
    }
  }, [refreshExtras])

  const start = useCallback(async (body: CreateInvestigationRequest) => {
    clearTimer()
    setError(null)
    setBusy(true)
    setEvents(null)
    setResults(null)
    setValidation(null)
    setRepair(null)
    setGraph(null)
    setScreenshots([])
    try {
      const created = await api.createInvestigation(body)
      setJob(created)
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
    }
  }, [pollOnce])

  const loadDemoGraph = useCallback(async () => {
    try {
      setGraph(await api.getDemoEvidenceGraph())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const loadControlledRepairDemo = useCallback(async () => {
    try {
      setRepair(await api.getDemoControlledRepair())
      try {
        setGraph(await api.getDemoEvidenceGraph())
      } catch {
        /* optional */
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const watchExisting = useCallback(async (id: string) => {
    clearTimer()
    setError(null)
    setBusy(true)
    setEvents(null)
    setResults(null)
    setValidation(null)
    setRepair(null)
    setGraph(null)
    setScreenshots([])
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
    }
  }, [pollOnce])

  useEffect(() => () => clearTimer(), [])

  return {
    job,
    events,
    results,
    validation,
    repair,
    graph,
    screenshots,
    error,
    busy,
    start,
    loadDemoGraph,
    loadControlledRepairDemo,
    watchExisting,
  }
}
