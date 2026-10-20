import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, Copy, Download, FileText, ShieldCheck, Wand2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { DraftBadge } from '@/components/badges'
import { EmptyState, ErrorState, ListSkeleton, Spinner } from '@/components/common'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api } from '@/lib/api'
import { documentLabel, formatDateTime } from '@/lib/format'
import { queryKeys } from '@/lib/query-keys'
import type { ApplicationDocument, Candidate, DocumentType } from '@/lib/types'

export const VERIFY_ITEMS = [
  'Dates and employment periods',
  'Skills and technologies claimed',
  'Job titles and employers',
  'Responsibilities and scope',
  'Achievements and metrics',
  'Contact information',
]

export function useApplicationDocuments(applicationId: string | undefined, candidateId: string) {
  return useQuery({
    queryKey: queryKeys.applications.documents(applicationId ?? 'none'),
    queryFn: () => api.applications.documents(applicationId as string, candidateId),
    enabled: !!applicationId,
  })
}

/** Groups documents by type, newest version first (as the API orders them). */
export function groupDocuments(documents: ApplicationDocument[]) {
  const groups = new Map<string, ApplicationDocument[]>()
  for (const document of documents) {
    const list = groups.get(document.document_type) ?? []
    list.push(document)
    groups.set(document.document_type, list)
  }
  for (const list of groups.values()) list.sort((a, b) => b.version - a.version)
  return groups
}

