import { describe, expect, it } from 'vitest'

import { safeNextPath } from '@/auth/guards'
import { applicationFormSchema, changedFields } from '@/features/applications/application-detail-page'
import { generationBlockers, groupDocuments } from '@/features/applications/documents'
import { filterApplications } from '@/features/applications/applications-page'
import { loginSchema, registerSchema } from '@/features/auth/auth-pages'
import { discoverySchema, toDiscoveryRequest } from '@/features/jobs/discover-page'
import { profileSchema, toFormValues, toPayload } from '@/features/profile/profile-form'
import { validateResumeFile } from '@/features/profile/resume-upload'
import { skillSchema } from '@/features/profile/skills-manager'
import type { ApplicationDocument, ApplicationListItem, Candidate } from './types'
import { htmlToText } from './html-to-text'

describe('auth forms', () => {
  it('requires a valid email and a 10+ character matching password', () => {
    expect(registerSchema.safeParse({ email: 'a@b.co', password: 'short', confirm: 'short' }).success).toBe(false)
    const mismatch = registerSchema.safeParse({ email: 'a@b.co', password: 'long enough pw', confirm: 'different pw!' })
    expect(mismatch.success).toBe(false)
    expect(mismatch.error?.issues[0].path).toEqual(['confirm'])
    expect(registerSchema.safeParse({ email: 'a@b.co', password: 'long enough pw', confirm: 'long enough pw' }).success).toBe(true)
    expect(loginSchema.safeParse({ email: 'nope', password: 'x' }).success).toBe(false)
  })

  it('only allows same-app redirect targets after login', () => {
    expect(safeNextPath('/jobs/1?x=2')).toBe('/jobs/1?x=2')
    expect(safeNextPath('https://evil.example')).toBe('/')
    expect(safeNextPath('//evil.example')).toBe('/')
    expect(safeNextPath('/login')).toBe('/')
    expect(safeNextPath(null)).toBe('/')
  })
})

describe('profile form', () => {
  const base = toFormValues(null, 'me@example.com')

  it('validates URLs, currency and numeric ranges like the API', () => {
    expect(profileSchema.safeParse({ ...base, full_name: 'Me' }).success).toBe(true)
    expect(profileSchema.safeParse({ ...base, full_name: '' }).success).toBe(false)
    expect(profileSchema.safeParse({ ...base, full_name: 'Me', salary_currency: 'RUPEE' }).success).toBe(false)
    expect(profileSchema.safeParse({ ...base, full_name: 'Me', years_experience: '-1' }).success).toBe(false)
    expect(profileSchema.safeParse({ ...base, full_name: 'Me', github_url: 'github.com/me' }).success).toBe(false)
  })

  it('converts form strings into the API payload', () => {
    const payload = toPayload({
      ...base,
      full_name: '  Me ',
      preferred_job_titles: 'Backend Engineer, , Python Developer',
      years_experience: '6.5',
      minimum_salary: '',
      salary_currency: 'inr',
      phone: '  ',
    })
    expect(payload.full_name).toBe('Me')
    expect(payload.preferred_job_titles).toEqual(['Backend Engineer', 'Python Developer'])
    expect(payload.preferred_locations).toBeNull()
    expect(payload.years_experience).toBe(6.5)
    expect(payload.minimum_salary).toBeNull()
    expect(payload.salary_currency).toBe('INR')
    expect(payload.phone).toBeNull()
  })

  it('round-trips an existing candidate', () => {
    const values = toFormValues({
      full_name: 'Me', email: 'me@example.com', preferred_locations: ['India', 'Remote'],
      years_experience: '8.0', salary_currency: 'INR', remote_only: true,
    } as Candidate)
    expect(values.preferred_locations).toBe('India, Remote')
    expect(values.years_experience).toBe('8.0')
    expect(values.remote_only).toBe(true)
  })
})

