import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { FieldError, Spinner } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, api } from '@/lib/api'
import { joinList, splitList } from '@/lib/format'
import { queryKeys } from '@/lib/query-keys'
import type { Candidate, CandidateInput } from '@/lib/types'

const optionalUrl = z
  .string()
  .max(500, 'Use at most 500 characters')
  .refine((value) => !value || /^https?:\/\/\S+$/i.test(value), 'Enter a full URL starting with https://')

const optionalNumber = (max?: number) =>
  z.string().refine((value) => {
    if (!value.trim()) return true
    const number = Number(value)
    return Number.isFinite(number) && number >= 0 && (max === undefined || number <= max)
  }, max === undefined ? 'Enter a positive number' : `Enter a number between 0 and ${max}`)

export const profileSchema = z.object({
  full_name: z.string().trim().min(1, 'Name is required').max(150),
  email: z.email('Enter a valid email address'),
  phone: z.string().max(50),
  headline: z.string().max(255),
  location: z.string().max(255),
  summary: z.string(),
  preferred_job_titles: z.string(),
  preferred_locations: z.string(),
  preferred_employment_types: z.string(),
  preferred_work_modes: z.string(),
  years_experience: optionalNumber(999.9),
  minimum_salary: optionalNumber(),
  salary_currency: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{3}$/, 'Use a 3-letter currency code, e.g. INR'),
  remote_only: z.boolean(),
  linkedin_url: optionalUrl,
  github_url: optionalUrl,
  portfolio_url: optionalUrl,
  resume_text: z.string(),
})

export type ProfileFormValues = z.infer<typeof profileSchema>

export function toFormValues(candidate: Candidate | null, fallbackEmail = ''): ProfileFormValues {
  const text = (value: string | number | null | undefined) =>
    value === null || value === undefined ? '' : String(value)
  return {
    full_name: candidate?.full_name ?? '',
    email: candidate?.email ?? fallbackEmail,
    phone: text(candidate?.phone),
    headline: text(candidate?.headline),
    location: text(candidate?.location),
    summary: text(candidate?.summary),
    preferred_job_titles: joinList(candidate?.preferred_job_titles),
    preferred_locations: joinList(candidate?.preferred_locations),
    preferred_employment_types: joinList(candidate?.preferred_employment_types),
    preferred_work_modes: joinList(candidate?.preferred_work_modes),
    years_experience: text(candidate?.years_experience),
    minimum_salary: text(candidate?.minimum_salary),
    salary_currency: candidate?.salary_currency ?? 'INR',
    remote_only: candidate?.remote_only ?? false,
    linkedin_url: text(candidate?.linkedin_url),
    github_url: text(candidate?.github_url),
    portfolio_url: text(candidate?.portfolio_url),
    resume_text: text(candidate?.resume_text),
  }
}

export function toPayload(values: ProfileFormValues): CandidateInput {
  const nullable = (value: string) => (value.trim() ? value.trim() : null)
  const list = (value: string) => {
    const items = splitList(value)
    return items.length ? items : null
  }
  const number = (value: string) => (value.trim() ? Number(value) : null)

  return {
    full_name: values.full_name.trim(),
    email: values.email.trim(),
    phone: nullable(values.phone),
    headline: nullable(values.headline),
    location: nullable(values.location),
    summary: nullable(values.summary),
    preferred_job_titles: list(values.preferred_job_titles),
    preferred_locations: list(values.preferred_locations),
    preferred_employment_types: list(values.preferred_employment_types),
    preferred_work_modes: list(values.preferred_work_modes),
    years_experience: number(values.years_experience),
    minimum_salary: number(values.minimum_salary),
    salary_currency: values.salary_currency.trim().toUpperCase(),
    remote_only: values.remote_only,
    linkedin_url: nullable(values.linkedin_url),
    github_url: nullable(values.github_url),
    portfolio_url: nullable(values.portfolio_url),
    resume_text: nullable(values.resume_text),
  }
}

function Field({
  id,
  label,
  hint,
  error,
  children,
  className,
}: {
  id: string
  label: string
  hint?: string
  error?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <div className="space-y-2">
        <Label htmlFor={id}>{label}</Label>
        {children}
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        <FieldError message={error} />
      </div>
    </div>
  )
}

