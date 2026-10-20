import { zodResolver } from '@hookform/resolvers/zod'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Compass, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { EmptyState, ErrorState, FieldError, ListSkeleton, PageHeader, Spinner } from '@/components/common'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useCandidate } from '@/hooks/use-candidate'
import { useJobSources } from '@/hooks/use-job-sources'
import { api } from '@/lib/api'
import { formatRelative } from '@/lib/format'
import { queryKeys } from '@/lib/query-keys'
import type {
  DiscoveryFilter,
  DiscoveryRequest,
  DiscoveryResponse,
  DiscoverySourceResult,
  JobSourceInfo,
  RemoteType,
} from '@/lib/types'
import { JobCard } from './job-card'
import { JobFilters, Pagination, useJobFilters } from './job-filters'
import { useRecalculateMatches } from './use-job-mutations'

// Limits mirror DiscoveryRequest in backend/app/schemas/discovery.py.
export const discoverySchema = z.object({
  keywords: z
    .string()
    .trim()
    .refine((value) => value === '' || (value.length >= 2 && value.length <= 100), 'Use 2–100 characters'),
  country: z
    .string()
    .trim()
    .refine((value) => value === '' || /^[A-Za-z]{2}$/.test(value), 'Use a 2-letter country code'),
  work_mode: z.enum(['any', 'remote', 'hybrid', 'onsite']),
  limit: z.number({ message: 'Enter a number' }).int().min(1, 'Use 1–50').max(50, 'Use 1–50'),
  sources: z.array(z.string()).min(1, 'Select at least one source'),
})

export type DiscoveryFormValues = z.infer<typeof discoverySchema>

export function toDiscoveryRequest(
  values: DiscoveryFormValues,
  allSourceKeys: string[],
): DiscoveryRequest {
  const allSelected =
    allSourceKeys.length > 0 && allSourceKeys.every((key) => values.sources.includes(key))
  return {
    keywords: values.keywords.trim() || undefined,
    country: values.country.trim() ? values.country.trim().toUpperCase() : undefined,
    work_mode: values.work_mode === 'any' ? undefined : (values.work_mode as RemoteType),
    limit: values.limit,
    // Omitted = every enabled source, including ones added later.
    sources: allSelected ? undefined : values.sources,
  }
}

const FILTER_LABELS: Record<DiscoveryFilter, string> = {
  keywords: 'keywords',
  country: 'country',
  work_mode: 'work mode',
}

const RESULT_STYLES: Record<DiscoverySourceResult['status'], string> = {
  succeeded: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  failed: 'border-rose-200 bg-rose-50 text-rose-800',
  skipped: 'bg-muted text-muted-foreground',
}

function SourceNote({ source }: { source: JobSourceInfo }) {
  const notes = []
  if (source.remote_only) notes.push('remote only')
  if (source.next_available_at) notes.push(`next run ${formatRelative(source.next_available_at)}`)
  else if (source.min_interval_minutes) {
    notes.push(
      source.min_interval_minutes >= 60
        ? `max once per ${source.min_interval_minutes / 60 === 1 ? 'hour' : `${source.min_interval_minutes / 60} hours`}`
        : `max once per ${source.min_interval_minutes} min`,
    )
  }
  if (!notes.length) return null
  return <span className="text-xs text-muted-foreground">({notes.join(', ')})</span>
}

