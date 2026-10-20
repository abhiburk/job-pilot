import { afterEach, describe, expect, it, vi } from 'vitest'

import { mockFetch } from '@/test/utils'
import { ApiError, api, buildUrl, onUnauthorized, request, setCsrfToken } from './api'

afterEach(() => setCsrfToken(null))

describe('api client', () => {
  it('builds URLs from the configured base and skips empty query values', () => {
    const url = new URL(buildUrl('/api/jobs', { q: 'python', location: '', min_score: 0, x: undefined }))
    expect(url.origin).toBe('http://localhost:8000')
    expect(url.pathname).toBe('/api/jobs')
    expect(url.searchParams.get('q')).toBe('python')
    expect(url.searchParams.get('min_score')).toBe('0')
    expect(url.searchParams.has('location')).toBe(false)
    expect(url.searchParams.has('x')).toBe(false)
  })

  it('sends cookies and attaches the CSRF token only to unsafe methods', async () => {
    const { calls, fetchMock } = mockFetch({
      'GET /api/candidates/me': () => ({ body: { id: 'c1' } }),
      'PATCH /api/candidates/c1': () => ({ body: { id: 'c1' } }),
    })
    setCsrfToken('csrf-123')

    await api.candidates.me()
    await api.candidates.update('c1', { full_name: 'A' })

    expect(calls[0].headers.get('X-CSRF-Token')).toBeNull()
    expect(calls[1].headers.get('X-CSRF-Token')).toBe('csrf-123')
    expect(calls[1].body).toEqual({ full_name: 'A' })
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include' })
  })

  it('turns FastAPI validation errors into field errors', async () => {
    mockFetch({
      'POST /api/candidates': () => ({
        status: 422,
        body: {
          detail: [
            { loc: ['body', 'email'], msg: 'value is not a valid email address' },
            { loc: ['body'], msg: 'Value error, full_name cannot be null' },
          ],
        },
      }),
    })

    const error = await api.candidates
      .create({ full_name: 'x', email: 'bad' })
      .catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(422)
    expect((error as ApiError).fieldErrors.email).toBe('value is not a valid email address')
    expect((error as ApiError).message).toContain('full_name cannot be null')
  })

  it('uses the server detail message and Retry-After header', async () => {
    mockFetch({
      'POST /api/auth/login': () => ({
        status: 429,
        body: { detail: 'Too many failed sign-in attempts. Try again later.' },
        headers: { 'Retry-After': '120' },
      }),
    })

    const error = (await api.auth.login('a@b.co', 'x').catch((e: unknown) => e)) as ApiError
    expect(error.message).toBe('Too many failed sign-in attempts. Try again later.')
    expect(error.retryAfter).toBe(120)
  })

  it('falls back to a readable message for errors without a body', async () => {
    mockFetch({ 'POST /api/jobs/discovery': () => ({ status: 502, body: null }) })
    const error = (await api.jobs.discover({ limit: 5 }).catch((e: unknown) => e)) as ApiError
    expect(error.status).toBe(502)
    expect(error.message).toMatch(/temporarily unavailable/)
  })

  it('reports network failures as status 0 with guidance', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = (await api.health.api().catch((e: unknown) => e)) as ApiError
    expect(error.isNetworkError).toBe(true)
    expect(error.message).toMatch(/Cannot reach the JobPilot API/)
  })

  it('notifies listeners on 401 except for auth endpoints', async () => {
    mockFetch({
      'GET /api/candidates/me': () => ({ status: 401, body: { detail: 'Session expired' } }),
      'POST /api/auth/login': () => ({ status: 401, body: { detail: 'Invalid email or password' } }),
    })
    const listener = vi.fn()
    const unsubscribe = onUnauthorized(listener)

    await api.auth.login('a@b.co', 'wrong').catch(() => undefined)
    expect(listener).not.toHaveBeenCalled()

    await api.candidates.me().catch(() => undefined)
    expect(listener).toHaveBeenCalledTimes(1)
    unsubscribe()
  })

  it('returns undefined for 204 responses', async () => {
    mockFetch({ 'DELETE /api/applications/a1': () => ({ status: 204 }) })
    await expect(request('/api/applications/a1', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('sends resume uploads as multipart form data', async () => {
    const { fetchMock } = mockFetch({
      'POST /api/candidates/c1/resume/upload': () => ({ body: { jobs_processed: 1 } }),
    })
    const file = new File(['%PDF'], 'resume.pdf', { type: 'application/pdf' })
    await api.candidates.uploadResume('c1', file)

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBe(file)
    expect(new Headers(init.headers).get('Content-Type')).toBeNull()
  })
})
