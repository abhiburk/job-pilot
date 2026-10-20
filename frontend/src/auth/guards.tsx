import { Loader2 } from 'lucide-react'
import { Navigate, Outlet, useLocation, useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { useAuth } from './auth-context'

/** Only same-app paths are accepted as post-login destinations. */
export function safeNextPath(value: string | null | undefined) {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return '/'
  if (value.startsWith('/login') || value.startsWith('/register')) return '/'
  return value
}

function FullPageMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-svh items-center justify-center bg-muted/40 p-6">
      {children}
    </div>
  )
}

function SessionError() {
  const { error, retry } = useAuth()
  return (
    <FullPageMessage>
      <div className="max-w-sm space-y-3 text-center">
        <p className="font-medium">Could not check your session</p>
        <p className="text-sm text-muted-foreground">{error?.message}</p>
        <Button onClick={retry}>Try again</Button>
      </div>
    </FullPageMessage>
  )
}

function Loading() {
  return (
    <FullPageMessage>
      <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
    </FullPageMessage>
  )
}

export function RequireAuth() {
  const { status, sessionExpired } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <Loading />
  if (status === 'error') return <SessionError />

  if (status === 'anonymous') {
    const next = `${location.pathname}${location.search}`
    const params = new URLSearchParams()
    if (next !== '/') params.set('next', next)
    if (sessionExpired) params.set('expired', '1')
    const query = params.toString()
    return <Navigate to={`/login${query ? `?${query}` : ''}`} replace />
  }

  return <Outlet />
}

/** For login/register pages: signed-in users go straight to the app. */
export function RedirectIfAuthenticated() {
  const { status } = useAuth()
  const [params] = useSearchParams()

  if (status === 'loading') return <Loading />
  if (status === 'authenticated') {
    return <Navigate to={safeNextPath(params.get('next'))} replace />
  }
  return <Outlet />
}
