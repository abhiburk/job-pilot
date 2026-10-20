import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus, Star, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { EmptyState, ErrorState, FieldError, ListSkeleton, Spinner } from '@/components/common'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import type { CandidateSkill } from '@/lib/types'

const yearsField = z.string().refine((value) => {
  if (!value.trim()) return true
  const number = Number(value)
  return Number.isFinite(number) && number >= 0 && number <= 60
}, 'Enter a number between 0 and 60')

export const skillSchema = z.object({
  name: z.string().trim().min(1, 'Skill name is required').max(100),
  category: z.string().max(100),
  proficiency: z.string().max(50),
  years_experience: yearsField,
  is_primary: z.boolean(),
})

type SkillValues = z.infer<typeof skillSchema>

const editSchema = skillSchema.pick({ proficiency: true, years_experience: true, is_primary: true })
type EditValues = z.infer<typeof editSchema>

const toYears = (value: string) => (value.trim() ? Number(value) : null)

function EditSkillDialog({
  candidateId,
  skill,
  onClose,
}: {
  candidateId: string
  skill: CandidateSkill
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      proficiency: skill.proficiency ?? '',
      years_experience: skill.years_experience === null ? '' : String(skill.years_experience),
      is_primary: skill.is_primary,
    },
  })

  const update = useMutation({
    mutationFn: (values: EditValues) =>
      api.skills.update(candidateId, skill.id, {
        proficiency: values.proficiency.trim() || null,
        years_experience: toYears(values.years_experience),
        is_primary: values.is_primary,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills(candidateId) })
      toast.success(`Updated ${skill.name}`)
      onClose()
    },
    onError: (error) => toast.error('Could not update skill', { description: error.message }),
  })

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {skill.name}</DialogTitle>
          <DialogDescription>The skill name and category are shared across profiles and cannot be edited here.</DialogDescription>
        </DialogHeader>
        <form
          id="edit-skill"
          className="grid gap-4"
          noValidate
          onSubmit={form.handleSubmit((values) => update.mutate(values))}
        >
          <div className="space-y-2">
            <Label htmlFor="edit-proficiency">Proficiency</Label>
            <Input id="edit-proficiency" placeholder="e.g. Advanced" {...form.register('proficiency')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-years">Years of experience</Label>
            <Input id="edit-years" inputMode="decimal" {...form.register('years_experience')} aria-invalid={!!form.formState.errors.years_experience} />
            <FieldError message={form.formState.errors.years_experience?.message} />
          </div>
          <div className="flex items-center gap-2">
            <Controller
              control={form.control}
              name="is_primary"
              render={({ field }) => (
                <Checkbox id="edit-primary" checked={field.value} onCheckedChange={(value) => field.onChange(value === true)} />
              )}
            />
            <Label htmlFor="edit-primary">Primary skill</Label>
          </div>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="edit-skill" disabled={update.isPending}>
            {update.isPending && <Spinner />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function SkillsManager({ candidateId }: { candidateId: string }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<CandidateSkill | null>(null)
  const skills = useQuery({
    queryKey: queryKeys.skills(candidateId),
    queryFn: () => api.skills.list(candidateId),
  })

  const form = useForm<SkillValues>({
    resolver: zodResolver(skillSchema),
    defaultValues: { name: '', category: '', proficiency: '', years_experience: '', is_primary: false },
  })

  const add = useMutation({
    mutationFn: (values: SkillValues) =>
      api.skills.add(candidateId, {
        name: values.name.trim(),
        category: values.category.trim() || null,
        proficiency: values.proficiency.trim() || null,
        years_experience: toYears(values.years_experience),
        is_primary: values.is_primary,
      }),
    onSuccess: (skill) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills(candidateId) })
      form.reset()
      toast.success(`Added ${skill.name}`)
    },
    onError: (error) => toast.error('Could not add skill', { description: error.message }),
  })

  const remove = useMutation({
    mutationFn: (skill: CandidateSkill) => api.skills.remove(candidateId, skill.id),
    onSuccess: (_, skill) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills(candidateId) })
      toast.success(`Removed ${skill.name}`)
    },
    onError: (error) => toast.error('Could not remove skill', { description: error.message }),
  })

  const errors = form.formState.errors

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Skills</CardTitle>
        <CardDescription>
          Used by the matcher and AI analysis. Only add skills you can back up with experience. Changes take effect on the next “Recalculate matches”.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <form
          noValidate
          onSubmit={form.handleSubmit((values) => add.mutate(values))}
          className="grid gap-3 rounded-lg border bg-muted/30 p-3 sm:grid-cols-[2fr_1.5fr_1.5fr_1fr_auto] sm:items-end"
        >
          <div className="space-y-1.5">
            <Label htmlFor="skill-name">Skill</Label>
            <Input id="skill-name" placeholder="e.g. FastAPI" {...form.register('name')} aria-invalid={!!errors.name} />
            <FieldError message={errors.name?.message} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="skill-category">Category</Label>
            <Input id="skill-category" placeholder="Backend" {...form.register('category')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="skill-proficiency">Proficiency</Label>
            <Input id="skill-proficiency" placeholder="Advanced" {...form.register('proficiency')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="skill-years">Years</Label>
            <Input id="skill-years" inputMode="decimal" {...form.register('years_experience')} aria-invalid={!!errors.years_experience} />
            <FieldError message={errors.years_experience?.message} />
          </div>
          <div className="flex items-center gap-3 sm:flex-col sm:items-stretch sm:gap-1.5">
            <div className="flex items-center gap-2">
              <Controller
                control={form.control}
                name="is_primary"
                render={({ field }) => (
                  <Checkbox id="skill-primary" checked={field.value} onCheckedChange={(value) => field.onChange(value === true)} />
                )}
              />
              <Label htmlFor="skill-primary" className="text-xs">Primary</Label>
            </div>
            <Button type="submit" size="sm" disabled={add.isPending}>
              {add.isPending ? <Spinner /> : <Plus />}
              Add
            </Button>
          </div>
        </form>

        {skills.isPending ? (
          <ListSkeleton rows={2} />
        ) : skills.isError ? (
          <ErrorState title="Could not load skills" error={skills.error} onRetry={() => skills.refetch()} />
        ) : skills.data.length === 0 ? (
          <EmptyState
            title="No skills yet"
            description="Add skills above, or upload your resume to detect them automatically."
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {skills.data.map((skill) => (
              <li key={skill.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5">
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  {skill.is_primary && <Star className="size-3.5 fill-amber-400 text-amber-500" aria-label="Primary skill" />}
                  <span className="font-medium">{skill.name}</span>
                  {skill.category && <Badge variant="secondary">{skill.category}</Badge>}
                </div>
                <div className="text-sm text-muted-foreground">
                  {[skill.proficiency, skill.years_experience !== null ? `${Number(skill.years_experience)} yrs` : null]
                    .filter(Boolean)
                    .join(' · ') || '—'}
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon-sm" aria-label={`Edit ${skill.name}`} onClick={() => setEditing(skill)}>
                    <Pencil />
                  </Button>
                  <ConfirmDialog
                    trigger={
                      <Button variant="ghost" size="icon-sm" aria-label={`Remove ${skill.name}`}>
                        <Trash2 />
                      </Button>
                    }
                    title={`Remove ${skill.name}?`}
                    description="It will be removed from your profile. Re-run matching to update scores."
                    confirmLabel="Remove"
                    destructive
                    onConfirm={() => remove.mutate(skill)}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      {editing && (
        <EditSkillDialog candidateId={candidateId} skill={editing} onClose={() => setEditing(null)} />
      )}
    </Card>
  )
}