describe('other forms', () => {
  it('validates skills', () => {
    const ok = { name: 'Python', category: '', proficiency: '', years_experience: '3', is_primary: false }
    expect(skillSchema.safeParse(ok).success).toBe(true)
    expect(skillSchema.safeParse({ ...ok, name: '  ' }).success).toBe(false)
    expect(skillSchema.safeParse({ ...ok, years_experience: '61' }).success).toBe(false)
  })

  it('mirrors the generic discovery request limits', () => {
    const ok = { keywords: '', country: '', work_mode: 'any' as const, limit: 20, sources: ['a'] }
    expect(discoverySchema.safeParse(ok).success).toBe(true)
    expect(discoverySchema.safeParse({ ...ok, keywords: 'x' }).success).toBe(false)
    expect(discoverySchema.safeParse({ ...ok, country: 'IND' }).success).toBe(false)
    expect(discoverySchema.safeParse({ ...ok, limit: 51 }).success).toBe(false)
    expect(discoverySchema.safeParse({ ...ok, sources: [] }).success).toBe(false)
  })

  it('builds one request for all sources', () => {
    const values = { keywords: ' backend developer ', country: 'in', work_mode: 'any' as const, limit: 10, sources: ['jobicy', 'remotive'] }
    // Everything selected → omit the list so newly added sources are included.
    expect(toDiscoveryRequest(values, ['jobicy', 'remotive'])).toEqual({
      keywords: 'backend developer', country: 'IN', work_mode: undefined, limit: 10, sources: undefined,
    })
    expect(toDiscoveryRequest({ ...values, keywords: '', work_mode: 'remote' }, ['jobicy', 'remotive', 'freehire'])).toEqual({
      keywords: undefined, country: 'IN', work_mode: 'remote', limit: 10, sources: ['jobicy', 'remotive'],
    })
  })

  it('rejects unsupported resume files before upload', () => {
    expect(validateResumeFile(new File(['x'], 'cv.txt'))).toMatch(/PDF and DOCX/)
    expect(validateResumeFile(new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'cv.pdf'))).toMatch(/5 MB/)
    expect(validateResumeFile(new File(['x'], 'CV.DOCX'))).toBeNull()
  })

  it('sends only changed application fields', () => {
    const initial = { status: 'saved' as const, applied_at: '', follow_up_at: '', application_url: '', notes: '' }
    expect(changedFields(initial, initial)).toEqual({})
    const update = changedFields(initial, { ...initial, status: 'applied', follow_up_at: '2026-11-02' })
    expect(update.status).toBe('applied')
    expect(update.follow_up_at).toMatch(/^2026-11-0[12]T/)
    expect('applied_at' in update).toBe(false)
    expect(applicationFormSchema.safeParse({ ...initial, status: 'ghosted' }).success).toBe(false)
  })
})

describe('documents', () => {
  const candidate = { resume_text: 'Python', summary: null, headline: null } as Candidate

  it('explains why generation is unavailable', () => {
    expect(generationBlockers('tailored_resume', candidate, { is_active: false, description: 'x' })).toMatch(/no longer active/)
    expect(generationBlockers('tailored_resume', candidate, { is_active: true, description: '' })).toMatch(/no description/)
    expect(generationBlockers('tailored_resume', { ...candidate, resume_text: '' }, { is_active: true, description: 'x' })).toMatch(/resume/)
    expect(generationBlockers('cover_letter', { ...candidate, resume_text: '' }, { is_active: true, description: '' })).toMatch(/resume, summary, or headline/)
    expect(generationBlockers('cover_letter', candidate, { is_active: true, description: '' })).toBeNull()
  })

  it('groups versions newest first', () => {
    const doc = (type: string, version: number) => ({ id: `${type}${version}`, document_type: type, version }) as ApplicationDocument
    const groups = groupDocuments([doc('cover_letter', 1), doc('tailored_resume', 1), doc('cover_letter', 3)])
    expect(groups.get('cover_letter')?.map((d) => d.version)).toEqual([3, 1])
    expect(groups.get('tailored_resume')).toHaveLength(1)
  })
})

describe('applications search', () => {
  it('matches job, company and notes case-insensitively', () => {
    const items = [
      { id: '1', job_title: 'Backend Engineer', company_name: 'Acme', job_location: null, notes: null },
      { id: '2', job_title: 'Data Engineer', company_name: 'Globex', job_location: null, notes: 'Recruiter: Sam' },
    ] as ApplicationListItem[]
    expect(filterApplications(items, 'acme').map((i) => i.id)).toEqual(['1'])
    expect(filterApplications(items, 'SAM').map((i) => i.id)).toEqual(['2'])
    expect(filterApplications(items, '  ')).toHaveLength(2)
  })
})

describe('htmlToText', () => {
  it('keeps text structure and drops markup and scripts', () => {
    const text = htmlToText('<p>Hello <b>world</b></p><ul><li>One</li><li>Two</li></ul><script>alert(1)</script>')
    expect(text).toBe('Hello world\n\n• One\n• Two')
  })

  it('never executes handlers in untrusted HTML', () => {
    const marker = { hit: false }
    ;(window as unknown as { __hit: typeof marker }).__hit = marker
    const text = htmlToText('<img src="x" onerror="window.__hit.hit = true">Text')
    expect(text).toBe('Text')
    expect(marker.hit).toBe(false)
  })

  it('returns plain text unchanged', () => {
    expect(htmlToText('  5 < 6 and plain  ')).toBe('5 < 6 and plain')
    expect(htmlToText(null)).toBe('')
  })
})
