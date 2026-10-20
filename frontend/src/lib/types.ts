// Mirrors the FastAPI response shapes in backend/app/schemas and
// backend/app/api/routes. Numeric Decimal fields arrive as strings from
// Pydantic models and as numbers from the hand-built dict responses.

export type User = {
  id: string
  email: string
  full_name: string | null
  created_at: string
}

export type SessionResponse = {
  user: User
  csrf_token: string
  expires_at: string
}

export type Candidate = {
  id: string
  full_name: string
  email: string
  phone: string | null
  headline: string | null
  summary: string | null
  location: string | null
  preferred_locations: string[] | null
  preferred_job_titles: string[] | null
  preferred_employment_types: string[] | null
  preferred_work_modes: string[] | null
  years_experience: string | number | null
  minimum_salary: string | number | null
  salary_currency: string
  remote_only: boolean
  is_active: boolean
  resume_text: string | null
  linkedin_url: string | null
  github_url: string | null
  portfolio_url: string | null
  created_at: string
  updated_at: string
}

export type CandidateInput = {
  full_name: string
  email: string
  phone?: string | null
  headline?: string | null
  summary?: string | null
  location?: string | null
  preferred_locations?: string[] | null
  preferred_job_titles?: string[] | null
  preferred_employment_types?: string[] | null
  preferred_work_modes?: string[] | null
  years_experience?: number | null
  minimum_salary?: number | null
  salary_currency?: string
  remote_only?: boolean
  resume_text?: string | null
  linkedin_url?: string | null
  github_url?: string | null
  portfolio_url?: string | null
}

export type CandidateSkill = {
  id: string
  skill_id: string
  name: string
  category: string | null
  proficiency: string | null
  years_experience: string | number | null
  is_primary: boolean
}

export type CandidateSkillInput = {
  name: string
  category?: string | null
  proficiency?: string | null
  years_experience?: number | null
  is_primary?: boolean
}

export type CandidateSkillUpdate = {
  proficiency?: string | null
  years_experience?: number | null
  is_primary?: boolean
}

export type ResumeUploadResult = {
  message: string
  candidate_id: string
  characters_extracted: number
  skills_found: number
  skills_added: number
  skills: unknown[]
  jobs_processed: number
  model_version: string
}

export type MatchBreakdown = {
  skills: number | null
  experience: number | null
  preferences: number | null
  role_relevance: number | null
  salary: number | null
}

export type RemoteType = 'remote' | 'hybrid' | 'onsite'

export type Job = {
  id: string
  title: string
  company_id: string | null
  company_name: string | null
  description: string | null
  location: string | null
  remote_type: string | null
  employment_type: string | null
  experience_level: string | null
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
  job_url: string
  source: string
  is_active: boolean
  posted_at: string | null
  discovered_at: string
  match_score: number | null
  score_coverage: number | null
  match_breakdown: MatchBreakdown
  strengths: string[]
  gaps: string[]
  explanation: string | null
}

export type JobDetail = Job & {
  confidence_score: number | null
}

export type JobSort = 'newest' | 'match_score' | 'salary_high' | 'salary_low'

export type JobListParams = {
  q?: string
  candidate_id?: string
  location?: string
  remote_type?: RemoteType
  employment_type?: string
  source?: string
  min_score?: number
  sort_by?: JobSort
  limit?: number
  offset?: number
}

export type JobListResponse = {
  items: Job[]
  pagination: {
    total: number
    limit: number
    offset: number
    has_more: boolean
  }
}

export type DiscoveryFilter = 'keywords' | 'country' | 'work_mode'

export type JobSourceInfo = {
  key: string
  label: string
  description: string
  homepage: string
  supported_filters: DiscoveryFilter[]
  remote_only: boolean
  max_limit: number
  min_interval_minutes: number | null
  enabled: boolean
  next_available_at: string | null
  last_run: {
    status: 'running' | 'succeeded' | 'failed'
    started_at: string
    finished_at: string | null
    created: number | null
  } | null
}

export type DiscoveryRequest = {
  keywords?: string
  country?: string
  work_mode?: RemoteType
  limit: number
  sources?: string[]
}

export type DiscoverySourceResult = {
  source: string
  label: string
  status: 'succeeded' | 'failed' | 'skipped'
  fetched: number
  created: number
  skipped: number
  message: string | null
  ignored_filters: DiscoveryFilter[]
  next_available_at: string | null
}

export type DiscoveryResponse = {
  results: DiscoverySourceResult[]
  totals: {
    fetched: number
    created: number
    skipped: number
    succeeded: number
    failed: number
  }
}

export type MatchRunResult = {
  candidate_id: string
  jobs_processed: number
  model_version: string
}

export type AnalysisRecommendation = 'strong_fit' | 'possible_fit' | 'poor_fit'

export type JobAnalysis = {
  id: string
  candidate_id: string
  job_id: string
  status: 'pending' | 'completed' | 'failed'
  fit_score: number | null
  recommendation: AnalysisRecommendation | null
  summary: string | null
  strengths: string[]
  missing_requirements: string[]
  evidence_gaps: string[]
  concerns: string[]
  model_version: string | null
  analyzed_at: string | null
  error_message?: string | null
}

export const APPLICATION_STATUSES = [
  'saved',
  'preparing',
  'applied',
  'interviewing',
  'offer',
  'rejected',
  'withdrawn',
] as const

export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number]

export type Application = {
  id: string
  candidate_id: string
  job_id: string
  status: ApplicationStatus
  application_url: string | null
  applied_at: string | null
  follow_up_at: string | null
  notes: string | null
  submission_metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type ApplicationListItem = Application & {
  job_title: string
  company_name: string | null
  job_location: string | null
  job_url: string
  job_source: string
}

export type ApplicationUpdate = {
  status?: ApplicationStatus
  application_url?: string | null
  applied_at?: string | null
  follow_up_at?: string | null
  notes?: string | null
}

export type ApplicationSummary = {
  candidate_id: string
  total: number
  by_status: Record<ApplicationStatus, number>
  follow_ups: {
    overdue: number
    due_today: number
    upcoming: number
  }
}

export type DocumentType = 'tailored_resume' | 'cover_letter'

export type ApplicationDocument = {
  id: string
  application_id: string
  document_type: DocumentType | string
  version: number
  content_text: string | null
  generation_metadata: {
    model?: string
    generated_at?: string
    changes_summary?: string[]
    warnings?: string[]
    [key: string]: unknown
  } | null
  is_approved: boolean
  approved_at: string | null
  created_at: string
}

export type CoverLetterResponse = {
  candidate_id: string
  job_id: string
  model: string
  cover_letter: string
}

export type TailorResumeResponse = {
  candidate_id: string
  job_id: string
  application_id: string
  document: Omit<ApplicationDocument, 'application_id'>
}
