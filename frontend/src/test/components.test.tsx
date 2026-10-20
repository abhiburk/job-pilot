import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { AuthProvider } from '@/auth/auth-context'
import { RequireAuth } from '@/auth/guards'
import { ApplicationsList } from '@/features/applications/applications-page'
import { DocumentReview } from '@/features/applications/documents'
import { DiscoverPage } from '@/features/jobs/discover-page'
import { LoginPage } from '@/features/auth/auth-pages'
import { SkillsManager } from '@/features/profile/skills-manager'
import type { ApplicationDocument, ApplicationListItem, Candidate } from '@/lib/types'
import { mockFetch, renderWithProviders } from './utils'

const candidate = { id: 'cand-1', full_name: 'Test User' } as Candidate

function application(overrides: Partial<ApplicationListItem> = {}): ApplicationListItem {
  return {
    id: 'app-1',
    candidate_id: 'cand-1',
    job_id: 'job-1',
    status: 'saved',
    application_url: null,
    applied_at: null,
    follow_up_at: null,
    notes: null,
    submission_metadata: null,
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-02T10:00:00Z',
    job_title: 'Senior Backend Engineer',
    company_name: 'Acme',
    job_location: 'Remote',
    job_url: 'https://example.com/job',
    job_source: 'jobicy',
    ...overrides,
  }
}

const draft: ApplicationDocument = {
  id: 'doc-1',
  application_id: 'app-1',
  document_type: 'cover_letter',
  version: 2,
  content_text: 'Dear Hiring Team,\nI build APIs.',
  generation_metadata: { model: 'test-model', warnings: ['Kubernetes requirement not supported by resume'] },
  is_approved: false,
  approved_at: null,
  created_at: '2026-10-02T10:00:00Z',
}

describe('ApplicationsList', () => {
  it('shows applications from the API', async () => {
    mockFetch({
      'GET /api/applications/candidate/cand-1': () => ({ body: [application()] }),
    })
    renderWithProviders(<ApplicationsList candidate={candidate} />)

    expect(await screen.findAllByText('Senior Backend Engineer')).not.toHaveLength(0)
    expect(screen.getAllByText('Saved').length).toBeGreaterThan(0)
  })

  it('shows an empty state when nothing is tracked', async () => {
    mockFetch({ 'GET /api/applications/candidate/cand-1': () => ({ body: [] }) })
    renderWithProviders(<ApplicationsList candidate={candidate} />)
    expect(await screen.findByText('No applications yet')).toBeInTheDocument()
  })

  it('shows the server error with a retry button', async () => {
    mockFetch({
      'GET /api/applications/candidate/cand-1': () => ({ status: 500, body: { detail: 'Database unavailable' } }),
    })
    renderWithProviders(<ApplicationsList candidate={candidate} />)
    expect(await screen.findByText('Database unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('passes the status filter to the API', async () => {
    const { calls } = mockFetch({
      'GET /api/applications/candidate/cand-1': () => ({ body: [] }),
    })
    renderWithProviders(<ApplicationsList candidate={candidate} />, { path: '/?status=applied' })
    await screen.findByText('Nothing matches these filters')
    expect(calls[0].url.searchParams.get('status')).toBe('applied')
  })
})

describe('DocumentReview approval', () => {
  it('stays a draft until the user explicitly confirms approval', async () => {
    const user = userEvent.setup()
    const { calls } = mockFetch({
      'PATCH /api/applications/app-1/documents/doc-1/approve': () => ({
        body: { ...draft, is_approved: true, approved_at: '2026-10-03T10:00:00Z' },
      }),
    })
    renderWithProviders(<DocumentReview document={draft} candidateId="cand-1" />)

    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByText('Kubernetes requirement not supported by resume')).toBeInTheDocument()
    expect(calls).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: /Approve version 2/ }))
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText('Dates and employment periods')).toBeInTheDocument()

    // Cancelling must not approve.
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(calls).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: /Approve version 2/ }))
    await user.click(await screen.findByRole('button', { name: /I verified it/ }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].url.searchParams.get('candidate_id')).toBe('cand-1')
    expect(await screen.findByText(/Cover letter v2 approved/)).toBeInTheDocument()
  })

  it('reports a failed approval and keeps the draft state', async () => {
    const user = userEvent.setup()
    mockFetch({
      'PATCH /api/applications/app-1/documents/doc-1/approve': () => ({
        status: 500,
        body: { detail: 'Unable to approve document.' },
      }),
    })
    renderWithProviders(<DocumentReview document={draft} candidateId="cand-1" />)

    await user.click(screen.getByRole('button', { name: /Approve version 2/ }))
    await user.click(await screen.findByRole('button', { name: /I verified it/ }))

    expect(await screen.findByText('Approval failed')).toBeInTheDocument()
    expect(screen.getByText(/Unable to approve document\. The document is still a draft\./)).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.queryByText('Approved by you')).not.toBeInTheDocument()
  })

  it('shows approved documents without an approve action', () => {
    mockFetch({})
    renderWithProviders(
      <DocumentReview document={{ ...draft, is_approved: true, approved_at: '2026-10-03T10:00:00Z' }} candidateId="cand-1" />,
    )
    expect(screen.getByText('Approved')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Approve version/ })).not.toBeInTheDocument()
  })
})

