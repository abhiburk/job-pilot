import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, Trash2 } from 'lucide-react'
import { useEffect } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { StatusBadge } from '@/components/badges'
import { ErrorState, FieldError, ListSkeleton, Spinner } from '@/components/common'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { WithCandidate } from '@/hooks/use-candidate'
import { ApiError, api } from '@/lib/api'
import {
  STATUS_LABELS,
  formatDate,
  formatDateTime,
  fromDateInputValue,
  toDateInputValue,
} from '@/lib/format'
import { queryKeys } from '@/lib/query-keys'
import { APPLICATION_STATUSES } from '@/lib/types'
import type { ApplicationListItem, ApplicationUpdate, Candidate } from '@/lib/types'
import { DocumentsPanel } from './documents'

export const applicationFormSchema = z.object({
  status: z.enum(APPLICATION_STATUSES),
  applied_at: z.string(),
  follow_up_at: z.string(),
  application_url: z
    .string()
    .refine((value) => !value || /^https?:\/\/\S+$/i.test(value), 'Enter a full URL starting with https://'),
  notes: z.string().max(10_000),
})

type FormValues = z.infer<typeof applicationFormSchema>

function toValues(item: ApplicationListItem): FormValues {
  return {
    status: item.status,
    applied_at: toDateInputValue(item.applied_at),
    follow_up_at: toDateInputValue(item.follow_up_at),
    application_url: item.application_url ?? '',
    notes: item.notes ?? '',
  }
}

/** Only fields the user changed are sent, so the backend's defaults apply. */
export function changedFields(initial: FormValues, values: FormValues): ApplicationUpdate {
  const update: ApplicationUpdate = {}
  if (values.status !== initial.status) update.status = values.status
  if (values.applied_at !== initial.applied_at) update.applied_at = fromDateInputValue(values.applied_at)
  if (values.follow_up_at !== initial.follow_up_at) update.follow_up_at = fromDateInputValue(values.follow_up_at)
  if (values.application_url !== initial.application_url) update.application_url = values.application_url.trim() || null
  if (values.notes !== initial.notes) update.notes = values.notes.trim() ? values.notes : null
  return update
}

function TrackingForm({ application, candidate }: { application: ApplicationListItem; candidate: Candidate }) {
  const queryClient = useQueryClient()
  const form = useForm<FormValues>({
    resolver: zodResolver(applicationFormSchema),
    defaultValues: toValues(application),
  })

  useEffect(() => {
    form.reset(toValues(application))
  }, [application, form])

  const save = useMutation({
    mutationFn: (update: ApplicationUpdate) =>
      api.applications.update(application.id, candidate.id, update),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.applications.all })
      toast.success('Application updated')
    },
    onError: (error) => toast.error('Could not update application', { description: error.message }),
  })

  const onSubmit = form.handleSubmit((values) => {
    const update = changedFields(toValues(application), values)
    if (Object.keys(update).length) save.mutate(update)
  })

  const errors = form.formState.errors
  const status = form.watch('status')

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Tracking</CardTitle>
        <CardDescription>
          Mark it “Applied” after you submit the application yourself. JobPilot never submits applications.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form noValidate onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="status">Status</Label>
            <Controller
              control={form.control}
              name="status"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="status" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {APPLICATION_STATUSES.map((value) => (
                      <SelectItem key={value} value={value}>{STATUS_LABELS[value]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {status === 'applied' && application.status !== 'applied' && !form.watch('applied_at') && (
              <p className="text-xs text-muted-foreground">The applied date will be set to now unless you pick one.</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="follow_up_at">Follow-up date</Label>
            <Input id="follow_up_at" type="date" {...form.register('follow_up_at')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="applied_at">Applied on</Label>
            <Input id="applied_at" type="date" {...form.register('applied_at')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="application_url">Application URL</Label>
            <Input id="application_url" type="url" {...form.register('application_url')} aria-invalid={!!errors.application_url} />
            <FieldError message={errors.application_url?.message} />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={4} placeholder="Recruiter contact, interview notes, next steps…" {...form.register('notes')} />
          </div>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <Button type="button" variant="ghost" disabled={!form.formState.isDirty || save.isPending} onClick={() => form.reset(toValues(application))}>
              Discard
            </Button>
            <Button type="submit" disabled={!form.formState.isDirty || save.isPending}>
              {save.isPending && <Spinner />}
              Save changes
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function ApplicationDetail({ applicationId, candidate }: { applicationId: string; candidate: Candidate }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const application = useQuery({
    queryKey: queryKeys.applications.detail(applicationId),
    queryFn: () => api.applications.get(applicationId, candidate.id),
  })

  const job = useQuery({
    queryKey: queryKeys.jobs.detail(application.data?.job_id ?? 'none', candidate.id),
    queryFn: () => api.jobs.get(application.data!.job_id, candidate.id),
    enabled: !!application.data,
  })

  const remove = useMutation({
    mutationFn: () => api.applications.remove(applicationId, candidate.id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: queryKeys.applications.detail(applicationId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.applications.all })
      toast.success('Application deleted')
      navigate('/applications', { replace: true })
    },
    onError: (error) => toast.error('Could not delete application', { description: error.message }),
  })

  if (application.isPending) return <ListSkeleton rows={4} />
  if (application.isError) {
    const notFound = application.error instanceof ApiError && application.error.status === 404
    return (
      <ErrorState
        title={notFound ? 'Application not found' : 'Could not load application'}
        error={application.error}
        onRetry={notFound ? undefined : () => application.refetch()}
      />
    )
  }

  const item = application.data

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{item.job_title}</h1>
            <StatusBadge status={item.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {[item.company_name, item.job_location].filter(Boolean).join(' · ') || 'Company not listed'}
          </p>
          <p className="text-xs text-muted-foreground">
            Tracked since {formatDate(item.created_at)} · updated {formatDateTime(item.updated_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline" size="sm">
            <Link to={`/jobs/${item.job_id}`}>Job details</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={item.application_url || item.job_url} target="_blank" rel="noopener noreferrer nofollow">
              Apply on site <ExternalLink />
            </a>
          </Button>
          <ConfirmDialog
            trigger={
              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" disabled={remove.isPending}>
                <Trash2 /> Delete
              </Button>
            }
            title="Delete this application?"
            description="This permanently removes the application, its notes, and all generated documents. The job stays in your job list."
            confirmLabel="Delete application"
            destructive
            onConfirm={() => remove.mutate()}
          />
        </div>
      </div>

      <TrackingForm application={item} candidate={candidate} />

      {job.isPending ? (
        <ListSkeleton rows={2} />
      ) : job.isError ? (
        <ErrorState title="Could not load the job for document generation" error={job.error} onRetry={() => job.refetch()} />
      ) : (
        <DocumentsPanel applicationId={item.id} candidate={candidate} job={job.data} />
      )}
    </div>
  )
}

export function ApplicationDetailPage() {
  const { applicationId = '' } = useParams()
  return (
    <>
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-2">
        <Link to="/applications"><ArrowLeft /> All applications</Link>
      </Button>
      <WithCandidate>
        {(candidate) => <ApplicationDetail applicationId={applicationId} candidate={candidate} />}
      </WithCandidate>
    </>
  )
}
