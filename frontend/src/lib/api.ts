import type {
  Application,
  ApplicationDocument,
  ApplicationListItem,
  ApplicationStatus,
  ApplicationSummary,
  ApplicationUpdate,
  Candidate,
  CandidateInput,
  CandidateSkill,
  CandidateSkillInput,
  CandidateSkillUpdate,
  CoverLetterResponse,
  DiscoveryRequest,
  DiscoveryResponse,
  JobAnalysis,
  JobDetail,
  JobListParams,
  JobListResponse,
  JobSourceInfo,
  MatchRunResult,
  ResumeUploadResult,
  SessionResponse,
  TailorResumeResponse,
  User,
} from './types'

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly fieldErrors: Record<string, string>
  readonly retryAfter: number | null

  constructor(
    status: number,
    message: string,
    fieldErrors: Record<string, string> = {},
    retryAfter: number | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
    this.retryAfter = retryAfter
  }

  get isNetworkError() {
    return this.status === 0
  }
}

// The CSRF token is held only in memory. It is re-issued by /api/auth/me
// after a reload; it never touches localStorage.
let csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

type UnauthorizedListener = (error: ApiError) => void
const unauthorizedListeners = new Set<UnauthorizedListener>()

/** Notified when a request made with a session gets a 401. */
export function onUnauthorized(listener: UnauthorizedListener) {
  unauthorizedListeners.add(listener)
  return () => {
    unauthorizedListeners.delete(listener)
  }
}

type Query = Record<string, string | number | boolean | null | undefined>

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  query?: Query
  json?: unknown
  form?: FormData
  signal?: AbortSignal
  /** Auth endpoints report 401 as bad credentials, not as an expired session. */
  skipUnauthorizedEvent?: boolean
}

export function buildUrl(path: string, query?: Query) {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value))
      }
    }
  }
  return url.toString()
}

type ValidationIssue = { loc?: (string | number)[]; msg?: string }

function parseErrorBody(body: unknown): {
  message: string
  fieldErrors: Record<string, string>
} {
  const fieldErrors: Record<string, string> = {}

  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail

    if (typeof detail === 'string') {
      return { message: detail, fieldErrors }
    }

    if (Array.isArray(detail)) {
      const messages: string[] = []
      for (const issue of detail as ValidationIssue[]) {
        const field = issue.loc?.filter((part) => part !== 'body').join('.')
        const msg = (issue.msg ?? 'Invalid value').replace(/^Value error, /, '')
        if (field) fieldErrors[field] = msg
        messages.push(field ? `${field}: ${msg}` : msg)
      }
      return {
        message: messages.join('; ') || 'The request was not valid.',
        fieldErrors,
      }
    }
  }

  return { message: '', fieldErrors }
}

function fallbackMessage(status: number) {
  if (status === 429) return 'Too many requests. Please wait and try again.'
  if (status === 502 || status === 503)
    return 'A required service is temporarily unavailable. Please try again.'
  if (status >= 500) return 'The server ran into an error. Please try again.'
  if (status === 404) return 'Not found.'
  if (status === 403) return 'You are not allowed to do that.'
  return `Request failed (${status}).`
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined

  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  } else if (options.form) {
    body = options.form
  }

  if (method !== 'GET' && csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body,
      credentials: 'include',
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(
      0,
      `Cannot reach the JobPilot API at ${API_BASE_URL}. Check that the backend is running.`,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  let payload: unknown = null
  const text = await response.text()
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const { message, fieldErrors } = parseErrorBody(payload)
    const retryAfterHeader = response.headers.get('Retry-After')
    const error = new ApiError(
      response.status,
      message || fallbackMessage(response.status),
      fieldErrors,
      retryAfterHeader ? Number(retryAfterHeader) : null,
    )

    if (response.status === 401 && !options.skipUnauthorizedEvent) {
      unauthorizedListeners.forEach((listener) => listener(error))
    }
    throw error
  }

  return payload as T
}

