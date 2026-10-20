import { Link } from 'react-router'

import { EmptyState } from '@/components/common'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      description="This page does not exist."
      action={
        <Button asChild variant="outline">
          <Link to="/">Go to dashboard</Link>
        </Button>
      }
    />
  )
}
