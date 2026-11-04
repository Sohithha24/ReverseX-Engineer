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

export type TargetId = string
export type InvestigationGoal = 'understand' | 'understand_and_reconstruct'

export interface AuthorizedTarget {
  id: TargetId
  label: string
  origin: string
  description: string
  validation_suite: string | null
  reuse_reconstruction_allowed: boolean
  kind?: string
  independent_validation_available?: boolean
}

export interface TargetsResponse {
  targets: AuthorizedTarget[]
  authorized_origins?: Array<{
    target_id: string
    label: string
    origin: string
    validation_available?: boolean
    kind?: string
  }>
}

export interface ResolveTargetResponse {
  approved: boolean
  target_id: string
  label: string
  origin: string
  application_url: string
  feature: string
  kind?: string
  independent_validation_available?: boolean
  message?: string
}

export interface CreateInvestigationRequest {
  mode: InvestigationMode
  pipeline: Pipeline
  reuse_reconstruction: boolean
  max_actions: number
  /** Authorized fixture sample id when not using application_url. */
  target_id?: TargetId
  application_url?: string
  feature?: string
  investigation_goal?: InvestigationGoal
}

export interface InvestigationSummary {
  id: string
  status: JobStatus | string
  mode?: string | null
  pipeline?: string | null
  target_id?: string | null
  feature?: string | null
  application_url?: string | null
  investigation_goal?: string | null
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

export type VerificationStatus =
  | 'verified'
  | 'partially_verified'
  | 'not_verified'
  | 'contradicted'
  | 'requires_review'

export interface EvidenceReference {
  ref_id: string
  kind: string
  location: string
  note?: string | null
  available?: boolean
}

export interface VerifiedFinding {
  claim_id: string
  investigation_id: string
  target_application?: string | null
  feature_investigated?: string | null
  claim_category: string
  claim_text: string
  supporting_evidence: EvidenceReference[]
  contradictory_evidence: EvidenceReference[]
  verification_status: VerificationStatus
  verification_scope: string
  limitations: string[]
  related_test_ids: string[]
  timestamps: string[]
  problem_category?: string | null
  rule_id?: string | null
}

export interface VerifiedResults {
  investigation_id: string
  generated_at: string
  availability: 'complete' | 'partial' | 'unavailable'
  target_application?: string | null
  feature_investigated?: string | null
  investigation_mode?: string | null
  pipeline?: string | null
  investigation_status?: string | null
  metadata?: Record<string, unknown>
  verified_findings: VerifiedFinding[]
  partially_verified_findings: VerifiedFinding[]
  unsupported_findings: VerifiedFinding[]
  contradicted_findings: VerifiedFinding[]
  requires_review_findings: VerifiedFinding[]
  contradictions: Array<{
    contradiction_id: string
    description: string
    claim_text: string
    expected: string
    observed: string
    evidence?: EvidenceReference[]
    decidable?: boolean
  }>
  problems: Array<{
    problem_id: string
    category: string
    description: string
    related_test_ids?: string[]
    notes?: string[]
  }>
  untested_behaviors: string[]
  reconstruction_status?: Record<string, unknown> | null
  validation_summary?: {
    passed?: number | null
    failed?: number | null
    invalid?: number | null
    total_valid?: number | null
    behavioral_match_rate_percent?: number | null
    isolation_status?: string | null
  } | null
  repair_summary?: {
    evaluation_kind?: string
    label?: string
    initial_match_rate_percent?: number | null
    final_match_rate_percent?: number | null
    stopped_reason?: string
    attempts?: number
  } | null
  coverage_limitations: string[]
  evidence_index?: EvidenceReference[]
  notes?: string[]
}

export interface TimelineItem {
  step: string
  action: string
  what_reversex_did: string
  what_happened: string
  what_that_shows: string
  recorded_purpose: string
}

export interface FailureExplanation {
  test_id: string
  status: string
  what_we_tested: string
  original_did: string
  reconstruction_did: string
  what_was_different: string
  why_it_matters: string
  repair_attempted?: string
  repair_result?: string
}

export interface HowWeKnowItem {
  title: string
  status: string
  scope: string
  evidence: string
  tests: string
}

export interface HumanReportResponse {
  verified: VerifiedResults
  timeline: TimelineItem[]
  failures: FailureExplanation[]
  how_we_know: HowWeKnowItem[]
  status_labels: Record<string, string>
  status_help: Record<string, string>
  investigation_note?: string | null
  api_request_count?: number | null
  specification_present?: boolean
  requirements?: Array<{
    id?: string
    kind?: string
    observed_result?: string
    action_performed?: string
  }>
}
