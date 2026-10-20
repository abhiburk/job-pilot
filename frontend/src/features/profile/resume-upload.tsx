import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileUp } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { Spinner } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { queryKeys } from '@/lib/query-keys'
import type { Candidate, ResumeUploadResult } from '@/lib/types'

// Mirrors MAX_RESUME_SIZE and the extension check in the backend.
const MAX_BYTES = 5 * 1024 * 1024
const ACCEPTED = ['.pdf', '.docx']

export function validateResumeFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ACCEPTED.some((extension) => name.endsWith(extension))) {
    return 'Only PDF and DOCX resumes are supported.'
  }
  if (file.size > MAX_BYTES) return 'Resume must not exceed 5 MB.'
  if (file.size === 0) return 'This file is empty.'
  return null
}

export function ResumeUpload({ candidate }: { candidate: Candidate }) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [result, setResult] = useState<ResumeUploadResult | null>(null)

  const upload = useMutation({
    mutationFn: (file: File) => api.candidates.uploadResume(candidate.id, file),
    onSuccess: (data) => {
      setResult(data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.candidate })
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills(candidate.id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all })
      toast.success('Resume processed', {
        description: `${data.skills_added} new skills, ${data.jobs_processed} jobs re-matched.`,
      })
    },
    onError: (error) => toast.error('Upload failed', { description: error.message }),
  })

  const onFile = (file: File | undefined) => {
    if (!file) return
    const problem = validateResumeFile(file)
    if (problem) {
      toast.error('Cannot upload this file', { description: problem })
      return
    }
    upload.mutate(file)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Resume file</CardTitle>
        <CardDescription>
          Upload a PDF or DOCX (max 5 MB). The text is extracted and stored, skills are detected, and jobs are re-matched. The file itself is not kept.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="sr-only"
            id="resume-file"
            onChange={(event) => {
              onFile(event.target.files?.[0])
              event.target.value = ''
            }}
          />
          <Button
            type="button"
            variant="outline"
            disabled={upload.isPending}
            onClick={() => inputRef.current?.click()}
          >
            {upload.isPending ? <Spinner /> : <FileUp />}
            {upload.isPending ? 'Processing…' : candidate.resume_text ? 'Replace resume' : 'Upload resume'}
          </Button>
          <span className="text-sm text-muted-foreground">
            {candidate.resume_text
              ? `${candidate.resume_text.length.toLocaleString()} characters stored · updated ${formatDateTime(candidate.updated_at)}`
              : 'No resume stored yet.'}
          </span>
        </div>
        {result && (
          <p className="text-sm text-muted-foreground" role="status">
            Extracted {result.characters_extracted.toLocaleString()} characters · {result.skills_found} skills found ({result.skills_added} new) · {result.jobs_processed} jobs re-matched.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
