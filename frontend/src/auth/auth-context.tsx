import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { ApiError, api, onUnauthorized, setCsrfToken } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import type { SessionResponse, User } from '@/lib/types'

type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'error'

type AuthContextValue = {
  status: AuthStatus
  user: User | null
  /** True after a request was rejected because the session ended. */
  sessionExpired: boolean
  error: Error | null
  login: (email: string, password: string) => Promise<void>
  register: (input: { email: string; password: string; full_name?: string }) => Promise<void>
  logout: () => Promise<void>
  setUser: (user: User) => void
  retry: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

async function fetchSession(): Promise<SessionResponse | null> {
  try {
    return await api.auth.me()
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [sessionExpired, setSessionExpired] = useState(false)

  const session = useQuery({
    queryKey: queryKeys.session,
    queryFn: fetchSession,
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    setCsrfToken(session.data?.csrf_token ?? null)
  }, [session.data])

  const startSession = useCallback(
    (response: SessionResponse) => {
      setCsrfToken(response.csrf_token)
      setSessionExpired(false)
      // Drop anything cached for a previous account before showing data.
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== queryKeys.session[0],
      })
      queryClient.setQueryData(queryKeys.session, response)
    },
    [queryClient],
  )

  const endSession = useCallback(() => {
    setCsrfToken(null)
    queryClient.setQueryData(queryKeys.session, null)
    queryClient.removeQueries({
      predicate: (query) => query.queryKey[0] !== queryKeys.session[0],
    })
  }, [queryClient])

  useEffect(
    () =>
      onUnauthorized(() => {
        if (queryClient.getQueryData(queryKeys.session)) {
          setSessionExpired(true)
          endSession()
        }
      }),
    [endSession, queryClient],
  )

  const value = useMemo<AuthContextValue>(() => {
    let status: AuthStatus = 'loading'
    if (session.isError) status = 'error'
    else if (session.isSuccess) status = session.data ? 'authenticated' : 'anonymous'

    return {
      status,
      user: session.data?.user ?? null,
      sessionExpired,
      error: session.error,
      login: async (email, password) => {
        startSession(await api.auth.login(email, password))
      },
      register: async (input) => {
        startSession(await api.auth.register(input))
      },
      logout: async () => {
        try {
          await api.auth.logout()
        } finally {
          setSessionExpired(false)
          endSession()
        }
      },
      setUser: (user) => {
        queryClient.setQueryData<SessionResponse | null>(queryKeys.session, (current) =>
          current ? { ...current, user } : current,
        )
      },
      retry: () => {
        void session.refetch()
      },
    }
  }, [session, sessionExpired, startSession, endSession, queryClient])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
