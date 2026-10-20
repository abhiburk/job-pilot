import { useQuery } from '@tanstack/react-query'
import { UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { EmptyState, ErrorState, ListSkeleton } from '@/components/common'
import { Button } from '@/components/ui/button'
import { ApiError, api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import type { Candidate } from '@/lib/types'

/** The signed-in account's candidate profile; `null` when not created yet. */
export function useCandidate() {
  return useQuery({
    queryKey: queryKeys.candidate,
    queryFn: async (): Promise<Candidate | null> => {
      try {
        return await api.candidates.me()
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
  })
}

/** Renders children with the candidate, or a prompt to create a profile. */
export function WithCandidate({
  children,
}: {
  children: (candidate: Candidate) => ReactNode
}) {
  const candidate = useCandidate()

  if (candidate.isPending) return <ListSkeleton rows={3} />
  if (candidate.isError) {
    return (
      <ErrorState
        title="Could not load your profile"
        error={candidate.error}
        onRetry={() => candidate.refetch()}
      />
    )
  }
  if (!candidate.data) {
    return (
      <EmptyState
        icon={<UserRound />}
        title="Create your candidate profile first"
        description="Matching, analysis, and document generation all use your profile and resume."
        action={
          <Button asChild>
            <Link to="/profile">Create profile</Link>
          </Button>
        }
      />
    )
  }
  return <>{children(candidate.data)}</>
}
