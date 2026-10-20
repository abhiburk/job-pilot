# JobPilot frontend

React + TypeScript SPA for the JobPilot API. Setup and the overall architecture are in the [root README](../README.md).

```bash
cp .env.example .env    # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev             # http://localhost:5173
```

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server on port 5173 (strict; the backend's default CORS origin) |
| `npm test` | Vitest + Testing Library (jsdom) |
| `npm run typecheck` | `tsc -b` (app, tests, Vite/Vitest config) |
| `npm run lint` | oxlint |
| `npm run build` | Type check + production build to `dist/` |

## Layout

```text
src/
  app/            router, 404 page
  auth/           session context (cookie session + in-memory CSRF token), route guards
  components/     layout shell, shared states (empty/error/skeleton), badges, confirm dialog
  components/ui/  shadcn/ui components (generated; edit sparingly)
  features/       one folder per screen: dashboard, jobs, applications, profile, settings, auth
  hooks/          useCandidate / WithCandidate
  lib/            api.ts (the only place that knows endpoint URLs), types, query keys, formatting, htmlToText
  test/           test setup, fetch mock, component tests
```

## Conventions

- All requests go through `src/lib/api.ts` with `credentials: "include"`. The CSRF token is held in memory only, and nothing auth-related goes in `localStorage`.
- Server state uses TanStack Query. Mutations invalidate the relevant `queryKeys` prefixes instead of updating caches by hand. The exceptions are the session and the profile, whose responses are written straight into the cache.
- A 401 on any non-auth request ends the session client-side and redirects to `/login?expired=1&next=…`.
- Job descriptions and AI output are rendered as plain text. `htmlToText` reads untrusted HTML through an inert `DOMParser` document; there is no `dangerouslySetInnerHTML`.
- Validation limits in Zod schemas mirror the backend's Pydantic and query constraints. The backend stays the source of truth.
