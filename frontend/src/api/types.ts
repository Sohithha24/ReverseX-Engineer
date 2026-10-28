/** Types aligned with docs/FRONTEND_API_CONTRACT.md and reversex/api.py */

export type InvestigationMode = 'scripted' | 'muse'
export type Pipeline = 'investigate_only' | 'full'

export type JobStatus =
  | 'queued'
  | 'investigating'
  | 'specifying'
  | 'reconstructing'
  | 'validating'
  | 'completed'
  | 'incomplete'
  | 'failed'

export interface HealthResponse {
  status: string
  phase: string
  reconstruction_available: boolean
  validation_available?: boolean
  docker_required_for_validation_preview?: boolean
  public?: boolean
  note?: string
}

export interface CreateInvestigationRequest {
  mode: InvestigationMode
  pipeline: Pipeline
  reuse_reconstruction: boolean
  max_actions: number
}

export interface InvestigationSummary {
  id: string
  status: JobStatus | string
  mode?: string | null
  pipeline?: string | null
  queued_at?: string | null
  updated_at?: string | null
  stages?: Record<string, unknown>
  errors?: string[]
  artifacts?: Record<string, unknown>
  meta_api_requests_total?: number | null
  error?: string | null
}

export interface EventsResponse {
  id: string
  status?: string
  investigation_status?: string
  events: Array<Record<string, unknown>>
  objectives?: Record<string, unknown>
  note?: string
}

export interface ResultsResponse {
  id: string
  status?: string
  stages?: Record<string, unknown>
  errors?: string[]
  specification_present?: boolean
  validation?: {
    present: boolean
    passed?: number | null
    failed?: number | null
    invalid?: number | null
    total_valid?: number | null
    behavioral_match_rate_percent?: number | null
    isolation_status?: string | null
  }
  reconstruction_reused_or_generated?: unknown
}

export interface EvidenceNode {
  id: string
  type: string
  description: string
  evidence_ref?: string | null
  status?: string
  timestamp?: string | null
  metadata?: Record<string, unknown>
}

export interface EvidenceEdge {
  id: string
  type: string
  source: string
  target: string
  description: string
}

export interface EvidenceGraph {
  project: string
  version: string
  generated_at: string
  source_artifacts: string[]
  nodes: EvidenceNode[]
  edges: EvidenceEdge[]
}

export interface ScreenshotItem {
  id: string
  filename: string
  relative_path: string
  url: string
}

export interface ScreenshotsResponse {
  id: string
  screenshots: ScreenshotItem[]
}

export interface ValidationTestCase {
  test_id: string
  description?: string
  input_values?: Record<string, string | null>
  status: string
  differences?: string[]
  original?: {
    observed_state?: Record<string, unknown>
    screenshot?: string | null
    error?: string | null
  }
  reconstruction?: {
    observed_state?: Record<string, unknown>
    screenshot?: string | null
    error?: string | null
  }
  error?: string | null
}

export interface ValidationResultsFile {
  passed?: number
  failed?: number
  invalid?: number
  total_valid?: number
  behavioral_match_rate_percent?: number | null
  tests?: ValidationTestCase[]
  isolation?: Record<string, unknown>
}
