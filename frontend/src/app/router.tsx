import { createBrowserRouter } from 'react-router'

import { RedirectIfAuthenticated, RequireAuth } from '@/auth/guards'
import { AppShell } from '@/components/layout/app-shell'
import { NotFoundPage } from '@/app/not-found'
import { ApplicationDetailPage } from '@/features/applications/application-detail-page'
import { ApplicationsPage } from '@/features/applications/applications-page'
import {
  ForgotPasswordPage,
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
} from '@/features/auth/auth-pages'
import { DashboardPage } from '@/features/dashboard/dashboard-page'
import { DiscoverPage } from '@/features/jobs/discover-page'
import { JobDetailPage } from '@/features/jobs/job-detail-page'
import { MatchesPage } from '@/features/jobs/matches-page'
import { ProfilePage } from '@/features/profile/profile-page'
import { SettingsPage } from '@/features/settings/settings-page'

export const routes = [
  {
    element: <RedirectIfAuthenticated />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
    ],
  },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/reset-password', element: <ResetPasswordPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/discover', element: <DiscoverPage /> },
          { path: '/matches', element: <MatchesPage /> },
          { path: '/jobs/:jobId', element: <JobDetailPage /> },
          { path: '/applications', element: <ApplicationsPage /> },
          { path: '/applications/:applicationId', element: <ApplicationDetailPage /> },
          { path: '/profile', element: <ProfilePage /> },
          { path: '/settings', element: <SettingsPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
