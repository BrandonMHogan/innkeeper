---
phase: quick
plan: 260618-coa
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/nginx.conf
  - docker-compose.yml
  - .env.example
autonomous: true
requirements: []
must_haves:
  truths:
    - "After login, the browser's next request to /api/auth/me succeeds (200) instead of 401, because the cookie is sent on a same-origin request"
    - "Frontend and API are served from the same origin (host:port) as seen by the browser, eliminating SameSite=Lax cross-site cookie suppression"
    - "Frontend no longer needs a build-time IP/hostname baked into PUBLIC_API_URL — relative /api paths resolve against whatever origin the browser is actually on"
  artifacts:
    - path: "frontend/nginx.conf"
      provides: "reverse proxy location /api/ -> http://api:8000/api/ on the docker-compose internal network"
      contains: "proxy_pass http://api:8000/api/"
    - path: "docker-compose.yml"
      provides: "PUBLIC_API_URL default empty so frontend build emits relative /api paths"
      contains: "PUBLIC_API_URL"
    - path: ".env.example"
      provides: "documentation that PUBLIC_API_URL should be empty for the standard same-origin setup"
      contains: "PUBLIC_API_URL"
  key_links:
    - from: "frontend/nginx.conf"
      to: "api service (docker-compose internal DNS)"
      via: "proxy_pass http://api:8000/api/"
      pattern: "proxy_pass\\s+http://api:8000/api/"
    - from: "frontend/src/lib/api.ts"
      to: "frontend/nginx.conf location /api/"
      via: "relative fetch path when PUBLIC_API_URL is empty string"
      pattern: "API_BASE"
---

<objective>
Fix the cross-origin session-cookie bug: the frontend (port 9999) and API (port 8000) are currently different origins in the browser, and Starlette's `SessionMiddleware` uses `SameSite=Lax`, which browsers refuse to send on cross-site `fetch()` calls (only top-level GET navigations get the cookie). Result: login succeeds (200 + Set-Cookie) but the very next `GET /api/auth/me` comes back 401 because the cookie was never attached.

Fix by making frontend and API same-origin: nginx (already fronting the SvelteKit static build on port 9999) gains a `location /api/` block that reverse-proxies to the `api` service over the docker-compose internal network (`http://api:8000/api/`). The browser then only ever talks to one origin (port 9999), so the session cookie is always same-site. `PUBLIC_API_URL` becomes an empty string by default, which makes `frontend/src/lib/api.ts`'s `API_BASE` resolve to `''` (the `??` nullish-coalescing operator does NOT treat `''` as nullish, so the empty string is preserved), turning every API call into a relative path like `/api/auth/me` that always targets whatever origin the browser is currently on.

This also kills a second latent bug: `PUBLIC_API_URL` was previously baked into the frontend bundle as a literal IP/hostname at Docker build time — if the dev box's IP changes, every client breaks until a full image rebuild. Relative same-origin paths make the baked value irrelevant.

Purpose: Unblock login — currently login "succeeds" per HTTP response but the resulting session is immediately unusable, which is a hard blocker for any authenticated feature work.
Output: Updated `frontend/nginx.conf` with an `/api/` reverse-proxy block, `docker-compose.yml`/`.env.example` defaulting `PUBLIC_API_URL` to empty, and a verified curl-with-cookie-jar login -> /api/auth/me round trip against the rebuilt stack proving the session persists across the request boundary that previously failed.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Current state (read during planning):
- `frontend/nginx.conf` serves the static SvelteKit build on port 9999 with SPA fallback (`try_files ... /200.html`); no `/api/` location exists yet.
- `frontend/src/lib/api.ts` line 1: `const API_BASE = import.meta.env.PUBLIC_API_URL ?? 'http://localhost:8000';` — all `apiPost`/`apiGet` calls build URLs as `${API_BASE}${path}` with `credentials: 'include'`. An empty string for `PUBLIC_API_URL` makes `API_BASE` `''`, producing relative paths.
- `frontend/Dockerfile`: `ARG PUBLIC_API_URL=http://localhost:8000` then `ENV PUBLIC_API_URL=$PUBLIC_API_URL` then `npm run build` — the value compiled into the static bundle is whatever `PUBLIC_API_URL` resolves to at `docker compose build` time, sourced from `docker-compose.yml`'s `args: PUBLIC_API_URL: ${PUBLIC_API_URL}`, which in turn reads from the shell/`.env` file.
- `docker-compose.yml`: `api` service exposes port 8000 on the host and is named `api` on the compose network (resolvable internally as `http://api:8000`); `frontend` service builds with `PUBLIC_API_URL` passed as a build arg, maps host port 9999.
- `backend/src/main.py`: `SessionMiddleware` configured with `same_site="lax"`, `https_only=False`, cookie name `innkeeper_session`. `CORSMiddleware` allows `settings.frontend_url`. **No changes needed here** — confirmed per task description; the fix is entirely about making the browser see one origin, not about loosening CORS/cookie policy (loosening to `SameSite=None` would require `https_only=True`, which is wrong for a local-network app).
- `.env.example` could not be read directly during planning due to a sandbox path restriction on dotfiles; the executing task must `cat` or `Read` it directly to see its current `PUBLIC_API_URL` line before editing — do not assume its exact current wording.
- Backend routes are mounted under `/api/auth` and `/api/capture` prefixes (`app.include_router(auth.router, prefix="/api/auth")`, `capture.router, prefix="/api/capture"`), so proxying nginx's `/api/` to `http://api:8000/api/` is a clean 1:1 path passthrough — no path rewriting needed.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add nginx reverse proxy for /api/ and default PUBLIC_API_URL to empty</name>
  <files>frontend/nginx.conf, docker-compose.yml, .env.example</files>
  <action>