export const api = {
  auth: {
    me: () =>
      request<SessionResponse>('/api/auth/me', { skipUnauthorizedEvent: true }),
    login: (email: string, password: string) =>
      request<SessionResponse>('/api/auth/login', {
        method: 'POST',
        json: { email, password },
        skipUnauthorizedEvent: true,
      }),
    register: (input: { email: string; password: string; full_name?: string }) =>
      request<SessionResponse>('/api/auth/register', {
        method: 'POST',
        json: input,
        skipUnauthorizedEvent: true,
      }),
    logout: () =>
      request<void>('/api/auth/logout', {
        method: 'POST',
        skipUnauthorizedEvent: true,
      }),
    updateAccount: (input: {
      full_name?: string | null
      email?: string
      current_password?: string
    }) => request<User>('/api/auth/me', { method: 'PATCH', json: input }),
    changePassword: (current_password: string, new_password: string) =>
      request<void>('/api/auth/password', {
        method: 'POST',
        json: { current_password, new_password },
      }),
    requestPasswordReset: (email: string) =>
      request<{ message: string }>('/api/auth/password-reset/request', {
        method: 'POST',
        json: { email },
        skipUnauthorizedEvent: true,
      }),
    confirmPasswordReset: (token: string, new_password: string) =>
      request<void>('/api/auth/password-reset/confirm', {
        method: 'POST',
        json: { token, new_password },
        skipUnauthorizedEvent: true,
      }),
  },

  health: {
    api: () => request<{ status: string }>('/health'),
    database: () => request<{ status: string; database: string }>('/health/db'),
  },

  candidates: {
    me: () => request<Candidate>('/api/candidates/me'),
    create: (input: CandidateInput) =>
      request<Candidate>('/api/candidates', { method: 'POST', json: input }),
    update: (candidateId: string, input: Partial<CandidateInput>) =>
      request<Candidate>(`/api/candidates/${candidateId}`, {
        method: 'PATCH',
        json: input,
      }),
    uploadResume: (candidateId: string, file: File) => {
      const form = new FormData()
      form.append('file', file)
      return request<ResumeUploadResult>(
        `/api/candidates/${candidateId}/resume/upload`,
        { method: 'POST', form },
      )
    },
  },

  skills: {
    list: (candidateId: string) =>
      request<CandidateSkill[]>(`/api/candidates/${candidateId}/skills`),
    add: (candidateId: string, input: CandidateSkillInput) =>
      request<CandidateSkill>(`/api/candidates/${candidateId}/skills`, {
        method: 'POST',
        json: input,
      }),
    update: (candidateId: string, skillId: string, input: CandidateSkillUpdate) =>
      request<CandidateSkill>(
        `/api/candidates/${candidateId}/skills/${skillId}`,
        { method: 'PATCH', json: input },
      ),
    remove: (candidateId: string, skillId: string) =>
      request<void>(`/api/candidates/${candidateId}/skills/${skillId}`, {
        method: 'DELETE',
      }),
  },

  jobs: {
    list: (params: JobListParams) =>
      request<JobListResponse>('/api/jobs', { query: params }),
    get: (jobId: string, candidateId?: string) =>
      request<JobDetail>(`/api/jobs/${jobId}`, {
        query: { candidate_id: candidateId },
      }),
    sources: () => request<JobSourceInfo[]>('/api/jobs/sources'),
    discover: (input: DiscoveryRequest) =>
      request<DiscoveryResponse>('/api/jobs/discovery', {
        method: 'POST',
        json: input,
      }),
    runMatching: (candidateId: string) =>
      request<MatchRunResult>(`/api/jobs/match/${candidateId}`, {
        method: 'POST',
      }),
    getAnalysis: (jobId: string, candidateId: string) =>
      request<{ analysis: JobAnalysis | null }>(
        `/api/jobs/${jobId}/analysis/${candidateId}`,
      ),
    analyze: (jobId: string, candidateId: string, force = false) =>
      request<{ cached: boolean; analysis: JobAnalysis }>(
        `/api/jobs/${jobId}/analyze/${candidateId}`,
        { method: 'POST', query: { force: force || undefined } },
      ),
  },

  applications: {
    list: (
      candidateId: string,
      params: { status?: ApplicationStatus; job_id?: string; limit?: number; offset?: number } = {},
    ) =>
      request<ApplicationListItem[]>(
        `/api/applications/candidate/${candidateId}`,
        { query: { limit: 100, ...params } },
      ),
    summary: (candidateId: string) =>
      request<ApplicationSummary>(
        `/api/applications/candidate/${candidateId}/summary`,
      ),
    get: (applicationId: string, candidateId: string) =>
      request<ApplicationListItem>(`/api/applications/${applicationId}`, {
        query: { candidate_id: candidateId },
      }),
    create: (input: { candidate_id: string; job_id: string; notes?: string }) =>
      request<Application>('/api/applications', { method: 'POST', json: input }),
    update: (applicationId: string, candidateId: string, input: ApplicationUpdate) =>
      request<Application>(`/api/applications/${applicationId}`, {
        method: 'PATCH',
        query: { candidate_id: candidateId },
        json: input,
      }),
    remove: (applicationId: string, candidateId: string) =>
      request<void>(`/api/applications/${applicationId}`, {
        method: 'DELETE',
        query: { candidate_id: candidateId },
      }),
    documents: (applicationId: string, candidateId: string) =>
      request<ApplicationDocument[]>(
        `/api/applications/${applicationId}/documents`,
        { query: { candidate_id: candidateId } },
      ),
    approveDocument: (applicationId: string, documentId: string, candidateId: string) =>
      request<ApplicationDocument>(
        `/api/applications/${applicationId}/documents/${documentId}/approve`,
        { method: 'PATCH', query: { candidate_id: candidateId } },
      ),
    generateCoverLetter: (candidateId: string, jobId: string) =>
      request<CoverLetterResponse>('/api/applications/generate-cover-letter', {
        method: 'POST',
        json: { candidate_id: candidateId, job_id: jobId },
      }),
    tailorResume: (candidateId: string, jobId: string) =>
      request<TailorResumeResponse>('/api/applications/tailor-resume', {
        method: 'POST',
        json: { candidate_id: candidateId, job_id: jobId },
      }),
  },
}
