import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2, LogOut, XCircle } from 'lucide-react'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { useAuth } from '@/auth/auth-context'
import { FieldError, PageHeader, Spinner } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { PASSWORD_MIN_LENGTH } from '@/features/auth/auth-pages'
import { useJobSources } from '@/hooks/use-job-sources'
import { API_BASE_URL, ApiError, api } from '@/lib/api'
import { formatDate, formatRelative } from '@/lib/format'
import { queryKeys } from '@/lib/query-keys'

const accountSchema = z.object({
  full_name: z.string().max(150),
  email: z.email('Enter a valid email address'),
  current_password: z.string(),
})

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: z.string().min(PASSWORD_MIN_LENGTH, `Use at least ${PASSWORD_MIN_LENGTH} characters`).max(128),
    confirm: z.string(),
  })
  .refine((values) => values.new_password === values.confirm, {
    path: ['confirm'],
    message: 'Passwords do not match',
  })

function AccountCard() {
  const { user, setUser } = useAuth()
  const form = useForm<z.infer<typeof accountSchema>>({
    resolver: zodResolver(accountSchema),
    defaultValues: { full_name: user?.full_name ?? '', email: user?.email ?? '', current_password: '' },
  })

  useEffect(() => {
    form.reset({ full_name: user?.full_name ?? '', email: user?.email ?? '', current_password: '' })
  }, [user, form])

  const emailChanged = form.watch('email').trim().toLowerCase() !== (user?.email ?? '')

  const save = useMutation({
    mutationFn: (values: z.infer<typeof accountSchema>) =>
      api.auth.updateAccount({
        full_name: values.full_name.trim() || null,
        ...(emailChanged ? { email: values.email, current_password: values.current_password } : {}),
      }),
    onSuccess: (updated) => {
      setUser(updated)
      toast.success('Account updated')
    },
    onError: (error) => toast.error('Could not update account', { description: error.message }),
  })

  const errors = form.formState.errors
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Account</CardTitle>
        <CardDescription>
          Your sign-in details. Member since {formatDate(user?.created_at)}. The contact email on generated documents is set on your Profile.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form noValidate className="grid gap-4 sm:grid-cols-2" onSubmit={form.handleSubmit((values) => save.mutate(values))}>
          <div className="space-y-2">
            <Label htmlFor="account-name">Name</Label>
            <Input id="account-name" autoComplete="name" {...form.register('full_name')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="account-email">Sign-in email</Label>
            <Input id="account-email" type="email" autoComplete="email" {...form.register('email')} aria-invalid={!!errors.email} />
            <FieldError message={errors.email?.message} />
          </div>
          {emailChanged && (
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="account-password">Current password (required to change email)</Label>
              <Input id="account-password" type="password" autoComplete="current-password" {...form.register('current_password')} />
            </div>
          )}
          <div className="flex justify-end sm:col-span-2">
            <Button type="submit" disabled={!form.formState.isDirty || save.isPending}>
              {save.isPending && <Spinner />}
              Save account
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function PasswordCard() {
  const form = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: '', new_password: '', confirm: '' },
  })
  const change = useMutation({
    mutationFn: (values: z.infer<typeof passwordSchema>) =>
      api.auth.changePassword(values.current_password, values.new_password),
    onSuccess: () => {
      form.reset()
      toast.success('Password changed', { description: 'Other devices have been signed out.' })
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 400) {
        form.setError('current_password', { message: error.message })
      } else {
        toast.error('Could not change password', { description: error.message })
      }
    },
  })
  const errors = form.formState.errors

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Password</CardTitle>
        <CardDescription>Changing it signs out every other session.</CardDescription>
      </CardHeader>
      <CardContent>
        <form noValidate className="grid gap-4 sm:grid-cols-3" onSubmit={form.handleSubmit((values) => change.mutate(values))}>
          <div className="space-y-2">
            <Label htmlFor="current-password">Current password</Label>
            <Input id="current-password" type="password" autoComplete="current-password" {...form.register('current_password')} aria-invalid={!!errors.current_password} />
            <FieldError message={errors.current_password?.message} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new-password">New password</Label>
            <Input id="new-password" type="password" autoComplete="new-password" {...form.register('new_password')} aria-invalid={!!errors.new_password} />
            <FieldError message={errors.new_password?.message} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-password">Confirm new password</Label>
            <Input id="confirm-password" type="password" autoComplete="new-password" {...form.register('confirm')} aria-invalid={!!errors.confirm} />
            <FieldError message={errors.confirm?.message} />
          </div>
          <div className="flex justify-end sm:col-span-3">
            <Button type="submit" disabled={change.isPending}>
              {change.isPending && <Spinner />}
              Change password
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function StatusLine({ label, ok, pending, detail }: { label: string; ok: boolean; pending: boolean; detail?: string }) {
  return (
    <div className="flex items-center justify-between py-2 text-sm">
      <span>{label}</span>
      {pending ? (
        <Spinner className="text-muted-foreground" />
      ) : (
        <span className={ok ? 'flex items-center gap-1.5 text-emerald-700' : 'flex items-center gap-1.5 text-destructive'}>
          {ok ? <CheckCircle2 className="size-4" /> : <XCircle className="size-4" />}
          {detail ?? (ok ? 'Connected' : 'Unavailable')}
        </span>
      )}
    </div>
  )
}

