import { Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useJobSources } from '@/hooks/use-job-sources'
import type { JobListParams, JobSort, RemoteType } from '@/lib/types'

export const PAGE_SIZE = 20
const ANY = 'any'

function useDebounced<T>(value: T, delay = 350) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(id)
  }, [value, delay])
  return debounced
}

/** Job list filters persisted in the URL so reloads and back/forward keep them. */
export function useJobFilters(defaults: { sort_by: JobSort; min_score?: number }) {
  const [params, setParams] = useSearchParams()

  const page = Math.max(0, Number(params.get('page') ?? 0) || 0)
  const q = params.get('q') ?? ''
  const minScoreParam = params.get('min_score')

  const filters: JobListParams = {
    // The API requires at least two characters for search.
    q: q.trim().length >= 2 ? q.trim() : undefined,
    location: params.get('location') || undefined,
    remote_type: (params.get('remote_type') as RemoteType) || undefined,
    employment_type: params.get('employment_type') || undefined,
    source: params.get('source') || undefined,
    sort_by: (params.get('sort') as JobSort) || defaults.sort_by,
    min_score:
      minScoreParam !== null ? Number(minScoreParam) : defaults.min_score,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }

  const update = (changes: Record<string, string | null>) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === '') next.delete(key)
          else next.set(key, value)
        }
        if (!('page' in changes)) next.delete('page')
        return next
      },
      { replace: true },
    )
  }

  const hasFilters = ['q', 'location', 'remote_type', 'employment_type', 'source', 'min_score', 'sort'].some(
    (key) => params.has(key),
  )

  return { params, filters, page, update, hasFilters, rawQuery: q }
}

function DebouncedInput({
  value,
  onChange,
  ...props
}: Omit<React.ComponentProps<typeof Input>, 'onChange' | 'value'> & {
  value: string
  onChange: (value: string) => void
}) {
  const [local, setLocal] = useState(value)
  const debounced = useDebounced(local)

  useEffect(() => setLocal(value), [value])
  useEffect(() => {
    if (debounced !== value) onChange(debounced)
    // onChange identity changes every render; the value comparison guards loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced])

  return <Input value={local} onChange={(event) => setLocal(event.target.value)} {...props} />
}

export function JobFilters({
  state,
  showScore = false,
  showMatchSort = false,
}: {
  state: ReturnType<typeof useJobFilters>
  showScore?: boolean
  showMatchSort?: boolean
}) {
  const { params, update, hasFilters, rawQuery } = state
  const sources = useJobSources()

  return (
    <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-[2fr_1.2fr_1fr_1fr_1fr_1fr_auto]">
      <div className="relative sm:col-span-2 lg:col-span-1">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <DebouncedInput
          aria-label="Search title, company, or description"
          placeholder="Search title, company, description"
          className="pl-8"
          value={rawQuery}
          onChange={(value) => update({ q: value })}
        />
      </div>
      <DebouncedInput
        aria-label="Location"
        placeholder="Location"
        value={params.get('location') ?? ''}
        onChange={(value) => update({ location: value })}
      />
      <Select
        value={params.get('remote_type') ?? ANY}
        onValueChange={(value) => update({ remote_type: value === ANY ? null : value })}
      >
        <SelectTrigger aria-label="Work mode" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any work mode</SelectItem>
          <SelectItem value="remote">Remote</SelectItem>
          <SelectItem value="hybrid">Hybrid</SelectItem>
          <SelectItem value="onsite">On-site</SelectItem>
        </SelectContent>
      </Select>
      <Select
        value={params.get('source') ?? ANY}
        onValueChange={(value) => update({ source: value === ANY ? null : value })}
      >
        <SelectTrigger aria-label="Source" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>All sources</SelectItem>
          {(sources.data ?? []).map((source) => (
            <SelectItem key={source.key} value={source.key}>{source.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      {showScore ? (
        <Select
          value={params.get('min_score') ?? '0'}
          onValueChange={(value) => update({ min_score: value === '0' ? null : value })}
        >
          <SelectTrigger aria-label="Minimum match score" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">Any score</SelectItem>
            <SelectItem value="50">Score 50+</SelectItem>
            <SelectItem value="60">Score 60+</SelectItem>
            <SelectItem value="70">Score 70+</SelectItem>
            <SelectItem value="80">Score 80+</SelectItem>
          </SelectContent>
        </Select>
      ) : (
        <DebouncedInput
          aria-label="Employment type"
          placeholder="Employment type"
          value={params.get('employment_type') ?? ''}
          onChange={(value) => update({ employment_type: value })}
        />
      )}
      <Select
        value={params.get('sort') ?? (showMatchSort ? 'match_score' : 'newest')}
        onValueChange={(value) => update({ sort: value })}
      >
        <SelectTrigger aria-label="Sort" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {showMatchSort && <SelectItem value="match_score">Best match</SelectItem>}
          <SelectItem value="newest">Newest</SelectItem>
          <SelectItem value="salary_high">Salary: high to low</SelectItem>
          <SelectItem value="salary_low">Salary: low to high</SelectItem>
        </SelectContent>
      </Select>
      {hasFilters ? (
        <Button
          variant="ghost"
          onClick={() =>
            update({ q: null, location: null, remote_type: null, employment_type: null, source: null, min_score: null, sort: null })
          }
        >
          <X /> Clear
        </Button>
      ) : (
        <span className="hidden lg:block" />
      )}
    </div>
  )
}

export function Pagination({
  total,
  page,
  onPage,
}: {
  total: number
  page: number
  onPage: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  if (total <= PAGE_SIZE) return null
  const start = page * PAGE_SIZE + 1
  const end = Math.min(total, (page + 1) * PAGE_SIZE)

  return (
    <div className="mt-4 flex items-center justify-between gap-2 text-sm text-muted-foreground">
      <span>
        {start}–{end} of {total}
      </span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={page === 0} onClick={() => onPage(page - 1)}>
          Previous
        </Button>
        <Button variant="outline" size="sm" disabled={page + 1 >= pages} onClick={() => onPage(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  )
}
