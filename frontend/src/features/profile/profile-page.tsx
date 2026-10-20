import { useAuth } from '@/auth/auth-context'
import { ErrorState, ListSkeleton, PageHeader } from '@/components/common'
import { useCandidate } from '@/hooks/use-candidate'
import { ProfileForm } from './profile-form'
import { ResumeUpload } from './resume-upload'
import { SkillsManager } from './skills-manager'

export function ProfilePage() {
  const { user } = useAuth()
  const candidate = useCandidate()

  if (candidate.isPending) {
    return (
      <>
        <PageHeader title="Profile" />
        <ListSkeleton rows={4} />
      </>
    )
  }

  if (candidate.isError) {
    return (
      <>
        <PageHeader title="Profile" />
        <ErrorState title="Could not load your profile" error={candidate.error} onRetry={() => candidate.refetch()} />
      </>
    )
  }

  const profile = candidate.data

  return (
    <>
      <PageHeader
        title={profile ? 'Profile' : 'Create your profile'}
        description={
          profile
            ? 'Your experience and preferences drive matching, analysis, and generated documents.'
            : 'Start with the basics. You can upload a resume and add skills right after.'
        }
      />
      <div className="space-y-6">
        {profile && <ResumeUpload candidate={profile} />}
        {profile && <SkillsManager candidateId={profile.id} />}
        <ProfileForm candidate={profile} defaultEmail={user?.email} />
      </div>
    </>
  )
}
