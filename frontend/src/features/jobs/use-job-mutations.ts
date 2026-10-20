import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'

export function useRecalculateMatches(candidateId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => {
      if (!candidateId) throw new Error('Create your profile first.')
      return api.jobs.runMatching(candidateId)
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all })
      toast.success('Matches recalculated', {
        description: `${result.jobs_processed} active jobs scored.`,
      })
    },
    onError: (error) => toast.error('Matching failed', { description: error.message }),
  })
}
