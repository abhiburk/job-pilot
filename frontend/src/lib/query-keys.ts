import type { ApplicationStatus, JobListParams } from './types'

export const queryKeys = {
  session: ['session'] as const,
  candidate: ['candidate', 'me'] as const,
  skills: (candidateId: string) => ['skills', candidateId] as const,
  jobs: {
    all: ['jobs'] as const,
    list: (params: JobListParams) => ['jobs', 'list', params] as const,
    detail: (jobId: string, candidateId?: string) =>
      ['jobs', 'detail', jobId, candidateId ?? null] as const,
    analysis: (jobId: string, candidateId: string) =>
      ['jobs', 'analysis', jobId, candidateId] as const,
  },
  applications: {
    all: ['applications'] as const,
    list: (
      candidateId: string,
      params: { status?: ApplicationStatus; job_id?: string } = {},
    ) => ['applications', 'list', candidateId, params] as const,
    summary: (candidateId: string) =>
      ['applications', 'summary', candidateId] as const,
    detail: (applicationId: string) =>
      ['applications', 'detail', applicationId] as const,
    documents: (applicationId: string) =>
      ['applications', 'documents', applicationId] as const,
  },
  jobSources: ['job-sources'] as const,
  health: ['health'] as const,
}
