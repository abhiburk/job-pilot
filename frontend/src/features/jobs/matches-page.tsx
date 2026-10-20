import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Info, RefreshCw, Sparkles } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState, ErrorState, ListSkeleton, PageHeader, Spinner } from '@/components/common'
import { Button } from '@/components/ui/button'
import { WithCandidate } from '@/hooks/use-candidate'
import { api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import type { Candidate } from '@/lib/types'
import { JobCard } from './job-card'
import { JobFilters, Pagination, useJobFilters } from './job-filters'
import { useRecalculateMatches } from './use-job-mutations'

export function useTrackedJobIds(candidateId: string) {
  const applications = useQuery({
    queryKey: queryKeys.applications.list(candidateId),
    queryFn: () => api.applications.list(candidateId),
  })
  return new Set(applications.data?.map((item) => item.job_id) ?? [])
}

function Matches({ candidate }: { candidate: Candidate }) {
  // min_score=0 limits the list to jobs that have a match score.
  const filterState = useJobFilters({ sort_by: 'match_score', min_score: 0 })
  const params = { ...filterState.filters, candidate_id: candidate.id }
  const recalculate = useRecalculateMatches(candidate.id)
  const tracked = useTrackedJobIds(candidate.id)

  const jobs = useQuery({
    queryKey: queryKeys.jobs.list(params),
    queryFn: () => api.jobs.list(params),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader
        title="Job matches"
        description="Active jobs ranked by JobPilot's rules-based matcher."
        actions={
          <Button variant="outline" disabled={recalculate.isPending} onClick={() => recalculate.mutate()}>
            {recalculate.isPending ? <Spinner /> : <RefreshCw />}
            Recalculate matches
          </Button>
        }
      />

      <p className="mb-4 flex gap-2 rounded-lg border bg-background p-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        <span>
          The match score (0–100) combines role relevance, skills, experience, preferences, and salary using fixed rules. It is not an AI judgement. Data coverage shows how much of that input was available for the job; low coverage means the score is less reliable. AI analysis is a separate, on-demand assessment on each job page.
        </span>
      </p>

      <JobFilters state={filterState} showScore showMatchSort />

      {jobs.isPending ? (
        <ListSkeleton />
      ) : jobs.isError ? (
        <ErrorState title="Could not load matches" error={jobs.error} onRetry={() => jobs.refetch()} />
      ) : jobs.data.items.length === 0 ? (
        <EmptyState
          icon={<Sparkles />}
          title={filterState.hasFilters ? 'No matches for these filters' : 'No scored jobs yet'}
          description={
            filterState.hasFilters
              ? 'Lower the minimum score or clear filters.'
              : 'Discover jobs and recalculate matches to see ranked results.'
          }
          action={
            !filterState.hasFilters && (
              <Button asChild variant="outline">
                <Link to="/discover">Discover jobs</Link>
              </Button>
            )
          }
        />
      ) : (
        <div className={jobs.isPlaceholderData ? 'space-y-3 opacity-60' : 'space-y-3'}>
          <p className="text-sm text-muted-foreground">{jobs.data.pagination.total} scored jobs</p>
          {jobs.data.items.map((job) => (
            <JobCard key={job.id} job={job} showMatch tracked={tracked.has(job.id)} />
          ))}
          <Pagination
            total={jobs.data.pagination.total}
            page={filterState.page}
            onPage={(page) => filterState.update({ page: String(page) })}
          />
        </div>
      )}
    </>
  )
}

export function MatchesPage() {
  return <WithCandidate>{(candidate) => <Matches candidate={candidate} />}</WithCandidate>
}
