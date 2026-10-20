import type { ApplicationStatus, DocumentType } from './types'

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

export function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateFormatter.format(date)
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateTimeFormatter.format(date)
}

export function formatRelative(value: string | null | undefined, now = new Date()) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'

  const days = Math.round((date.getTime() - now.getTime()) / 86_400_000)
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  if (Math.abs(days) < 1) {
    const hours = Math.round((date.getTime() - now.getTime()) / 3_600_000)
    return formatter.format(hours, 'hour')
  }
  if (Math.abs(days) < 30) return formatter.format(days, 'day')
  return formatDate(value)
}

/** Converts an ISO timestamp to the value of a date input (local date). */
export function toDateInputValue(value: string | null | undefined) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** Converts a date input value to an ISO timestamp at 09:00 local time. */
export function fromDateInputValue(value: string) {
  if (!value) return null
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day, 9, 0, 0).toISOString()
}

export function formatSalary(
  min: number | string | null | undefined,
  max: number | string | null | undefined,
  currency: string | null | undefined,
) {
  const toNumber = (value: number | string | null | undefined) =>
    value === null || value === undefined || value === '' ? null : Number(value)
  const low = toNumber(min)
  const high = toNumber(max)
  if (low === null && high === null) return null

  const format = (amount: number) =>
    new Intl.NumberFormat(undefined, {
      style: currency ? 'currency' : 'decimal',
      currency: currency || undefined,
      maximumFractionDigits: 0,
      notation: amount >= 100_000 ? 'compact' : 'standard',
    }).format(amount)

  if (low !== null && high !== null && low !== high) {
    return `${format(low)} – ${format(high)}`
  }
  return format((low ?? high) as number)
}

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  saved: 'Saved',
  preparing: 'Preparing',
  applied: 'Applied',
  interviewing: 'Interviewing',
  offer: 'Offer',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
}

export const DOCUMENT_LABELS: Record<DocumentType, string> = {
  tailored_resume: 'Tailored resume',
  cover_letter: 'Cover letter',
}

export function documentLabel(type: string) {
  return DOCUMENT_LABELS[type as DocumentType] ?? type.replace(/_/g, ' ')
}

export const WORK_MODE_LABELS: Record<string, string> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'On-site',
}

export function workModeLabel(value: string | null | undefined) {
  if (!value) return null
  return WORK_MODE_LABELS[value.toLowerCase()] ?? value
}

export function splitList(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function joinList(value: string[] | null | undefined) {
  return (value ?? []).join(', ')
}

export function isOverdue(followUpAt: string | null, now = new Date()) {
  return !!followUpAt && new Date(followUpAt).getTime() < now.getTime()
}

export const ACTIVE_STATUSES: ApplicationStatus[] = [
  'saved',
  'preparing',
  'applied',
  'interviewing',
]
