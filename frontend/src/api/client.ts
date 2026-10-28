import type {
  CreateInvestigationRequest,
  EvidenceGraph,
  EventsResponse,
  HealthResponse,
  InvestigationSummary,
  ResultsResponse,
  ScreenshotsResponse,
  ValidationResultsFile,
} from './types'

const DEFAULT_BASE = 'http://127.0.0.1:8000'

export function apiBaseUrl(): string {
  const raw = import.meta.env.VITE_REVERSEX_API_BASE_URL as string | undefined
  return (raw || DEFAULT_BASE).replace(/\/$/, '')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') detail = body.detail
      else if (body?.detail) detail = JSON.stringify(body.detail)
    } catch {
      /* ignore */
    }
    throw new Error(`${response.status}: ${detail}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<HealthResponse>('/health'),
  createInvestigation: (body: CreateInvestigationRequest) =>
    request<InvestigationSummary>('/api/investigations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getInvestigation: (id: string) =>
    request<InvestigationSummary>(`/api/investigations/${id}`),
  getEvents: (id: string) =>
    request<EventsResponse>(`/api/investigations/${id}/events`),
  getResults: (id: string) =>
    request<ResultsResponse>(`/api/investigations/${id}/results`),
  getEvidenceGraph: (id: string) =>
    request<EvidenceGraph>(`/api/investigations/${id}/evidence-graph`),
  getDemoEvidenceGraph: () =>
    request<EvidenceGraph>('/api/demo/evidence-graph'),
  getReport: (id: string) =>
    request<Record<string, unknown>>(`/api/investigations/${id}/report`),
  listScreenshots: (id: string) =>
    request<ScreenshotsResponse>(`/api/investigations/${id}/screenshots`),
  getValidation: (id: string) =>
    request<ValidationResultsFile>(`/api/investigations/${id}/validation`),
  screenshotUrl: (id: string, filename: string) =>
    `${apiBaseUrl()}/api/investigations/${id}/screenshots/${encodeURIComponent(filename)}`,
}

export const TERMINAL_STATUSES = new Set([
  'completed',
  'incomplete',
  'failed',
  'partial', // legacy
])
