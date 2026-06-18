---
phase: quick
plan: 260618-dcc
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/src/routes/capture.py
  - backend/tests/test_capture.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Capture container's POST to /api/capture/arp succeeds (201) when run through real docker-compose hairpin NAT, where source IP arrives as the bridge gateway address rather than 127.0.0.1"
    - "A genuinely external LAN client (any IP other than loopback or the detected default gateway) is still rejected with 403"
    - "If the gateway can't be determined (missing/unparseable /proc/net/route), the check fails safe to loopback-only behavior, not open/disabled"
  artifacts:
    - path: "backend/src/routes/capture.py"
      provides: "Dynamic default-gateway detection merged into the trusted-host allowlist for the capture ingest endpoint"
      contains: "/proc/net/route"
    - path: "backend/tests/test_capture.py"
      provides: "Regression tests covering gateway-IP acceptance and continued rejection of arbitrary external IPs"
  key_links:
    - from: "backend/src/routes/capture.py"
      to: "trusted host set"
      via: "module-load-time gateway detection merged with _LOOPBACK_HOSTS"
      pattern: "_LOOPBACK_HOSTS|_TRUSTED_HOSTS|gateway"
---

<objective>
Fix the capture ingest security check in `backend/src/routes/capture.py` so it accepts requests from the capture container in real docker-compose deployments (where Docker's hairpin NAT rewrites the loopback-originated source IP to the bridge gateway address, e.g. 172.18.0.1), while continuing to reject genuinely external LAN clients with 403.

Purpose: Phase 1 D-05 go/no-go gate requires capturing a real ARP packet end-to-end into `arp_events`. The capture service runs with `network_mode: host` (required for real LAN ARP capture) and POSTs to `http://127.0.0.1:${API_PORT}/api/capture/arp`. The `api` service runs on the default Docker bridge network. When this loopback-originated traffic is Docker-NATed into the api container's namespace, hairpin NAT rewrites the source IP to the bridge gateway, so `request.client.host` is never `127.0.0.1`/`::1` and the request is always rejected — fully blocking the gate.

Output: Updated `capture.py` with runtime-detected default-gateway IP added to the trusted-host set (never hardcoded), plus regression tests proving both the fix and the continued rejection of external IPs.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@backend/src/routes/capture.py
@backend/tests/test_capture.py
@docker-compose.yml
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Detect default gateway at module load and trust it alongside loopback</name>
  <files>backend/src/routes/capture.py, backend/tests/test_capture.py</files>
  <behavior>
    - Test 1 (existing, must still pass): request from `127.0.0.1`/loopback test client succeeds with 201.
    - Test 2 (existing, must still pass): request from an arbitrary external IP (`203.0.113.5`) is rejected with 403.
    - Test 3 (new): a request whose `request.client.host` equals the module's detected gateway IP (monkeypatch/inject the detected gateway constant, or parametrize via the same `ASGITransport(client=(...))` pattern used in the existing rejection test, using whatever value `_detect_default_gateway()` returns when fed a fixed/fake `/proc/net/route` fixture) is accepted with 201.
    - Test 4 (new): when `_detect_default_gateway()` is given malformed/missing route data (e.g. empty string, or a path that doesn't exist), it returns `None` (or equivalent "not detected" sentinel) without raising, and the trusted-host set falls back to loopback-only — i.e. a request from a fake "gateway-shaped" IP that wasn't actually detected is still rejected with 403.
  </behavior>
  <action>
    In backend/src/routes/capture.py: add a `_detect_default_gateway() -> str | None` function that reads `/proc/net/route` (path injectable via a module-level constant like `_PROC_NET_ROUTE_PATH = "/proc/net/route"` so tests can override it), finds the line whose `Destination` field is `00000000` (the default route), parses the `Gateway` field (little-endian hex, e.g. `0102FE0A` packed via `struct` or `socket.inet_ntoa(bytes.fromhex(field)[::-1])`), and returns the dotted-quad gateway IP. Wrap all file I/O and parsing in a broad `try/except` (OSError, ValueError, IndexError, etc.) and return `None` on any failure — never raise, never crash module import.

    Replace the static `_LOOPBACK_HOSTS = ("127.0.0.1", "::1")` tuple with a computed `_TRUSTED_HOSTS` frozenset built at module load: start with `{"127.0.0.1", "::1"}`, then call `_detect_default_gateway()` once at import time and add its result to the set only if it returned a non-None value. Update the `ingest_arp` check to use `client_host not in _TRUSTED_HOSTS` instead of `_LOOPBACK_HOSTS`. Keep the existing 403 error message and status code unchanged. Do not hardcode any specific gateway IP (e.g. 172.18.0.1) anywhere in the code — it must always come from runtime detection, with loopback-only as the safe fallback when detection fails.

    In backend/tests/test_capture.py: add the two new tests described in `<behavior>`. For Test 3, the cleanest approach is to monkeypatch `src.routes.capture._TRUSTED_HOSTS` directly to include a known fake IP (e.g. `"10.99.0.1"`) for the duration of the test, then use the existing `ASGITransport(client=("10.99.0.1", 12345))` pattern to prove that IP is now accepted — this verifies the membership-check logic without depending on the real host's actual route table. For Test 4, test `_detect_default_gateway()` directly: monkeypatch `src.routes.capture._PROC_NET_ROUTE_PATH` to a nonexistent path (e.g. `"/nonexistent/path/route"`) and assert the function returns `None` rather than raising.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/test_capture.py -v</automated>
  </verify>
  <done>All four tests in test_capture.py pass: original loopback-accept, original external-reject, new gateway-accept (via monkeypatched trusted set), new fail-safe-on-bad-route-path returns None. No hardcoded gateway IP literal appears in capture.py.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Runtime default-gateway detection added to backend/src/routes/capture.py so the capture container's hairpin-NATed requests (source IP rewritten to the Docker bridge gateway) are now trusted alongside loopback, while external LAN IPs remain rejected. Unit tests pass.</what-built>
  <how-to-verify>
    This requires the real Lima VM docker-compose stack (per plan constraints) since the bug only reproduces under genuine Docker hairpin NAT — not reproducible in the unit test sandbox.

    1. `limactl shell innkeeper`
    2. Inside the VM: `cd /innkeeper && docker compose up -d --build api`
    3. Wait for the api container to report healthy/started (`docker compose ps`).
    4. From inside the capture container, send a test ARP payload to confirm the fix:
       `docker compose exec capture python3 -c "import httpx; r = httpx.post('http://127.0.0.1:8000/api/capture/arp', json={'src_mac': 'aa:bb:cc:dd:ee:ff', 'src_ip': '192.168.1.50', 'dst_ip': '192.168.1.1'}); print(r.status_code, r.text)"`
       Expected: `201` (not `403`).
    5. Confirm the row landed in the database:
       `docker compose exec db psql -U innkeeper -d innkeeper -c "SELECT * FROM arp_events;"`
       Expected: at least one row with the test payload's src_mac/src_ip/dst_ip.
    6. Sanity-check the security boundary is still intact: confirm no code path accepts arbitrary external IPs (this was already covered by the automated test in Task 1, but visually re-check capture.py if anything looks off).
  </how-to-verify>
  <resume-signal>Type "approved" once you see 201 Created and a row in arp_events, or describe what failed.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|--------------|
| Docker bridge network -> api container | Requests reaching `/api/capture/arp` arrive from either same-host hairpin-NATed traffic (trusted) or other containers/LAN clients on the bridge network (untrusted) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|------------------|
| T-quick-01 | Spoofing | `ingest_arp` trusted-host check | mitigate | Only loopback addresses plus the runtime-detected default gateway IP are trusted; this gateway IP is only reachable via Docker's own NAT for same-host traffic and cannot be sourced from genuine external LAN clients, since Docker preserves real external source IPs unmodified |
| T-quick-02 | Denial of Service | `_detect_default_gateway()` at module import | accept | Function is wrapped in broad try/except and never raises; worst case it returns None and the service falls back to loopback-only, which is the pre-existing (safe, if not currently functional) behavior |
| T-quick-03 | Tampering | Hardcoding the gateway IP | mitigate | Explicitly prohibited by plan action — IP is always detected at runtime from `/proc/net/route`, never a literal constant, so the fix is not tied to one specific subnet/Docker version |
</threat_model>

<verification>
1. `cd backend && python -m pytest tests/test_capture.py -v` — all 4 tests pass.
2. Grep confirms no hardcoded gateway literal: `grep -n "172\." backend/src/routes/capture.py` returns no matches.
3. Live verification per the human-verify checkpoint: 201 Created from the capture container through real Docker hairpin NAT, and a row visible in `arp_events` via psql.
</verification>

<success_criteria>
- backend/tests/test_capture.py passes with 4 tests (2 original + 2 new), including a fail-safe test proving the check never crashes or opens up to arbitrary hosts when gateway detection fails.
- capture.py contains no hardcoded gateway IP literal; gateway is always detected at runtime from /proc/net/route.
- Live Lima VM verification confirms POST /api/capture/arp returns 201 (not 403) from the capture container, and the resulting row appears in arp_events.
- Phase 1 D-05 go/no-go gate is unblocked.
</success_criteria>

<output>
Create `.planning/quick/260618-dcc-fix-capture-py-loopback-only-security-ch/260618-dcc-SUMMARY.md` when done
</output>
</content>
