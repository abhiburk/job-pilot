import { zodResolver } from '@hookform/resolvers/zod'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { useAuth } from '@/auth/auth-context'
import { safeNextPath } from '@/auth/guards'
import { FieldError, Spinner } from '@/components/common'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, api } from '@/lib/api'

export const PASSWORD_MIN_LENGTH = 10

const passwordSchema = z
  .string()
  .min(PASSWORD_MIN_LENGTH, `Use at least ${PASSWORD_MIN_LENGTH} characters`)
  .max(128, 'Use at most 128 characters')

export const loginSchema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
})

export const registerSchema = z
  .object({
    full_name: z.string().max(150).optional(),
    email: z.email('Enter a valid email address'),
    password: passwordSchema,
    confirm: z.string(),
  })
  .refine((values) => values.password === values.confirm, {
    path: ['confirm'],
    message: 'Passwords do not match',
  })

function AuthLayout({
  title,
  description,
  children,
  footer,
}: {
  title: string
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="flex min-h-svh items-center justify-center bg-muted/40 px-4 py-10">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex items-center justify-center gap-2 font-semibold tracking-tight">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-xs text-primary-foreground">
            JP
          </span>
          JobPilot
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </CardHeader>
          <CardContent>{children}</CardContent>
          {footer && (
            <CardFooter className="justify-center text-sm text-muted-foreground">
              {footer}
            </CardFooter>
          )}
        </Card>
      </div>
    </div>
  )
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 429 && error.retryAfter) {
    const minutes = Math.ceil(error.retryAfter / 60)
    return `${error.message} (about ${minutes} minute${minutes === 1 ? '' : 's'})`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [formError, setFormError] = useState<string | null>(null)
  const location = useLocation()
  const expired = params.get('expired') === '1'
  const passwordReset = (location.state as { passwordReset?: boolean } | null)?.passwordReset
  const next = safeNextPath(params.get('next'))

  const form = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null)
    try {
      await login(values.email, values.password)
      navigate(next, { replace: true })
    } catch (error) {
      setFormError(errorMessage(error))
    }
  })

  const registerHref = params.get('next')
    ? `/register?next=${encodeURIComponent(next)}`
    : '/register'

  return (
    <AuthLayout
      title="Sign in"
      description="Sign in to manage your job search."
      footer={
        <span>
          No account?{' '}
          <Link to={registerHref} className="font-medium text-foreground underline-offset-4 hover:underline">
            Create one
          </Link>
        </span>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {expired && !formError && (
          <Alert>
            <AlertCircle />
            <AlertDescription>Your session ended. Sign in again to continue.</AlertDescription>
          </Alert>
        )}
        {passwordReset && !formError && (
          <Alert>
            <CheckCircle2 />
            <AlertDescription>Password updated. Sign in with your new password.</AlertDescription>
          </Alert>
        )}
        <FormError message={formError} />
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" autoFocus {...form.register('email')} aria-invalid={!!form.formState.errors.email} />
          <FieldError message={form.formState.errors.email?.message} />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link to="/forgot-password" className="text-xs text-muted-foreground underline-offset-4 hover:underline">
              Forgot password?
            </Link>
          </div>
          <Input id="password" type="password" autoComplete="current-password" {...form.register('password')} aria-invalid={!!form.formState.errors.password} />
          <FieldError message={form.formState.errors.password?.message} />
        </div>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Spinner />}
          Sign in
        </Button>
      </form>
    </AuthLayout>
  )
}

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [formError, setFormError] = useState<string | null>(null)

  const form = useForm<z.infer<typeof registerSchema>>({
    resolver: zodResolver(registerSchema),
    defaultValues: { full_name: '', email: '', password: '', confirm: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null)
    try {
      await register({
        email: values.email,
        password: values.password,
        full_name: values.full_name || undefined,
      })
      const next = params.get('next')
      navigate(next ? safeNextPath(next) : '/profile', { replace: true })
    } catch (error) {
      setFormError(errorMessage(error))
    }
  })

  const errors = form.formState.errors

  return (
    <AuthLayout
      title="Create your account"
      description="Your profile, matches, and documents stay private to your account."
      footer={
        <span>
          Already registered?{' '}
          <Link to="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
            Sign in
          </Link>
        </span>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <FormError message={formError} />
        <div className="space-y-2">
          <Label htmlFor="full_name">Name <span className="text-muted-foreground">(optional)</span></Label>
          <Input id="full_name" autoComplete="name" {...form.register('full_name')} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" {...form.register('email')} aria-invalid={!!errors.email} />
          <FieldError message={errors.email?.message} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="new-password" {...form.register('password')} aria-invalid={!!errors.password} aria-describedby="password-hint" />
          <p id="password-hint" className="text-xs text-muted-foreground">At least {PASSWORD_MIN_LENGTH} characters.</p>
          <FieldError message={errors.password?.message} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm">Confirm password</Label>
          <Input id="confirm" type="password" autoComplete="new-password" {...form.register('confirm')} aria-invalid={!!errors.confirm} />
          <FieldError message={errors.confirm?.message} />
        </div>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Spinner />}
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}