describe('authentication', () => {
  it('redirects signed-out users to login and remembers the destination', async () => {
    mockFetch({ 'GET /api/auth/me': () => ({ status: 401, body: { detail: 'Not authenticated' } }) })
    const { router } = renderWithProviders(<></>, {
      path: '/matches?min_score=70',
      routes: [
        {
          element: <AuthProvider><RequireAuth /></AuthProvider>,
          children: [{ path: '/matches', element: <p>Matches</p> }],
        },
        { path: '/login', element: <p>Login screen</p> },
      ],
    })

    expect(await screen.findByText('Login screen')).toBeInTheDocument()
    expect(router.state.location.search).toBe(`?next=${encodeURIComponent('/matches?min_score=70')}`)
  })

  it('shows invalid credential errors from the server', async () => {
    const user = userEvent.setup()
    mockFetch({
      'POST /api/auth/login': () => ({ status: 401, body: { detail: 'Invalid email or password' } }),
    })
    renderWithProviders(<></>, {
      path: '/login',
      routes: [{ path: '/login', element: <AuthProvider><LoginPage /></AuthProvider> }],
    })

    await user.type(screen.getByLabelText('Email'), 'me@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument()
  })

  it('validates the login form before calling the API', async () => {
    const user = userEvent.setup()
    const { calls } = mockFetch({})
    renderWithProviders(<></>, {
      path: '/login',
      routes: [{ path: '/login', element: <AuthProvider><LoginPage /></AuthProvider> }],
    })
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
    expect(calls.filter((call) => call.method === 'POST')).toHaveLength(0)
  })
})

describe('mutation failures', () => {
  it('reports a failed skill creation and keeps the input', async () => {
    const user = userEvent.setup()
    mockFetch({
      'GET /api/candidates/cand-1/skills': () => ({ body: [] }),
      'POST /api/candidates/cand-1/skills': () => ({
        status: 409,
        body: { detail: 'Candidate already has this skill' },
      }),
    })
    renderWithProviders(<SkillsManager candidateId="cand-1" />)

    await screen.findByText('No skills yet')
    await user.type(screen.getByLabelText('Skill'), 'Python')
    await user.click(screen.getByRole('button', { name: 'Add' }))

    expect(await screen.findByText('Could not add skill')).toBeInTheDocument()
    expect(screen.getByText('Candidate already has this skill')).toBeInTheDocument()
    expect(screen.getByLabelText('Skill')).toHaveValue('Python')
  })
})

describe('DiscoverPage', () => {
  const sources = [
    { key: 'jobicy', label: 'Jobicy', description: '', homepage: '', supported_filters: ['keywords'], remote_only: true, max_limit: 50, min_interval_minutes: 60, enabled: true, next_available_at: null, last_run: null },
    { key: 'freehire', label: 'FreeHire', description: '', homepage: '', supported_filters: ['keywords', 'country', 'work_mode'], remote_only: false, max_limit: 100, min_interval_minutes: null, enabled: true, next_available_at: null, last_run: null },
    { key: 'remotive', label: 'Remotive', description: '', homepage: '', supported_filters: ['keywords'], remote_only: true, max_limit: 50, min_interval_minutes: 360, enabled: true, next_available_at: null, last_run: null },
  ]

  it('runs one search across every source and reports each outcome', async () => {
    const user = userEvent.setup()
    const { calls } = mockFetch({
      'GET /api/candidates/me': () => ({ body: { id: 'cand-1', preferred_job_titles: ['Backend Developer'] } }),
      'GET /api/jobs/sources': () => ({ body: sources }),
      'GET /api/jobs': () => ({ body: { items: [], pagination: { total: 0, limit: 20, offset: 0, has_more: false } } }),
      'POST /api/jobs/discovery': () => ({
        body: {
          results: [
            { source: 'jobicy', label: 'Jobicy', status: 'skipped', fetched: 0, created: 0, skipped: 0, message: 'Jobicy allows one request every 1 hour.', ignored_filters: ['country'], next_available_at: null },
            { source: 'freehire', label: 'FreeHire', status: 'succeeded', fetched: 10, created: 4, skipped: 6, message: null, ignored_filters: [], next_available_at: null },
            { source: 'remotive', label: 'Remotive', status: 'succeeded', fetched: 5, created: 5, skipped: 0, message: null, ignored_filters: ['country'], next_available_at: null },
          ],
          totals: { fetched: 15, created: 9, skipped: 6, succeeded: 2, failed: 0 },
        },
      }),
    })
    renderWithProviders(<DiscoverPage />)

    // One generic form, prefilled from the profile, with every source selected.
    const keywords = await screen.findByLabelText('Role or skill')
    await waitFor(() => expect(keywords).toHaveValue('Backend Developer'))
    for (const label of ['Jobicy', 'FreeHire', 'Remotive']) {
      expect(await screen.findByRole('checkbox', { name: new RegExp(label) })).toBeChecked()
    }
    expect(screen.getAllByRole('button', { name: /Discover/ })).toHaveLength(1)

    await user.type(screen.getByLabelText('Country'), 'in')
    await user.click(screen.getByRole('button', { name: 'Discover jobs' }))

    expect(await screen.findByText('9 new jobs saved')).toBeInTheDocument()
    const post = calls.find((call) => call.method === 'POST')!
    expect(post.body).toEqual({ keywords: 'Backend Developer', country: 'IN', limit: 20 })
    expect(screen.getByText('Jobicy allows one request every 1 hour.')).toBeInTheDocument()
    expect(screen.getByText(/4 new · 10 fetched · 6 duplicates/)).toBeInTheDocument()
    expect(screen.getByText(/Does not support filtering by country/)).toBeInTheDocument()
  })

  it('sends only the selected sources when some are unchecked', async () => {
    const user = userEvent.setup()
    const { calls } = mockFetch({
      'GET /api/candidates/me': () => ({ body: { id: 'cand-1', preferred_job_titles: null } }),
      'GET /api/jobs/sources': () => ({ body: sources }),
      'GET /api/jobs': () => ({ body: { items: [], pagination: { total: 0, limit: 20, offset: 0, has_more: false } } }),
      'POST /api/jobs/discovery': () => ({ body: { results: [], totals: { fetched: 0, created: 0, skipped: 0, succeeded: 0, failed: 0 } } }),
    })
    renderWithProviders(<DiscoverPage />)

    await user.click(await screen.findByRole('checkbox', { name: /Jobicy/ }))
    await user.click(screen.getByRole('button', { name: 'Discover jobs' }))

    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true))
    expect(calls.find((call) => call.method === 'POST')!.body).toEqual({ limit: 20, sources: ['freehire', 'remotive'] })
  })
})