function StatusCard() {
  const apiHealth = useQuery({ queryKey: [...queryKeys.health, 'api'], queryFn: api.health.api, retry: false })
  const dbHealth = useQuery({ queryKey: [...queryKeys.health, 'db'], queryFn: api.health.database, retry: false })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Service status</CardTitle>
        <CardDescription>API: {API_BASE_URL}</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        <StatusLine label="Backend API" ok={apiHealth.isSuccess} pending={apiHealth.isPending} />
        <StatusLine label="Database" ok={dbHealth.isSuccess} pending={dbHealth.isPending} />
        <div className="pt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void apiHealth.refetch()
              void dbHealth.refetch()
            }}
          >
            Check again
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function JobSourcesCard() {
  const sources = useJobSources()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Job sources</CardTitle>
        <CardDescription>
          Every connected source is searched together from Discover Jobs. Sources are added on the server; request limits follow each provider's terms.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sources.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : sources.isError ? (
          <p className="text-sm text-destructive">Could not load sources: {sources.error.message}</p>
        ) : (
          <ul className="divide-y">
            {sources.data.map((source) => (
              <li key={source.key} className="flex flex-col gap-1 py-2.5 text-sm sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                <div className="min-w-0">
                  <a href={source.homepage} target="_blank" rel="noopener noreferrer" className="font-medium hover:underline">
                    {source.label}
                  </a>
                  {!source.enabled && <span className="ml-2 text-xs text-muted-foreground">(disabled on server)</span>}
                  <p className="text-xs text-muted-foreground">{source.description}</p>
                  <p className="text-xs text-muted-foreground">
                    Filters: {source.supported_filters.join(', ').replace('work_mode', 'work mode') || 'none'}
                    {source.remote_only ? ' · remote jobs only' : ''}
                    {source.min_interval_minutes ? ` · at most one request every ${source.min_interval_minutes >= 60 ? `${source.min_interval_minutes / 60} h` : `${source.min_interval_minutes} min`}` : ''}
                  </p>
                </div>
                <div className="shrink-0 text-xs text-muted-foreground sm:text-right">
                  {source.last_run ? (
                    <>
                      <p className={source.last_run.status === 'failed' ? 'text-destructive' : undefined}>
                        Last run {formatRelative(source.last_run.started_at)}
                        {source.last_run.status === 'failed' ? ' (failed)' : source.last_run.created !== null ? ` · ${source.last_run.created} new` : ''}
                      </p>
                      {source.next_available_at && <p>Next run {formatRelative(source.next_available_at)}</p>}
                    </>
                  ) : (
                    <p>Not run yet</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function SettingsPage() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  return (
    <>
      <PageHeader title="Settings" />
      <div className="space-y-6">
        <AccountCard />
        <PasswordCard />
        <StatusCard />
        <JobSourcesCard />
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Job digests</CardTitle>
            <CardDescription>
              Digest emails are configured on the server (the JOB_DIGEST_* and SMTP_* settings) and sent to the contact email on your profile when the digest command runs. They cannot be changed from the browser.
            </CardDescription>
          </CardHeader>
        </Card>
        <div className="flex justify-end">
          <Button
            variant="outline"
            onClick={async () => {
              try {
                await logout()
                navigate('/login', { replace: true })
              } catch (error) {
                toast.error('Sign out failed', { description: error instanceof Error ? error.message : undefined })
              }
            }}
          >
            <LogOut /> Sign out
          </Button>
        </div>
      </div>
    </>
  )
}