export function ForgotPasswordPage() {
  const [sentMessage, setSentMessage] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<{ email: string }>({
    resolver: zodResolver(z.object({ email: z.email('Enter a valid email address') })),
    defaultValues: { email: '' },
  })

  const onSubmit = form.handleSubmit(async ({ email }) => {
    setFormError(null)
    try {
      const response = await api.auth.requestPasswordReset(email)
      setSentMessage(response.message)
    } catch (error) {
      setFormError(errorMessage(error))
    }
  })

  return (
    <AuthLayout
      title="Reset your password"
      description="We will email a reset link if an account exists for this address."
      footer={
        <Link to="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
      {sentMessage ? (
        <Alert>
          <CheckCircle2 />
          <AlertDescription>
            {sentMessage} The link expires in 60 minutes. Delivery requires SMTP to be configured on the server.
          </AlertDescription>
        </Alert>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormError message={formError} />
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" {...form.register('email')} aria-invalid={!!form.formState.errors.email} />
            <FieldError message={form.formState.errors.email?.message} />
          </div>
          <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting && <Spinner />}
            Send reset link
          </Button>
        </form>
      )}
    </AuthLayout>
  )
}

const resetSchema = z
  .object({ password: passwordSchema, confirm: z.string() })
  .refine((values) => values.password === values.confirm, {
    path: ['confirm'],
    message: 'Passwords do not match',
  })

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') ?? ''
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<z.infer<typeof resetSchema>>({
    resolver: zodResolver(resetSchema),
    defaultValues: { password: '', confirm: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null)
    try {
      await api.auth.confirmPasswordReset(token, values.password)
      navigate('/login', { replace: true, state: { passwordReset: true } })
    } catch (error) {
      setFormError(errorMessage(error))
    }
  })

  if (!token) {
    return (
      <AuthLayout title="Reset link missing">
        <p className="text-sm text-muted-foreground">
          Open the link from your email, or{' '}
          <Link to="/forgot-password" className="underline">request a new one</Link>.
        </p>
      </AuthLayout>
    )
  }

  const errors = form.formState.errors
  return (
    <AuthLayout title="Choose a new password" description="Signing in again is required on all devices afterwards.">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <FormError message={formError} />
        <div className="space-y-2">
          <Label htmlFor="password">New password</Label>
          <Input id="password" type="password" autoComplete="new-password" {...form.register('password')} aria-invalid={!!errors.password} />
          <FieldError message={errors.password?.message} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm">Confirm new password</Label>
          <Input id="confirm" type="password" autoComplete="new-password" {...form.register('confirm')} aria-invalid={!!errors.confirm} />
          <FieldError message={errors.confirm?.message} />
        </div>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Spinner />}
          Update password
        </Button>
      </form>
    </AuthLayout>
  )
}
