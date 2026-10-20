import { useQuery } from '@tanstack/react-query'
import { ArrowRight, CalendarClock, CircleCheck, Compass, FileUp, Sparkles, UserRound } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { ScoreBadge, StatusBadge } from '@/components/badges'
import { EmptyState, ErrorState, PageHeader, Stat } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/auth/auth-context'
import { WithCandidate, useCandidate } from '@/hooks/use-candidate'
import { api } from '@/lib/api'
import { ACTIVE_STATUSES, STATUS_LABELS, formatRelative, isOverdue } from '@/lib/format'
import { queryKeys } from '@/lib/query-keys'
import { APPLICATION_STATUSES } from '@/lib/types'
import type { ApplicationListItem, ApplicationSummary, Candidate, Job } from '@/lib/types'
import { cn } from '@/lib/utils'

// Same default threshold as JOB_DIGEST_MIN_SCORE in the backend settings.
const STRONG_MATCH = 70
const WEEK_MS = 7 * 86_400_000

type NextStep = { icon: ReactNode; text: string; to: string; cta: string }

export function nextSteps(input: {
  candidate: Candidate
  skillsCount: number | undefined
  jobsTotal: number | undefined
  scoredTotal: number | undefined
  summary: ApplicationSummary | undefined
  draftsAwaiting: number
}): NextStep[] {
  const steps: NextStep[] = []
  const { candidate, summary } = input

  if (!candidate.resume_text?.trim()) {
    steps.push({ icon: <FileUp />, text: 'Upload your resume so matching and tailoring have real experience to work with.', to: '/profile', cta: 'Upload resume' })
  }
  if (input.skillsCount === 0) {
    steps.push({ icon: <UserRound />, text: 'Add your core skills to improve match quality.', to: '/profile', cta: 'Add skills' })
  }
  if (input.jobsTotal === 0) {
    steps.push({ icon: <Compass />, text: 'No jobs yet. Run a discovery to fetch listings.', to: '/discover', cta: 'Discover jobs' })
  } else if (input.scoredTotal === 0) {
    steps.push({ icon: <Sparkles />, text: 'Jobs are not scored yet. Recalculate matches.', to: '/matches', cta: 'Open matches' })
  }
  const due = (summary?.follow_ups.overdue ?? 0) + (summary?.follow_ups.due_today ?? 0)
  if (due > 0) {
    steps.push({ icon: <CalendarClock />, text: `${due} follow-up${due === 1 ? '' : 's'} due or overdue.`, to: '/applications', cta: 'Review' })
  }
  if (input.draftsAwaiting > 0) {
    steps.push({ icon: <CircleCheck />, text: `${input.draftsAwaiting} application${input.draftsAwaiting === 1 ? ' is' : 's are'} in “Preparing”. Review and approve their documents.`, to: '/applications?status=preparing', cta: 'Review' })
  }
  return steps
}

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <Card className="gap-3">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function JobLine({ job, tracked }: { job: Job; tracked?: boolean }) {
  return (
    <li>
      <Link to={`/jobs/${job.id}`} className="flex items-center justify-between gap-3 rounded-md px-2 py-2 hover:bg-muted">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{job.title}</p>
          <p className="truncate text-xs text-muted-foreground">
            {[job.company_name, job.location].filter(Boolean).join(' · ') || '—'}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {tracked && <span className="text-xs text-muted-foreground">Tracked</span>}
          <ScoreBadge score={job.match_score} />
        </div>
      </Link>
    </li>
  )
}

function ApplicationLine({ item, detail }: { item: ApplicationListItem; detail: ReactNode }) {
  return (
    <li>
      <Link to={`/applications/${item.id}`} className="flex items-center justify-between gap-3 rounded-md px-2 py-2 hover:bg-muted">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{item.job_title}</p>
          <p className="truncate text-xs text-muted-foreground">{detail}</p>
        </div>
        <StatusBadge status={item.status} />
      </Link>
    </li>
  )
}

function LinesSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-10" />
      <Skeleton className="h-10" />
      <Skeleton className="h-10" />
    </div>
  )
}

function Dashboard({ candidate }: { candidate: Candidate }) {
  const [renderedAt] = useState(() => Date.now())
  const allJobs = useQuery({
    queryKey: queryKeys.jobs.list({ limit: 5, sort_by: 'newest', candidate_id: candidate.id }),
    queryFn: () => api.jobs.list({ limit: 5, sort_by: 'newest', candidate_id: candidate.id }),
  })
  const scored = useQuery({
    queryKey: queryKeys.jobs.list({ limit: 1, min_score: 0, candidate_id: candidate.id }),
    queryFn: () => api.jobs.list({ limit: 1, min_score: 0, candidate_id: candidate.id }),
  })
  const strong = useQuery({
    queryKey: queryKeys.jobs.list({ limit: 15, min_score: STRONG_MATCH, sort_by: 'match_score', candidate_id: candidate.id }),
    queryFn: () => api.jobs.list({ limit: 15, min_score: STRONG_MATCH, sort_by: 'match_score', candidate_id: candidate.id }),
  })
  const summary = useQuery({
    queryKey: queryKeys.applications.summary(candidate.id),
    queryFn: () => api.applications.summary(candidate.id),
  })
  const applications = useQuery({
    queryKey: queryKeys.applications.list(candidate.id),
    queryFn: () => api.applications.list(candidate.id),
  })
  const skills = useQuery({
    queryKey: queryKeys.skills(candidate.id),
    queryFn: () => api.skills.list(candidate.id),
  })

  const trackedIds = new Set(applications.data?.map((item) => item.job_id) ?? [])
  const toReview = (strong.data?.items ?? []).filter((job) => !trackedIds.has(job.id)).slice(0, 5)

  const attention = (applications.data ?? [])
    .filter(
      (item) =>
        item.follow_up_at &&
        ACTIVE_STATUSES.includes(item.status) &&
        new Date(item.follow_up_at).getTime() < renderedAt + WEEK_MS,
    )
    .sort((a, b) => new Date(a.follow_up_at!).getTime() - new Date(b.follow_up_at!).getTime())
    .slice(0, 5)

  const activeCount = summary.data
    ? ACTIVE_STATUSES.reduce((total, status) => total + summary.data.by_status[status], 0)
    : undefined

  const steps = nextSteps({
    candidate,
    skillsCount: skills.data?.length,
    jobsTotal: allJobs.data?.pagination.total,
    scoredTotal: scored.data?.pagination.total,
    summary: summary.data,
    draftsAwaiting: summary.data?.by_status.preparing ?? 0,
  })

  const firstError = [allJobs, strong, summary, applications].find((query) => query.isError)

  return (
    <>
      <PageHeader
        title={`Hi${candidate.full_name ? `, ${candidate.full_name.split(' ')[0]}` : ''}`}
        description="Here is where your job search stands."
        actions={
          <>
            <Button asChild variant="outline"><Link to="/discover"><Compass /> Discover</Link></Button>
            <Button asChild><Link to="/matches"><Sparkles /> Review matches</Link></Button>
          </>
        }
      />

      {firstError && (
        <div className="mb-4">
          <ErrorState title="Some dashboard data could not load" error={firstError.error} onRetry={() => firstError.refetch()} />
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Active jobs" value={allJobs.data?.pagination.total ?? '—'} hint="Across all sources" />
        <Stat label={`Matches scoring ${STRONG_MATCH}+`} value={strong.data?.pagination.total ?? '—'} hint={scored.data ? `of ${scored.data.pagination.total} scored` : undefined} />
        <Stat label="Active applications" value={activeCount ?? '—'} hint={summary.data ? `${summary.data.total} tracked in total` : undefined} />
        <Stat
          label="Follow-ups due"
          value={summary.data ? summary.data.follow_ups.overdue + summary.data.follow_ups.due_today : '—'}
          hint={summary.data ? `${summary.data.follow_ups.overdue} overdue · ${summary.data.follow_ups.upcoming} later` : undefined}
        />
      </div>

      {steps.length > 0 && (
        <Card className="mt-6 gap-3">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Next steps</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {steps.map((step) => (
                <li key={step.text} className="flex items-center gap-3 py-2.5">
                  <span className="text-muted-foreground [&_svg]:size-4">{step.icon}</span>
                  <span className="flex-1 text-sm">{step.text}</span>
                  <Button asChild size="sm" variant="ghost">
                    <Link to={step.to}>{step.cta} <ArrowRight /></Link>
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Section
          title="Strong matches to review"
          action={<Button asChild size="sm" variant="ghost"><Link to={`/matches?min_score=${STRONG_MATCH}`}>All <ArrowRight /></Link></Button>}
        >
          {strong.isPending || applications.isPending ? (
            <LinesSkeleton />
          ) : toReview.length === 0 ? (
            <EmptyState className="py-6" title="Nothing new to review" description={`No untracked jobs score ${STRONG_MATCH}+ right now.`} />
          ) : (
            <ul className="-mx-2">{toReview.map((job) => <JobLine key={job.id} job={job} />)}</ul>
          )}
        </Section>

        <Section
          title="Needs attention"
          action={<Button asChild size="sm" variant="ghost"><Link to="/applications">All <ArrowRight /></Link></Button>}
        >
          {applications.isPending ? (
            <LinesSkeleton />
          ) : attention.length === 0 ? (
            <EmptyState className="py-6" title="No follow-ups this week" description="Set follow-up dates on applications to see reminders here." />
          ) : (
            <ul className="-mx-2">
              {attention.map((item) => (
                <ApplicationLine
                  key={item.id}
                  item={item}
                  detail={
                    <span className={cn(isOverdue(item.follow_up_at) && 'text-destructive')}>
                      Follow up {formatRelative(item.follow_up_at)}
                    </span>
                  }
                />
              ))}
            </ul>
          )}
        </Section>

        <Section
          title="Recently discovered"
          action={<Button asChild size="sm" variant="ghost"><Link to="/discover">All <ArrowRight /></Link></Button>}
        >
          {allJobs.isPending ? (
            <LinesSkeleton />
          ) : allJobs.data?.items.length ? (
            <ul className="-mx-2">
              {allJobs.data.items.map((job) => <JobLine key={job.id} job={job} tracked={trackedIds.has(job.id)} />)}
            </ul>
          ) : (
            <EmptyState className="py-6" title="No jobs yet" action={<Button asChild size="sm" variant="outline"><Link to="/discover">Discover jobs</Link></Button>} />
          )}
        </Section>

        <Section title="Recently updated applications">
          {applications.isPending ? (
            <LinesSkeleton />
          ) : applications.data?.length ? (
            <ul className="-mx-2">
              {applications.data.slice(0, 5).map((item) => (
                <ApplicationLine key={item.id} item={item} detail={`${item.company_name ?? 'Company not listed'} · updated ${formatRelative(item.updated_at)}`} />
              ))}
            </ul>
          ) : (
            <EmptyState className="py-6" title="No applications yet" description="Track a job from its page to start." />
          )}
        </Section>
      </div>

      {summary.data && summary.data.total > 0 && (
        <Card className="mt-4 gap-3">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-wrap gap-2">
              {APPLICATION_STATUSES.map((status) => (
                <li key={status}>
                  <Link
                    to={`/applications?status=${status}`}
                    className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                  >
                    {STATUS_LABELS[status]}
                    <span className="font-semibold tabular-nums">{summary.data.by_status[status]}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const candidate = useCandidate()

  if (candidate.isSuccess && !candidate.data) {
    return (
      <>
        <PageHeader
          title={`Welcome${user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}`}
          description="Set up your profile to start matching jobs."
        />
        <WithCandidate>{() => null}</WithCandidate>
      </>
    )
  }

  return <WithCandidate>{(profile) => <Dashboard candidate={profile} />}</WithCandidate>
}
