import { Badge } from '@/components/ui/badge'
import { STATUS_LABELS } from '@/lib/format'
import type { ApplicationStatus } from '@/lib/types'
import { cn } from '@/lib/utils'

const STATUS_STYLES: Record<ApplicationStatus, string> = {
  saved: 'bg-muted text-foreground',
  preparing: 'bg-amber-50 text-amber-800 border-amber-200',
  applied: 'bg-sky-50 text-sky-800 border-sky-200',
  interviewing: 'bg-violet-50 text-violet-800 border-violet-200',
  offer: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  rejected: 'bg-rose-50 text-rose-800 border-rose-200',
  withdrawn: 'bg-muted text-muted-foreground',
}

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <Badge variant="outline" className={cn(STATUS_STYLES[status])}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  )
}

export function scoreTone(score: number) {
  if (score >= 70) return 'bg-emerald-50 text-emerald-800 border-emerald-200'
  if (score >= 50) return 'bg-amber-50 text-amber-800 border-amber-200'
  return 'bg-muted text-muted-foreground'
}

/** Rules-based match score from the backend matcher (0–100). */
export function ScoreBadge({ score, className }: { score: number | null; className?: string }) {
  if (score === null || score === undefined) {
    return (
      <Badge variant="outline" className={cn('text-muted-foreground', className)}>
        Not scored
      </Badge>
    )
  }
  return (
    <Badge
      variant="outline"
      className={cn('tabular-nums', scoreTone(score), className)}
      title="Rules-based match score"
    >
      {Math.round(score)} match
    </Badge>
  )
}

export function DraftBadge({ approved }: { approved: boolean }) {
  return approved ? (
    <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-800">
      Approved
    </Badge>
  ) : (
    <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
      Draft
    </Badge>
  )
}
