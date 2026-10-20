import { ExternalLink } from 'lucide-react'
import { Link } from 'react-router'

import { ScoreBadge } from '@/components/badges'
import { Badge } from '@/components/ui/badge'
import { useSourceLabel } from '@/hooks/use-job-sources'
import { formatDate, formatSalary, workModeLabel } from '@/lib/format'
import type { Job } from '@/lib/types'

export function JobMeta({ job }: { job: Job }) {
  const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency)
  const items = [
    job.location,
    workModeLabel(job.remote_type),
    job.employment_type,
    job.experience_level,
    salary,
  ].filter(Boolean)

  return (
    <p className="text-sm text-muted-foreground">
      {items.length ? items.join(' · ') : 'No location or type listed'}
    </p>
  )
}

export function JobCard({
  job,
  showMatch = false,
  tracked = false,
}: {
  job: Job
  showMatch?: boolean
  tracked?: boolean
}) {
  const sourceLabel = useSourceLabel()
  return (
    <article className="group relative rounded-lg border bg-card p-4 transition-colors hover:border-foreground/20">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h3 className="font-medium leading-snug">
            <Link
              to={`/jobs/${job.id}`}
              className="after:absolute after:inset-0 focus-visible:outline-none group-focus-within:underline"
            >
              {job.title}
            </Link>
          </h3>
          <p className="text-sm">{job.company_name ?? 'Company not listed'}</p>
          <JobMeta job={job} />
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:flex-col sm:items-end">
          {showMatch && <ScoreBadge score={job.match_score} />}
          {tracked && <Badge variant="secondary">Tracked</Badge>}
        </div>
      </div>

      {showMatch && job.match_score !== null && (
        <div className="mt-3 space-y-2">
          {job.explanation && (
            <p className="line-clamp-2 text-sm text-muted-foreground">{job.explanation}</p>
          )}
          {(job.strengths.length > 0 || job.gaps.length > 0) && (
            <div className="flex flex-wrap gap-1.5">
              {job.strengths.slice(0, 3).map((item) => (
                <Badge key={`s-${item}`} variant="outline" className="border-emerald-200 bg-emerald-50/60 font-normal text-emerald-900">
                  {item}
                </Badge>
              ))}
              {job.gaps.slice(0, 2).map((item) => (
                <Badge key={`g-${item}`} variant="outline" className="border-rose-200 bg-rose-50/60 font-normal text-rose-900">
                  {item}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>Posted {formatDate(job.posted_at ?? job.discovered_at)}</span>
        {showMatch && job.score_coverage !== null && (
          <span title="Share of the score's inputs that had data for this job">
            {Math.round(job.score_coverage)}% data coverage
          </span>
        )}
        <a
          href={job.job_url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="relative z-10 ml-auto inline-flex items-center gap-1 hover:text-foreground"
        >
          View on {sourceLabel(job.source)} <ExternalLink className="size-3" />
        </a>
      </div>
    </article>
  )
}
