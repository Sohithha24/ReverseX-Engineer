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
  authorized_targets?: string[]
  note?: string
}

export type TargetId = 'taskboard' | 'calculator'

export interface AuthorizedTarget {
  id: TargetId
  label: string
  origin: string
  description: string
  validation_suite: string
  reuse_reconstruction_allowed: boolean
}

export interface TargetsResponse {
  targets: AuthorizedTarget[]
}

export interface CreateInvestigationRequest {
  mode: InvestigationMode
  pipeline: Pipeline
  reuse_reconstruction: boolean
  max_actions: number
  /** Authorized fixture; defaults to taskboard on the API. */
  target_id?: TargetId
}

export interface InvestigationSummary {
  id: string
  status: JobStatus | string
  mode?: string | null
  pipeline?: string | null
  target_id?: string | null
  queued_at?: string | null
  updated_at?: string | null
  stages?: Record<string, unknown>
  errors?: string[]
  artifacts?: Record<string, unknown>
  meta_api_requests_total?: number | null
  error?: string | null
}

export interface RepairAttempt {
  attempt: number
  failed_scenarios_addressed: string[]
  meta_api_requests?: number
  changed_files?: string[]
  candidate_dir?: string
  validation_artifact?: string | null
  prior_match_rate_percent?: number | null
  new_match_rate_percent?: number | null
  newly_passed_tests?: string[]
  regressed_tests?: string[]
  remaining_failures?: string[]
  runtime_seconds?: number | null
  status?: string
  error?: string | null
  accepted_as_best?: boolean
}

export interface RepairReport {
  evaluation_kind: 'pipeline_repair' | 'controlled_fault_injection' | string
  label: string
  target_id: string
  max_attempts?: number
  initial_match_rate_percent?: number | null
  final_match_rate_percent?: number | null
  initial_failed?: string[]
  attempts?: RepairAttempt[]
  best_candidate_dir?: string | null
  best_match_rate_percent?: number | null
  meta_api_requests_total?: number
  stopped_reason?: string
  original_fixture_untouched?: boolean
  notes?: string[]
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
  holdout_values?: Record<string, string>
}
