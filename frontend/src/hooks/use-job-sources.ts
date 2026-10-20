import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import type { JobSourceInfo } from '@/lib/types'

/** Job providers registered on the backend. Nothing in the UI hardcodes them. */
export function useJobSources() {
  return useQuery({
    queryKey: queryKeys.jobSources,
    queryFn: api.jobs.sources,
    staleTime: 60_000,
  })
}

/** Display name for a stored `job.source` key. */
export function sourceLabel(key: string, sources: JobSourceInfo[] | undefined) {
  const match = sources?.find((source) => source.key === key)
  if (match) return match.label
  return key.charAt(0).toUpperCase() + key.slice(1)
}

export function useSourceLabel() {
  const { data } = useJobSources()
  return (key: string) => sourceLabel(key, data)
}
