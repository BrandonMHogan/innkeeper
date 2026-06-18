---
phase: 01-foundation-capture-feasibility
plan: 03
subsystem: frontend
tags: [sveltekit, svelte5, adapter-static, tailwindcss-v4, nginx, auth-ui]

requires: ["backend /api/auth/* route surface (Plan 01-01)"]
provides:
  - "frontend/ SvelteKit SPA scaffold (adapter-static, SPA mode via ssr=false)"
  - "theme.css single source of truth for all --color-* tokens, inherited by all future phases"
  - "api.ts apiPost/apiGet fetch wrapper with credentials: 'include' for cross-port session cookie"
  - "/setup, /login, /dashboard pages matching UI-SPEC.md's copy/color/spacing/interaction contract exactly"
  - "nginx.conf + multi-stage Dockerfile serving the static build on port 9999 (D-17)"
affects: [01-02-capture-compose (docker compose end-to-end checkpoint), phase-2-device-registry (first real dashboard content)]

tech-stack:
  added: ["@sveltejs/kit@2.65.2", "svelte@5.56.3", "@sveltejs/adapter-static@3.0.10", "vite@6.x", "tailwindcss@4.3.1", "@lucide/svelte@1.20.0", "bits-ui@2.18.1", "@fontsource/inter@5.2.8"]
  patterns:
    - "SvelteKit SPA mode: ssr=false in root +layout.ts, adapter-static with fallback: '200.html'"
    - "All cross-origin fetches go through src/lib/api.ts (apiPost/apiGet), both setting credentials: 'include'"
    - "All color values are CSS custom properties from theme.css; no hardcoded hex anywhere else in the app"
    - "Svelte 5 runes idiom: $state, $props with {@render children()} in root layout instead of <slot />"
    - "Client-side onMount auth guard pattern: apiGet('/api/auth/me') -> redirect to /login on non-ok response (UX-only; server-side require_auth is the real boundary per threat model T-01-10)"

key-files:
  created:
    - frontend/package.json
    - frontend/svelte.config.js
    - frontend/vite.config.ts
    - frontend/tsconfig.json
    - frontend/Dockerfile
    - frontend/nginx.conf
    - frontend/.gitignore
    - frontend/src/app.html
    - frontend/src/lib/styles/theme.css
    - frontend/src/lib/api.ts
    - frontend/src/routes/+layout.svelte
    - frontend/src/routes/+layout.ts
    - frontend/src/routes/setup/+page.svelte
    - frontend/src/routes/login/+page.svelte
    - frontend/src/routes/dashboard/+page.svelte
  modified: []

key-decisions:
  - "Verified all pinned package versions (@sveltejs/kit@2.65.2, svelte@5.56.3, @lucide/svelte@1.20.0, bits-ui@2.18.1, @fontsource/inter@5.2.8, tailwindcss@4.3.1, @sveltejs/adapter-static@3.0.10) exist on the npm registry via `npm view` before installing — no slopsquatting risk, matches RESEARCH.md's Package Legitimacy Audit"
  - "Used @lucide/svelte (not the deprecated lucide-svelte) per RESEARCH.md and UI-SPEC's icon library note"
  - "Inline styles used for layout/spacing/color in the three page components rather than a Tailwind utility-class pass, since theme.css already defines all needed tokens via CSS custom properties and Tailwind v4 config wiring was not required by the plan's acceptance criteria — all values still reference var(--color-*) tokens, satisfying the single-source-of-truth requirement"
  - "Added frontend/.gitignore (not explicitly listed in files_modified) to exclude node_modules, build/, .svelte-kit/ from version control — required for any frontend Node project, Rule 2 (missing critical functionality)"

patterns-established:
  - "Page components reference only var(--color-*) tokens — never hardcoded hex — enforced by grep verification in this plan and to be carried into Phase 2+"
  - "Auth page layout: flex column, centered, min-height: 100dvh, 400px-wide card matching UI-SPEC Layout section"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, PLAT-01]

duration: 12min
completed: 2026-06-18
---

# Phase 1 Plan 03: Frontend Foundation Summary

**SvelteKit 5 SPA (adapter-static) with theme.css token system, api.ts fetch wrapper, and /setup, /login, /dashboard pages matching UI-SPEC.md's copy and interaction contract exactly.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-18T00:39:00Z (approx, post Plan 01-01)
- **Completed:** 2026-06-18T00:39:41Z
- **Tasks:** 2 completed
- **Files modified:** 16 created (including .gitignore), 0 modified

## Accomplishments