export function DiscoveryResults({ response }: { response: DiscoveryResponse }) {
  return (
    <div className="mt-4 space-y-3" role="status">
      <p className="text-sm">
        <span className="font-medium">{response.totals.created} new jobs saved</span>{' '}
        <span className="text-muted-foreground">
          from {response.totals.fetched} fetched · {response.totals.skipped} duplicates or incomplete
        </span>
      </p>
      <ul className="divide-y rounded-lg border">
        {response.results.map((result) => (
          <li key={result.source} className="flex flex-col gap-1 px-3 py-2.5 sm:flex-row sm:items-center sm:gap-3">
            <div className="flex items-center gap-2 sm:w-40">
              <span className="text-sm font-medium">{result.label}</span>
              <Badge variant="outline" className={RESULT_STYLES[result.status]}>
                {result.status === 'succeeded' ? 'Done' : result.status === 'failed' ? 'Failed' : 'Skipped'}
              </Badge>
            </div>
            <div className="flex-1 text-sm text-muted-foreground">
              {result.status === 'succeeded' ? (
                <span>
                  {result.created} new · {result.fetched} fetched · {result.skipped} duplicates
                </span>
              ) : (
                <span>{result.message}</span>
              )}
              {result.next_available_at && (
                <span> Next run {formatRelative(result.next_available_at)}.</span>
              )}
              {result.ignored_filters.length > 0 && result.status === 'succeeded' && (
                <span className="block text-xs">
                  Does not support filtering by {result.ignored_filters.map((name) => FILTER_LABELS[name]).join(' or ')}; results are unfiltered there.
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function DiscoveryForm({
  defaultKeywords,
  onDone,
}: {
  defaultKeywords: string
  onDone: (response: DiscoveryResponse) => void
}) {
  const queryClient = useQueryClient()
  const sources = useJobSources()
  const enabled = useMemo(() => (sources.data ?? []).filter((source) => source.enabled), [sources.data])
  const enabledKeys = useMemo(() => enabled.map((source) => source.key), [enabled])
  const [response, setResponse] = useState<DiscoveryResponse | null>(null)

  const form = useForm<DiscoveryFormValues>({
    resolver: zodResolver(discoverySchema),
    defaultValues: { keywords: defaultKeywords, country: '', work_mode: 'any', limit: 20, sources: [] },
  })

  // Select every source once the registry has loaded.
  useEffect(() => {
    if (enabledKeys.length && !form.getValues('sources').length) {
      form.setValue('sources', enabledKeys)
    }
  }, [enabledKeys, form])

  const discover = useMutation({
    mutationFn: (values: DiscoveryFormValues) => api.jobs.discover(toDiscoveryRequest(values, enabledKeys)),
    onMutate: () => setResponse(null),
    onSuccess: (data) => {
      setResponse(data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobSources })
      const { created, failed } = data.totals
      if (failed && failed === data.results.length) {
        toast.error('No source returned results', { description: 'See the details below.' })
      } else {
        toast.success(`Discovery finished: ${created} new jobs`)
      }
      onDone(data)
    },
    onError: (error) => toast.error('Discovery failed', { description: error.message }),
  })

  const errors = form.formState.errors
  const selectedCount = form.watch('sources').length

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Search job sources</CardTitle>
        <CardDescription>
          One search runs against every selected source. Filters a source does not support are reported in the results.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form noValidate className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr]" onSubmit={form.handleSubmit((values) => discover.mutate(values))}>
          <div className="space-y-1.5 sm:col-span-2 lg:col-span-1">
            <Label htmlFor="discover-keywords">Role or skill</Label>
            <Input id="discover-keywords" placeholder="e.g. backend developer" {...form.register('keywords')} aria-invalid={!!errors.keywords} aria-describedby="discover-keywords-hint" />
            <p id="discover-keywords-hint" className="text-xs text-muted-foreground">One phrase works best. Leave empty for the newest listings.</p>
            <FieldError message={errors.keywords?.message} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="discover-country">Country</Label>
            <Input id="discover-country" placeholder="e.g. IN" maxLength={2} className="uppercase" {...form.register('country')} aria-invalid={!!errors.country} />
            <FieldError message={errors.country?.message} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="discover-mode">Work mode</Label>
            <Controller
              control={form.control}
              name="work_mode"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="discover-mode" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any</SelectItem>
                    <SelectItem value="remote">Remote</SelectItem>
                    <SelectItem value="hybrid">Hybrid</SelectItem>
                    <SelectItem value="onsite">On-site</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="discover-limit">Per source</Label>
            <Input id="discover-limit" type="number" min={1} max={50} {...form.register('limit', { valueAsNumber: true })} aria-invalid={!!errors.limit} />
            <FieldError message={errors.limit?.message} />
          </div>

          <fieldset className="space-y-2 sm:col-span-2 lg:col-span-4">
            <legend className="text-sm font-medium">Sources</legend>
            {sources.isPending ? (
              <Skeleton className="h-6 w-64" />
            ) : sources.isError ? (
              <p className="text-sm text-destructive">Could not load sources: {sources.error.message}</p>
            ) : (
              <Controller
                control={form.control}
                name="sources"
                render={({ field }) => (
                  <div className="flex flex-wrap gap-x-5 gap-y-2">
                    {enabled.map((source) => (
                      <label key={source.key} className="flex items-center gap-2 text-sm" title={source.description}>
                        <Checkbox
                          checked={field.value.includes(source.key)}
                          onCheckedChange={(checked) =>
                            field.onChange(
                              checked
                                ? [...field.value, source.key]
                                : field.value.filter((key) => key !== source.key),
                            )
                          }
                        />
                        {source.label}
                        <SourceNote source={source} />
                      </label>
                    ))}
                  </div>
                )}
              />
            )}
            <FieldError message={errors.sources?.message} />
          </fieldset>

          <div className="sm:col-span-2 lg:col-span-4">
            <Button type="submit" disabled={discover.isPending || sources.isPending}>
              {discover.isPending ? <Spinner /> : <Compass />}
              {discover.isPending
                ? `Searching ${selectedCount} source${selectedCount === 1 ? '' : 's'}…`
                : 'Discover jobs'}
            </Button>
            {discover.isPending && (
              <span className="ml-3 text-xs text-muted-foreground">Waiting for every source to respond; this can take up to 20 seconds.</span>
            )}
          </div>
        </form>
        {response && <DiscoveryResults response={response} />}
      </CardContent>
    </Card>
  )
}

export function DiscoverPage() {
  const candidate = useCandidate()
  const candidateId = candidate.data?.id
  const [needsMatching, setNeedsMatching] = useState(false)
  const recalculate = useRecalculateMatches(candidateId)
  const filterState = useJobFilters({ sort_by: 'newest' })
  const params = { ...filterState.filters, candidate_id: candidateId }

  const jobs = useQuery({
    queryKey: queryKeys.jobs.list(params),
    queryFn: () => api.jobs.list(params),
    enabled: !candidate.isPending,
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader
        title="Discover jobs"
        description="Fetch new listings from all connected job sources with one search."
      />

      {candidate.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <DiscoveryForm
          defaultKeywords={candidate.data?.preferred_job_titles?.[0] ?? ''}
          onDone={(response) => setNeedsMatching(response.totals.created > 0)}
        />
      )}

      {needsMatching && candidateId && (
        <Alert className="mt-4">
          <RefreshCw />
          <AlertTitle>New jobs are not scored yet</AlertTitle>
          <AlertDescription>
            <p>Recalculate matches to score them against your profile.</p>
            <Button
              size="sm"
              className="mt-2"
              disabled={recalculate.isPending}
              onClick={() => recalculate.mutate(undefined, { onSuccess: () => setNeedsMatching(false) })}
            >
              {recalculate.isPending && <Spinner />}
              Recalculate matches
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <section className="mt-8" aria-labelledby="all-jobs">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="all-jobs" className="text-base font-semibold">All active jobs</h2>
          {jobs.data && (
            <span className="text-sm text-muted-foreground">{jobs.data.pagination.total} jobs</span>
          )}
        </div>
        <JobFilters state={filterState} />
        {jobs.isPending ? (
          <ListSkeleton />
        ) : jobs.isError ? (
          <ErrorState title="Could not load jobs" error={jobs.error} onRetry={() => jobs.refetch()} />
        ) : jobs.data.items.length === 0 ? (
          <EmptyState
            icon={<Compass />}
            title={filterState.hasFilters ? 'No jobs match these filters' : 'No jobs yet'}
            description={filterState.hasFilters ? 'Try clearing a filter.' : 'Run a discovery above to fetch listings.'}
          />
        ) : (
          <div className={jobs.isPlaceholderData ? 'space-y-3 opacity-60' : 'space-y-3'}>
            {jobs.data.items.map((job) => (
              <JobCard key={job.id} job={job} showMatch={!!candidateId} />
            ))}
            <Pagination
              total={jobs.data.pagination.total}
              page={filterState.page}
              onPage={(page) => filterState.update({ page: String(page) })}
            />
          </div>
        )}
      </section>
    </>
  )
}
