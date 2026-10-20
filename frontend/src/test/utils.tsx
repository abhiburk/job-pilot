import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { RouterProvider, createMemoryRouter } from 'react-router'
import type { RouteObject } from 'react-router'
import { vi } from 'vitest'

import { Toaster } from '@/components/ui/sonner'

type Handler = (request: { url: URL; method: string; body: unknown; headers: Headers }) =>
  | { status?: number; body?: unknown; headers?: Record<string, string> }
  | undefined

export type FetchCall = { url: URL; method: string; body: unknown; headers: Headers }

/** Replaces fetch with a router of `METHOD /path` handlers. Unmatched calls fail the test. */
export function mockFetch(handlers: Record<string, Handler>) {
  const calls: FetchCall[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input))
    const method = (init.method ?? 'GET').toUpperCase()
    const headers = new Headers(init.headers)
    let body: unknown = init.body
    if (typeof init.body === 'string') body = JSON.parse(init.body)
    const call = { url, method, body, headers }
    calls.push(call)

    const handler = handlers[`${method} ${url.pathname}`]
    if (!handler) throw new Error(`Unexpected request: ${method} ${url.pathname}`)
    const result = handler(call) ?? {}
    const status = result.status ?? 200
    return new Response(
      status === 204 ? null : JSON.stringify(result.body ?? null),
      { status, headers: { 'Content-Type': 'application/json', ...result.headers } },
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, calls }
}

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

export function renderWithProviders(
  ui: ReactElement,
  { path = '/', routes }: { path?: string; routes?: RouteObject[] } = {},
) {
  const queryClient = createTestQueryClient()
  const router = createMemoryRouter(routes ?? [{ path: '*', element: ui }], {
    initialEntries: [path],
  })
  const result = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>,
  )
  return { ...result, queryClient, router }
}
