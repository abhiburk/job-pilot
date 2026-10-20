import { useQuery } from '@tanstack/react-query'
import { Briefcase, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { StatusBadge } from '@/components/badges'
import { EmptyState, ErrorState, ListSkeleton, PageHeader } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { WithCandidate } from '@/hooks/use-candidate'
import { api } from '@/lib/api'
import { ACTIVE_STATUSES, STATUS_LABELS, formatDate, formatRelative, isOverdue } from '@/lib/format'
import { queryKeys } from '@/lib/query-keys'
import { APPLICATION_STATUSES } from '@/lib/types'
import type { ApplicationListItem, ApplicationStatus, Candidate } from '@/lib/types'
import { cn } from '@/lib/utils'

const ALL = 'all'

export function filterApplications(items: ApplicationListItem[], search: string) {
  const term = search.trim().toLowerCase()
  if (!term) return items
  return items.filter((item) =>
    [item.job_title, item.company_name, item.job_location, item.notes]
      .filter(Boolean)
      .some((value) => (value as string).toLowerCase().includes(term)),
  )
}

function FollowUp({ item }: { item: ApplicationListItem }) {
  if (!item.follow_up_at) return <span className="text-muted-foreground">—</span>
  const overdue = isOverdue(item.follow_up_at) && ACTIVE_STATUSES.includes(item.status)
  return (
    <span className={cn(overdue && 'font-medium text-destructive')} title={formatDate(item.follow_up_at)}>
      {overdue ? 'Overdue · ' : ''}
      {formatRelative(item.follow_up_at)}
    </span>
  )
}

export function ApplicationsList({ candidate }: { candidate: Candidate }) {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const status = (params.get('status') as ApplicationStatus | null) ?? undefined

  const applications = useQuery({
    queryKey: queryKeys.applications.list(candidate.id, { status }),
    queryFn: () => api.applications.list(candidate.id, { status }),
  })

  const items = useMemo(
    () => filterApplications(applications.data ?? [], search),
    [applications.data, search],
  )

  return (
    <>
      <PageHeader
        title="Applications"
        description="Jobs you are tracking. JobPilot prepares documents; you submit applications yourself."
      />

      <div className="mb-4 grid gap-2 sm:grid-cols-[1fr_12rem]">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="Search applications"
            placeholder="Search job, company, notes"
            className="pl-8"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <Select
          value={status ?? ALL}
          onValueChange={(value) =>
            setParams(value === ALL ? {} : { status: value }, { replace: true })
          }
        >
          <SelectTrigger aria-label="Filter by status" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {APPLICATION_STATUSES.map((value) => (
              <SelectItem key={value} value={value}>{STATUS_LABELS[value]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {applications.isPending ? (
        <ListSkeleton />
      ) : applications.isError ? (
        <ErrorState title="Could not load applications" error={applications.error} onRetry={() => applications.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Briefcase />}
          title={applications.data.length === 0 && !status ? 'No applications yet' : 'Nothing matches these filters'}
          description={
            applications.data.length === 0 && !status
              ? 'Track a job from its detail page, or generate a document for it.'
              : 'Try a different status or search.'
          }
          action={
            applications.data.length === 0 && !status ? (
              <Button asChild variant="outline"><Link to="/matches">Review matches</Link></Button>
            ) : undefined
          }
        />
      ) : (
        <>
          {/* Cards on small screens */}
          <ul className="space-y-2 md:hidden">
            {items.map((item) => (
              <li key={item.id}>
                <Link to={`/applications/${item.id}`} className="block rounded-lg border bg-card p-3 hover:border-foreground/20">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{item.job_title}</p>
                      <p className="truncate text-sm text-muted-foreground">{item.company_name ?? 'Company not listed'}</p>
                    </div>
                    <StatusBadge status={item.status} />
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-muted-foreground">
                    <span>Updated {formatRelative(item.updated_at)}</span>
                    <span>Follow-up: <FollowUp item={item} /></span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>

          {/* Table on larger screens */}
          <div className="hidden rounded-lg border bg-card md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Applied</TableHead>
                  <TableHead>Follow-up</TableHead>
                  <TableHead>Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id} className="relative">
                    <TableCell className="max-w-xs">
                      <Link to={`/applications/${item.id}`} className="font-medium after:absolute after:inset-0 hover:underline">
                        {item.job_title}
                      </Link>
                      <p className="truncate text-xs text-muted-foreground">
                        {[item.company_name, item.job_location].filter(Boolean).join(' · ') || '—'}
                      </p>
                    </TableCell>
                    <TableCell><StatusBadge status={item.status} /></TableCell>
                    <TableCell className="text-sm">{formatDate(item.applied_at)}</TableCell>
                    <TableCell className="text-sm"><FollowUp item={item} /></TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatRelative(item.updated_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {applications.data.length >= 100 && (
            <p className="mt-2 text-xs text-muted-foreground">Showing the 100 most recently updated applications.</p>
          )}
        </>
      )}
    </>
  )
}

export function ApplicationsPage() {
  return <WithCandidate>{(candidate) => <ApplicationsList candidate={candidate} />}</WithCandidate>
}
