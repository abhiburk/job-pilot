import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Bot, Briefcase, ExternalLink, Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useParams } from 'react-router'
import { toast } from 'sonner'

import { ScoreBadge, StatusBadge } from '@/components/badges'
import { ErrorState, ListSkeleton, Spinner } from '@/components/common'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DocumentsPanel } from '@/features/applications/documents'
import { useCandidate } from '@/hooks/use-candidate'
import { useSourceLabel } from '@/hooks/use-job-sources'
import { ApiError, api } from '@/lib/api'
import { formatDate, formatDateTime } from '@/lib/format'
import { htmlToText } from '@/lib/html-to-text'
import { queryKeys } from '@/lib/query-keys'
import type { Candidate, JobAnalysis, JobDetail } from '@/lib/types'
import { JobMeta } from './job-card'

const BREAKDOWN_LABELS: Record<string, string> = {
  role_relevance: 'Role relevance',
  skills: 'Skills',
  experience: 'Experience',
  preferences: 'Preferences',
  salary: 'Salary',
}

function MatchCard({ job }: { job: JobDetail }) {
  if (job.match_score === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Match score</CardTitle>
          <CardDescription>Not scored yet. Recalculate matches on the Matches page.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          Match score <ScoreBadge score={job.match_score} />
        </CardTitle>
        <CardDescription>Rules-based score; not AI-generated.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <dl className="space-y-2">
          {Object.entries(job.match_breakdown).map(([key, value]) => (
            <div key={key} className="flex items-center gap-3">
              <dt className="w-28 shrink-0 text-muted-foreground">{BREAKDOWN_LABELS[key] ?? key}</dt>
              <dd className="flex flex-1 items-center gap-2">
                {value === null ? (
                  <span className="text-xs text-muted-foreground">No data</span>
                ) : (
                  <>
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <span className="block h-full rounded-full bg-foreground/70" style={{ width: `${Math.min(100, value)}%` }} />
                    </span>
                    <span className="w-8 text-right tabular-nums">{Math.round(value)}</span>
                  </>
                )}
              </dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {job.score_coverage !== null && <span>Data coverage {Math.round(job.score_coverage)}%</span>}
          {job.confidence_score !== null && (
            <span title="How complete the job and resume data are; not a probability of fit">
              Data completeness {Math.round(job.confidence_score)}%
            </span>
          )}
        </div>
        {job.explanation && <p className="text-muted-foreground">{job.explanation}</p>}
        {job.strengths.length > 0 && (
          <div>
            <p className="mb-1 font-medium">Strengths</p>
            <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">
              {job.strengths.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        )}
        {job.gaps.length > 0 && (
          <div>
            <p className="mb-1 font-medium">Gaps</p>
            <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">
              {job.gaps.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

const RECOMMENDATION_LABELS: Record<string, string> = {
  strong_fit: 'Strong fit',
  possible_fit: 'Possible fit',
  poor_fit: 'Poor fit',
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div>
      <p className="mb-1 font-medium">{title}</p>
      <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  )
}

function AnalysisCard({ jobId, candidate }: { jobId: string; candidate: Candidate }) {
  const queryClient = useQueryClient()
  const key = queryKeys.jobs.analysis(jobId, candidate.id)
  const stored = useQuery({
    queryKey: key,
    queryFn: () => api.jobs.getAnalysis(jobId, candidate.id),
  })

  const run = useMutation({
    mutationFn: (force: boolean) => api.jobs.analyze(jobId, candidate.id, force),
    onSuccess: (data) => {
      queryClient.setQueryData(key, { analysis: data.analysis })
      toast.success(data.cached ? 'Inputs unchanged — showing saved analysis' : 'Analysis complete')
    },
    onError: (error) => {
      void queryClient.invalidateQueries({ queryKey: key })
      toast.error('Analysis failed', { description: error.message })
    },
  })

  const analysis: JobAnalysis | null = stored.data?.analysis ?? null
  const completed = analysis?.status === 'completed'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Bot className="size-4" /> AI analysis
        </CardTitle>
        <CardDescription>
          Generated on request by the AI provider. It can be wrong; treat it as a second opinion.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {stored.isPending ? (
          <ListSkeleton rows={1} />
        ) : stored.isError ? (
          <ErrorState title="Could not load analysis" error={stored.error} onRetry={() => stored.refetch()} />
        ) : completed && analysis ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="tabular-nums">AI fit {analysis.fit_score}/100</Badge>
              {analysis.recommendation && (
                <Badge variant="secondary">{RECOMMENDATION_LABELS[analysis.recommendation] ?? analysis.recommendation}</Badge>
              )}
              <span className="text-xs text-muted-foreground">{formatDateTime(analysis.analyzed_at)}</span>
            </div>
            {analysis.summary && <p>{analysis.summary}</p>}
            <AnalysisList title="Strengths" items={analysis.strengths} />
            <AnalysisList title="Missing requirements" items={analysis.missing_requirements} />
            <AnalysisList title="Could not verify" items={analysis.evidence_gaps} />
            <AnalysisList title="Concerns" items={analysis.concerns} />
          </>
        ) : analysis?.status === 'failed' ? (
          <p className="text-destructive">{analysis.error_message ?? 'The last analysis attempt failed.'}</p>
        ) : (
          <p className="text-muted-foreground">No analysis yet for this job.</p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={completed ? 'outline' : 'default'}
            disabled={run.isPending || stored.isPending}
            onClick={() => run.mutate(false)}
          >
            {run.isPending && <Spinner />}
            {run.isPending ? 'Analyzing…' : completed ? 'Refresh if inputs changed' : 'Analyze with AI'}
          </Button>
          {completed && (
            <Button size="sm" variant="ghost" disabled={run.isPending} onClick={() => run.mutate(true)}>
              Force re-run
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function ApplicationCard({ job, candidate, applicationId, status }: {
  job: JobDetail
  candidate: Candidate
  applicationId?: string
  status?: Parameters<typeof StatusBadge>[0]['status']
}) {
  const queryClient = useQueryClient()
  const track = useMutation({
    mutationFn: () => api.applications.create({ candidate_id: candidate.id, job_id: job.id }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.applications.all })
      toast.success('Saved to applications')
    },
    onError: (error) => toast.error('Could not track this job', { description: error.message }),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Briefcase className="size-4" /> Application
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {applicationId && status ? (
          <>
            <div className="flex items-center gap-2">
              <StatusBadge status={status} />
            </div>
            <Button asChild size="sm" variant="outline">
              <Link to={`/applications/${applicationId}`}>Open application</Link>
            </Button>
          </>
        ) : (
          <>
            <p className="text-muted-foreground">Not tracked yet. Save it to set a status, follow-up, and notes.</p>
            <Button size="sm" disabled={track.isPending} onClick={() => track.mutate()}>
              {track.isPending ? <Spinner /> : <Plus />} Track this job
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function JobDetailContent({ jobId, candidate }: { jobId: string; candidate: Candidate | null }) {
  const job = useQuery({
    queryKey: queryKeys.jobs.detail(jobId, candidate?.id),
    queryFn: () => api.jobs.get(jobId, candidate?.id),
  })

  const applications = useQuery({
    queryKey: queryKeys.applications.list(candidate?.id ?? 'none', { job_id: jobId }),
    queryFn: () => api.applications.list(candidate!.id, { job_id: jobId }),
    enabled: !!candidate,
  })
  const application = applications.data?.[0]

  const description = useMemo(() => htmlToText(job.data?.description), [job.data?.description])
  const sourceLabel = useSourceLabel()

  if (job.isPending) return <ListSkeleton rows={4} />
  if (job.isError) {
    const notFound = job.error instanceof ApiError && job.error.status === 404
    return (
      <ErrorState
        title={notFound ? 'Job not found' : 'Could not load this job'}
        error={job.error}
        onRetry={notFound ? undefined : () => job.refetch()}
      />
    )
  }

  const data = job.data

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-w-0 space-y-6">
        <div className="space-y-2">
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{data.title}</h1>
          <p>{data.company_name ?? 'Company not listed'}</p>
          <JobMeta job={data} />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>Source: {sourceLabel(data.source)}</span>
            <span>Posted {formatDate(data.posted_at)}</span>
            <span>Discovered {formatDate(data.discovered_at)}</span>
          </div>
          <Button asChild variant="outline" size="sm" className="mt-1">
            <a href={data.job_url} target="_blank" rel="noopener noreferrer nofollow">
              View on {sourceLabel(data.source)} <ExternalLink />
            </a>
          </Button>
        </div>

        {!data.is_active && (
          <Alert>
            <AlertTriangle />
            <AlertTitle>This job is no longer active</AlertTitle>
            <AlertDescription>Documents cannot be generated for inactive jobs.</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Job description</CardTitle>
            <CardDescription>As provided by the source. Verify details on the original listing.</CardDescription>
          </CardHeader>
          <CardContent>
            {description ? (
              <div className="text-sm leading-relaxed whitespace-pre-wrap">{description}</div>
            ) : (
              <p className="text-sm text-muted-foreground">The source did not include a description.</p>
            )}
          </CardContent>
        </Card>

        {candidate && (
          <DocumentsPanel applicationId={application?.id} candidate={candidate} job={data} />
        )}
      </div>

      <div className="space-y-4">
        {candidate ? (
          <>
            <ApplicationCard
              job={data}
              candidate={candidate}
              applicationId={application?.id}
              status={application?.status}
            />
            <MatchCard job={data} />
            <AnalysisCard jobId={data.id} candidate={candidate} />
          </>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Personalize this job</CardTitle>
              <CardDescription>Create your profile to see match details, AI analysis, and generate documents.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild size="sm"><Link to="/profile">Create profile</Link></Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

export function JobDetailPage() {
  const { jobId = '' } = useParams()
  const candidate = useCandidate()

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-2">
        <Link to="/matches"><ArrowLeft /> Back to matches</Link>
      </Button>
      {candidate.isPending ? (
        <ListSkeleton rows={4} />
      ) : candidate.isError ? (
        <ErrorState error={candidate.error} onRetry={() => candidate.refetch()} />
      ) : (
        <JobDetailContent jobId={jobId} candidate={candidate.data} />
      )}
    </>
  )
}