export function ProfileForm({
  candidate,
  defaultEmail,
}: {
  candidate: Candidate | null
  defaultEmail?: string
}) {
  const queryClient = useQueryClient()
  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: toFormValues(candidate, defaultEmail),
  })

  useEffect(() => {
    form.reset(toFormValues(candidate, defaultEmail))
  }, [candidate, defaultEmail, form])

  const save = useMutation({
    mutationFn: (values: ProfileFormValues) => {
      const payload = toPayload(values)
      return candidate
        ? api.candidates.update(candidate.id, payload)
        : api.candidates.create(payload)
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.candidate, saved)
      // Preferences feed the matcher, so cached scores may be stale.
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all })
      toast.success(candidate ? 'Profile saved' : 'Profile created')
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        for (const [field, message] of Object.entries(error.fieldErrors)) {
          if (field in profileSchema.shape) {
            form.setError(field as keyof ProfileFormValues, { message })
          }
        }
      }
      toast.error('Could not save profile', { description: error.message })
    },
  })

  const errors = form.formState.errors
  const onSubmit = form.handleSubmit((values) => save.mutate(values))

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Basics</CardTitle>
          <CardDescription>Used on generated resumes and cover letters.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field id="full_name" label="Full name" error={errors.full_name?.message}>
            <Input id="full_name" autoComplete="name" {...form.register('full_name')} aria-invalid={!!errors.full_name} />
          </Field>
          <Field id="email" label="Contact email" error={errors.email?.message} hint="Also where job digests are sent.">
            <Input id="email" type="email" {...form.register('email')} aria-invalid={!!errors.email} />
          </Field>
          <Field id="phone" label="Phone" error={errors.phone?.message}>
            <Input id="phone" autoComplete="tel" {...form.register('phone')} />
          </Field>
          <Field id="location" label="Current location" error={errors.location?.message}>
            <Input id="location" {...form.register('location')} />
          </Field>
          <Field id="headline" label="Headline" error={errors.headline?.message} className="sm:col-span-2">
            <Input id="headline" placeholder="e.g. Senior Backend Engineer" {...form.register('headline')} />
          </Field>
          <Field id="summary" label="Professional summary" error={errors.summary?.message} className="sm:col-span-2">
            <Textarea id="summary" rows={4} {...form.register('summary')} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Preferences</CardTitle>
          <CardDescription>The matcher compares these with each job. Separate multiple values with commas.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field id="preferred_job_titles" label="Preferred job titles" className="sm:col-span-2">
            <Input id="preferred_job_titles" placeholder="Backend Developer, Python Engineer" {...form.register('preferred_job_titles')} />
          </Field>
          <Field id="preferred_locations" label="Preferred locations">
            <Input id="preferred_locations" placeholder="India, Remote" {...form.register('preferred_locations')} />
          </Field>
          <Field id="preferred_work_modes" label="Preferred work modes">
            <Input id="preferred_work_modes" placeholder="Remote, Hybrid" {...form.register('preferred_work_modes')} />
          </Field>
          <Field id="preferred_employment_types" label="Preferred employment types">
            <Input id="preferred_employment_types" placeholder="Full-time, Contract" {...form.register('preferred_employment_types')} />
          </Field>
          <Field id="years_experience" label="Years of experience" error={errors.years_experience?.message}>
            <Input id="years_experience" inputMode="decimal" {...form.register('years_experience')} aria-invalid={!!errors.years_experience} />
          </Field>
          <Field id="minimum_salary" label="Minimum salary (yearly)" error={errors.minimum_salary?.message}>
            <Input id="minimum_salary" inputMode="numeric" {...form.register('minimum_salary')} aria-invalid={!!errors.minimum_salary} />
          </Field>
          <Field id="salary_currency" label="Salary currency" error={errors.salary_currency?.message}>
            <Input id="salary_currency" maxLength={3} className="uppercase" {...form.register('salary_currency')} aria-invalid={!!errors.salary_currency} />
          </Field>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Controller
              control={form.control}
              name="remote_only"
              render={({ field }) => (
                <Switch id="remote_only" checked={field.value} onCheckedChange={field.onChange} />
              )}
            />
            <Label htmlFor="remote_only">Remote roles only</Label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Links</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <Field id="linkedin_url" label="LinkedIn" error={errors.linkedin_url?.message}>
            <Input id="linkedin_url" type="url" placeholder="https://linkedin.com/in/…" {...form.register('linkedin_url')} aria-invalid={!!errors.linkedin_url} />
          </Field>
          <Field id="github_url" label="GitHub" error={errors.github_url?.message}>
            <Input id="github_url" type="url" placeholder="https://github.com/…" {...form.register('github_url')} aria-invalid={!!errors.github_url} />
          </Field>
          <Field id="portfolio_url" label="Portfolio" error={errors.portfolio_url?.message}>
            <Input id="portfolio_url" type="url" placeholder="https://…" {...form.register('portfolio_url')} aria-invalid={!!errors.portfolio_url} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Resume text</CardTitle>
          <CardDescription>
            The original resume used for matching and tailoring. Uploading a file above replaces this text. Tailoring never changes it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea id="resume_text" aria-label="Resume text" rows={12} className="font-mono text-xs" {...form.register('resume_text')} />
        </CardContent>
      </Card>

      <div className="sticky bottom-0 -mx-4 flex justify-end gap-2 border-t bg-background/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border">
        {candidate && (
          <Button
            type="button"
            variant="ghost"
            disabled={!form.formState.isDirty || save.isPending}
            onClick={() => form.reset(toFormValues(candidate, defaultEmail))}
          >
            Discard changes
          </Button>
        )}
        <Button type="submit" disabled={save.isPending || (!!candidate && !form.formState.isDirty)}>
          {save.isPending && <Spinner />}
          {candidate ? 'Save profile' : 'Create profile'}
        </Button>
      </div>
    </form>
  )
}