In `frontend/nginx.conf`, add a `location /api/` block (placed before the existing `location /` block so nginx's longest-prefix-first matching still works correctly, or anywhere since `/api/` is a more specific prefix than `/`) that does:
- `proxy_pass http://api:8000/api/;` — `api` is the docker-compose service name, resolvable on the internal compose network; trailing slash on both sides means no path rewriting occurs (nginx passes the matched URI through as-is appended to the proxy_pass path).
- `proxy_set_header Host $host;`
- `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
- `proxy_set_header X-Forwarded-Proto $scheme;`
- `proxy_http_version 1.1;` (standard for proxy_pass to avoid HTTP/1.0 connection-handling quirks)

Do NOT add `proxy_buffering off` or SSE-specific directives — no SSE endpoints exist yet in this phase per CLAUDE.md stack notes; keep this fix scoped to the cookie bug only.

In `docker-compose.yml`, change the `frontend` service's build arg from `PUBLIC_API_URL: ${PUBLIC_API_URL}` to `PUBLIC_API_URL: ${PUBLIC_API_URL:-}` so that if the shell/.env doesn't set it, Compose passes an explicit empty string as the build arg (Compose's `${VAR}` with no default leaves the arg unset, which would fall back to the Dockerfile's `ARG PUBLIC_API_URL=http://localhost:8000` default — `:-` with nothing after it forces empty string instead, which is the same-origin-safe default).

In `.env.example`, read the file first to see its current content, then update or add the `PUBLIC_API_URL` line so it documents (as a comment) that it should be left empty for the standard same-origin Docker Compose setup (nginx reverse-proxies /api/ internally), and only set to an absolute URL like `http://localhost:8000` if running the frontend dev server (`npm run dev`) standalone against a separately-running API.
  </action>
  <verify>
    <automated>grep -c 'proxy_pass http://api:8000/api/' frontend/nginx.conf | grep -q '^1$' &amp;&amp; grep -q 'PUBLIC_API_URL:-' docker-compose.yml</automated>
  </verify>
  <done>frontend/nginx.conf has a location /api/ block proxying to http://api:8000/api/ with Host/X-Forwarded-For/X-Forwarded-Proto headers set; docker-compose.yml's frontend build arg defaults PUBLIC_API_URL to empty string when unset; .env.example documents the empty-by-default convention.</done>
</task>

<task type="auto">
  <name>Task 2: Rebuild stack and verify session cookie survives across the login -> /api/auth/me boundary</name>
  <files>(no source files — verification only; may touch nothing or a throwaway script under /tmp)</files>
  <action>
Rebuild and restart the affected services so the nginx config and build-arg changes take effect: run `docker compose build frontend` then `docker compose up -d frontend api db` (or the project's equivalent compose invocation/profile if one exists — check docker-compose.yml for any profiles before assuming a bare `docker compose up -d` is correct). Wait for the `api` healthcheck-equivalent and frontend container to be running (`docker compose ps`).

Confirm the build actually picked up the empty `PUBLIC_API_URL`: inspect the built frontend bundle for the absence of a baked literal `http://localhost:8000` or any baked IP in the JS asset that contains `API_BASE`/`apiGet`/`apiPost` (e.g. `docker compose exec frontend grep -rl "API_BASE\|apiGet" /usr/share/nginx/html` then grep that file for `localhost:8000` — it should NOT appear, confirming the empty string took effect).

Then run the real cross-origin reproduction using curl with a cookie jar, hitting the frontend's port (9999) for BOTH the login and the follow-up check, simulating exactly what the browser would now do as a single origin:
1. `curl -i -c /tmp/innkeeper-cookies.txt -X POST http://localhost:9999/api/auth/login -H 'Content-Type: application/json' -d '{...valid login payload per auth.router's expected schema...}'` — inspect the auth route source if needed to get the correct field names/credentials for a valid login (or use the setup endpoint first if no account exists yet). Confirm response is 200 and `Set-Cookie: innkeeper_session=...` is present.
2. `curl -i -b /tmp/innkeeper-cookies.txt http://localhost:9999/api/auth/me` — confirm response is 200 (not 401), proving the cookie was sent and accepted on the very next request through the new same-origin nginx proxy path.

This curl-with-cookie-jar sequence is the closest automatable equivalent to real browser behavior for this specific bug class (SameSite=Lax suppression only triggers on cross-site fetch(), and curl hitting a single origin twice in sequence is mechanically the same trust context a browser would see once both requests target port 9999). Note explicitly in the task output that final, fully authoritative confirmation still requires an actual browser session (the original bug was discovered via live browser testing and Starlette's TestClient does not enforce real SameSite cookie policy) — but this curl reproduction proves the server-side cookie/proxy wiring is now correct since both requests cross the same nginx origin boundary that a browser would also see as same-site.

Clean up `/tmp/innkeeper-cookies.txt` after verification.
  </action>
  <verify>
    <automated>test -f /tmp/innkeeper-cookies.txt &amp;&amp; grep -q innkeeper_session /tmp/innkeeper-cookies.txt; echo "exit=$?"</automated>
  </verify>
  <done>docker compose build/up completed for frontend+api+db; frontend bundle confirmed to no longer contain a baked localhost:8000 (or stale IP) API_BASE value; curl login against http://localhost:9999/api/auth/login returns 200 with Set-Cookie; the immediately following curl GET http://localhost:9999/api/auth/me using the saved cookie jar returns 200 (not 401), proving the SameSite=Lax cookie is now sent because both requests share one origin.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|--------------|
| browser -> nginx (port 9999) | Untrusted client requests; now the single public entry point for both static assets and proxied API calls |
| nginx -> api (compose internal network, http://api:8000) | Trusted internal network; nginx forwards Host/X-Forwarded-* headers so backend can reason about original request context if ever needed |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|------------------|
| T-quick-260618-01 | Spoofing | X-Forwarded-Proto/X-Forwarded-For headers from nginx | accept | Single trusted reverse proxy hop on an internal compose network with no other ingress to `api:8000` exposed beyond the host-mapped port already present pre-fix; not a new attack surface introduced by this change |
| T-quick-260618-02 | Information Disclosure | nginx proxy_pass error responses | accept | Default nginx error pages for upstream failures (502/504) reveal no internal paths or stack traces; no custom error_page directives added that could leak detail |
| T-quick-260618-03 | Tampering | docker-compose.yml / nginx.conf edits | mitigate | Changes are plain-text config reviewed in this plan's diff; no package installs or new dependencies introduced, so no package-legitimacy gate applies |
</threat_model>

<verification>
1. `docker compose build frontend` succeeds with no errors.
2. `docker compose up -d` (frontend, api, db) reaches running state; `docker compose ps` shows all healthy/running.
3. `frontend/nginx.conf` contains the new `location /api/` block with the correct `proxy_pass http://api:8000/api/`.
4. Frontend built bundle no longer contains a literal `http://localhost:8000` (or any baked dev IP) tied to `API_BASE`.
5. curl-with-cookie-jar reproduction: POST `http://localhost:9999/api/auth/login` returns 200 + `Set-Cookie`; immediately following GET `http://localhost:9999/api/auth/me` with that cookie returns 200, not 401.
6. Explicit note carried into the SUMMARY that full confirmation requires a real browser session, since this is fundamentally a browser SameSite cookie-policy bug and the curl reproduction — while mechanically faithful to the same-origin trust context — is not literally a browser.
</verification>

<success_criteria>
- Login followed immediately by `/api/auth/me` returns 200 (not 401) when both requests target the frontend's origin (port 9999), proven via curl cookie-jar simulation.
- `frontend/nginx.conf` proxies `/api/` to the `api` compose service internally; the browser never talks to port 8000 directly.
- `PUBLIC_API_URL` defaults to empty string in `docker-compose.yml` and is documented as such in `.env.example`, eliminating the baked-IP fragility.
- No changes made to `backend/src/main.py` — CORS/session middleware confirmed unnecessary to touch.
</success_criteria>

<output>
Create `.planning/quick/260618-coa-fix-cross-origin-session-cookie-bug-fron/260618-coa-SUMMARY.md` when done
</output>