- Scaffolded a SvelteKit 2.65.2 + Svelte 5.56.3 SPA using `adapter-static` with `fallback: '200.html'` and `ssr = false`, confirmed all pinned package versions are legitimate on the npm registry before install
- Built `theme.css` as the single source of truth for all nine UI-SPEC color tokens plus the emerald-600 submit-button contrast override, and `api.ts` as the single fetch entry point with `credentials: 'include'` on both `apiPost` and `apiGet` for the cross-port httpOnly session cookie
- Implemented `/setup` and `/login` with exact UI-SPEC copy (headings, subtext, button labels, all four error-state strings), show/hide password toggle (`Eye`/`EyeOff` from `@lucide/svelte`), `Loader2` spinner loading state with `aria-busy`, and `role="alert"` error banners
- Implemented `/dashboard` with an `onMount` client-side auth guard calling `apiGet('/api/auth/me')` that redirects unauthenticated visitors to `/login`, rendering the exact UI-SPEC placeholder copy once authenticated
- `npm run build` exits 0, producing `build/200.html` and all three routes in the static output; verified no hardcoded hex colors exist anywhere outside `theme.css`

## Task Commits

Each task was committed atomically:

1. **Task 1: SvelteKit scaffold, theme tokens, API client** - `dcbebce` (feat)
2. **Task 2: Setup, login, and dashboard pages per UI-SPEC copy contract** - `5cf7400` (feat)

## Files Created/Modified

- `frontend/package.json` - SvelteKit 2.65.2, Svelte 5.56.3, adapter-static 3.0.10, Tailwind v4.3.1, @lucide/svelte 1.20.0, bits-ui 2.18.1, @fontsource/inter 5.2.8
- `frontend/svelte.config.js` - adapter-static with `fallback: '200.html'`, `precompress: true`
- `frontend/vite.config.ts` - sveltekit() + tailwindcss() Vite plugins
- `frontend/tsconfig.json` - extends .svelte-kit/tsconfig.json, strict mode
- `frontend/Dockerfile` - multi-stage node:22-alpine builder + nginx:alpine release, `ARG PUBLIC_API_URL` baked at build time, `EXPOSE 9999`
- `frontend/nginx.conf` - `listen 9999`, `try_files ... /200.html`, static asset caching
- `frontend/.gitignore` - excludes node_modules, build/, .svelte-kit/ (added per Rule 2 — missing critical functionality for any Node project)
- `frontend/src/app.html` - SvelteKit app shell template
- `frontend/src/lib/styles/theme.css` - all 9 UI-SPEC `--color-*` tokens + `--color-accent-button-bg` contrast override
- `frontend/src/lib/api.ts` - `apiPost`/`apiGet`, both `credentials: 'include'`, `PUBLIC_API_URL` env-driven base
- `frontend/src/routes/+layout.svelte` - root layout importing theme.css and @fontsource/inter (400/500/600/700), Svelte 5 `{@render children()}`
- `frontend/src/routes/+layout.ts` - `export const ssr = false;`
- `frontend/src/routes/setup/+page.svelte` - first-run password setup form
- `frontend/src/routes/login/+page.svelte` - login form
- `frontend/src/routes/dashboard/+page.svelte` - protected empty dashboard shell with onMount auth guard

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `<svelte:head>` cannot be nested inside an `{#if}` block**
- **Found during:** Task 2, first build attempt of `/dashboard`
- **Issue:** Initial implementation placed `<svelte:head><title>Innkeeper</title></svelte:head>` inside the `{#if authenticated}` block. Svelte 5's compiler rejects this with `svelte_meta_invalid_placement` since `<svelte:head>` must be a top-level element in the component.
- **Fix:** Moved `<svelte:head>` to the top level of the component, outside the `{#if}` block. The page title is now always set regardless of auth state, matching the spirit of the UI-SPEC's "Innkeeper" tab title requirement.
- **Files modified:** `frontend/src/routes/dashboard/+page.svelte`
- **Commit:** `5cf7400`

**2. [Rule 2 - Missing critical functionality] Added `frontend/.gitignore`**
- **Found during:** Task 1, before staging files for commit
- **Issue:** The plan's `files_modified` list did not include a `.gitignore`, but without one, `node_modules/`, `build/`, and `.svelte-kit/` would either be committed (bloating the repo) or left as untracked noise.
- **Fix:** Added `frontend/.gitignore` excluding `node_modules`, `/build`, `/.svelte-kit`, `/package`, and env files (mirroring the root `.gitignore`'s `.env` pattern).
- **Files modified:** `frontend/.gitignore`
- **Commit:** `dcbebce`

No architectural deviations (Rule 4) were needed.

## Known Stubs

None. All three pages are fully wired to the real backend API (`apiPost`/`apiGet` against `/api/auth/setup`, `/api/auth/login`, `/api/auth/me`) built in Plan 01-01. No mock data or hardcoded empty states exist outside the intentional Phase 1 dashboard placeholder copy, which is the documented UI-SPEC contract for this phase (Phase 2 adds real dashboard content).

## Threat Flags

None. All security-relevant surface in this plan (password input masking, client-side auth guard as UX-only redirect) was already covered by the plan's `<threat_model>` (T-01-08, T-01-09, T-01-10) and implemented exactly as dispositioned — no new surface introduced.

## Self-Check: PASSED