function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function DocumentReview({
  document,
  candidateId,
}: {
  document: ApplicationDocument
  candidateId: string
}) {
  const queryClient = useQueryClient()
  const metadata = document.generation_metadata ?? {}
  const warnings = Array.isArray(metadata.warnings) ? metadata.warnings : []
  const changes = Array.isArray(metadata.changes_summary) ? metadata.changes_summary : []
  const content = document.content_text ?? ''

  const approve = useMutation({
    mutationFn: () =>
      api.applications.approveDocument(document.application_id, document.id, candidateId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.applications.documents(document.application_id),
      })
      void queryClient.invalidateQueries({ queryKey: queryKeys.applications.all })
      toast.success(`${documentLabel(document.document_type)} v${document.version} approved`)
    },
    onError: (error) => toast.error('Approval failed', { description: `${error.message} The document is still a draft.` }),
  })

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      toast.success('Copied to clipboard')
    } catch {
      toast.error('Could not copy. Select the text and copy it manually.')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <DraftBadge approved={document.is_approved} />
        <span className="text-sm text-muted-foreground">
          Version {document.version} · generated {formatDateTime((metadata.generated_at as string) ?? document.created_at)}
          {metadata.model ? ` · ${metadata.model}` : ''}
        </span>
        {document.is_approved && document.approved_at && (
          <span className="text-sm text-muted-foreground">· approved {formatDateTime(document.approved_at)}</span>
        )}
      </div>

      {warnings.length > 0 && (
        <Alert className="border-amber-200 bg-amber-50 text-amber-900">
          <AlertTriangle />
          <AlertTitle>Generation warnings</AlertTitle>
          <AlertDescription className="text-amber-900">
            <ul className="list-disc space-y-0.5 pl-4">
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {changes.length > 0 && (
        <details className="rounded-lg border px-3 py-2 text-sm">
          <summary className="cursor-pointer font-medium">What the AI changed ({changes.length})</summary>
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-muted-foreground">
            {changes.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        </details>
      )}

      <div
        className="max-h-[32rem] overflow-y-auto rounded-lg border bg-background p-4 text-sm leading-relaxed whitespace-pre-wrap"
        aria-label={`${documentLabel(document.document_type)} content`}
        tabIndex={0}
      >
        {content || <span className="text-muted-foreground">This document has no text.</span>}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={copy} disabled={!content}>
          <Copy /> Copy text
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!content}
          onClick={() => downloadText(`${document.document_type}-v${document.version}.txt`, content)}
        >
          <Download /> Download .txt
        </Button>
        <div className="ml-auto">
          {document.is_approved ? (
            <span className="inline-flex items-center gap-1.5 text-sm text-emerald-700">
              <ShieldCheck className="size-4" /> Approved by you
            </span>
          ) : (
            <ConfirmDialog
              trigger={
                <Button size="sm" disabled={approve.isPending || !content}>
                  {approve.isPending ? <Spinner /> : <Check />}
                  Approve version {document.version}
                </Button>
              }
              title={`Approve this ${documentLabel(document.document_type).toLowerCase()}?`}
              description="Approval records that you reviewed this version and it is accurate. It does not submit anything; you still apply yourself."
              confirmLabel="I verified it — approve"
              onConfirm={() => approve.mutate()}
            >
              <div className="rounded-md border bg-muted/40 p-3 text-sm">
                <p className="mb-1.5 font-medium">Confirm you checked:</p>
                <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">
                  {VERIFY_ITEMS.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </ConfirmDialog>
          )}
        </div>
      </div>
    </div>
  )
}

function DocumentGroup({
  versions,
  candidateId,
}: {
  versions: ApplicationDocument[]
  candidateId: string
}) {
  const [selectedId, setSelectedId] = useState(versions[0].id)
  const selected = versions.find((item) => item.id === selectedId) ?? versions[0]

  return (
    <div className="space-y-3">
      {versions.length > 1 && (
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Versions">
          {versions.map((version) => (
            <Button
              key={version.id}
              size="xs"
              variant={version.id === selected.id ? 'secondary' : 'ghost'}
              aria-pressed={version.id === selected.id}
              onClick={() => setSelectedId(version.id)}
            >
              v{version.version}
              {version.is_approved && <Check className="text-emerald-600" />}
            </Button>
          ))}
        </div>
      )}
      <DocumentReview key={selected.id} document={selected} candidateId={candidateId} />
    </div>
  )
}

export function generationBlockers(
  type: DocumentType,
  candidate: Candidate,
  job: { is_active: boolean; description: string | null },
): string | null {
  if (!job.is_active) return 'This job is no longer active.'
  if (type === 'tailored_resume') {
    if (!candidate.resume_text?.trim()) return 'Add your resume on the Profile page first.'
    if (!job.description?.trim()) return 'This job has no description to tailor against.'
  } else if (
    !candidate.resume_text?.trim() &&
    !candidate.summary?.trim() &&
    !candidate.headline?.trim()
  ) {
    return 'Add a resume, summary, or headline on the Profile page first.'
  }
  return null
}

export function DocumentsPanel({
  applicationId,
  candidate,
  job,
}: {
  applicationId: string | undefined
  candidate: Candidate
  job: { id: string; is_active: boolean; description: string | null }
}) {
  const queryClient = useQueryClient()
  const documents = useApplicationDocuments(applicationId, candidate.id)

  const onGenerated = (label: string) => {
    // Generation creates the application when needed, so refresh both.
    void queryClient.invalidateQueries({ queryKey: queryKeys.applications.all })
    toast.success(`${label} draft generated`, {
      description: 'Review it carefully before approving.',
    })
  }

  const tailor = useMutation({
    mutationFn: () => api.applications.tailorResume(candidate.id, job.id),
    onSuccess: () => onGenerated('Tailored resume'),
    onError: (error) => toast.error('Resume tailoring failed', { description: error.message }),
  })

  const coverLetter = useMutation({
    mutationFn: () => api.applications.generateCoverLetter(candidate.id, job.id),
    onSuccess: () => onGenerated('Cover letter'),
    onError: (error) => toast.error('Cover letter generation failed', { description: error.message }),
  })

  const busy = tailor.isPending || coverLetter.isPending
  const resumeBlocker = generationBlockers('tailored_resume', candidate, job)
  const letterBlocker = generationBlockers('cover_letter', candidate, job)
  const groups = documents.data ? groupDocuments(documents.data) : new Map()
  const types = (['tailored_resume', 'cover_letter'] as const).filter((type) => groups.has(type))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Application documents</CardTitle>
        <CardDescription>
          AI drafts based on your stored resume and this job. They can contain mistakes and stay drafts until you approve them. Your original resume is never changed.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={busy || !!resumeBlocker}
            title={resumeBlocker ?? undefined}
            onClick={() => tailor.mutate()}
          >
            {tailor.isPending ? <Spinner /> : <Wand2 />}
            {tailor.isPending ? 'Tailoring resume…' : 'Generate tailored resume'}
          </Button>
          <Button
            variant="outline"
            disabled={busy || !!letterBlocker}
            title={letterBlocker ?? undefined}
            onClick={() => coverLetter.mutate()}
          >
            {coverLetter.isPending ? <Spinner /> : <FileText />}
            {coverLetter.isPending ? 'Writing cover letter…' : 'Generate cover letter'}
          </Button>
        </div>
        {(resumeBlocker || letterBlocker) && (
          <p className="text-xs text-muted-foreground">{resumeBlocker ?? letterBlocker}</p>
        )}
        {busy && (
          <p className="text-xs text-muted-foreground" role="status">
            Waiting for the AI provider. This usually takes 10–30 seconds.
          </p>
        )}

        {!applicationId ? (
          <EmptyState title="No documents yet" description="Generating a document also starts tracking this job as a saved application." />
        ) : documents.isPending ? (
          <ListSkeleton rows={2} />
        ) : documents.isError ? (
          <ErrorState title="Could not load documents" error={documents.error} onRetry={() => documents.refetch()} />
        ) : types.length === 0 ? (
          <EmptyState title="No documents yet" description="Generate a tailored resume or cover letter above." />
        ) : (
          <Tabs defaultValue={types[0]}>
            <TabsList>
              {types.map((type) => (
                <TabsTrigger key={type} value={type}>
                  {documentLabel(type)}
                </TabsTrigger>
              ))}
            </TabsList>
            {types.map((type) => (
              <TabsContent key={type} value={type} className="pt-3">
                <DocumentGroup
                  key={groups.get(type)[0].id}
                  versions={groups.get(type)}
                  candidateId={candidate.id}
                />
              </TabsContent>
            ))}
          </Tabs>
        )}
      </CardContent>
    </Card>
  )
}
