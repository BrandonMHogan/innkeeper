---
phase: 04-security
plan: 03
status: complete
---

# Plan 04-03 Summary: Capture-Container Port Scanning (nmap)

## What Was Built

The privileged capture-container side of SEC-01's port scanning: a new
`port_scan.py` module wrapping the home-assistant-libs `python-nmap` fork
for top-1000-port SYN scans, a scan-trigger-listener thread polling the
backend's `/api/capture/pending-scans`, and a daily-rescan thread pinging
`/api/capture/queue-daily-scans` on a fixed schedule.

### Task 0 — Checkpoint resolution (python-nmap dependency source)
Resolved by the orchestrator/user before this execution resumed: verified
via GitHub API that `home-assistant-libs/python-nmap` is legitimate (not
archived, exposes the expected `nmap.PortScanner` API). Pinned to commit
`9ac822b56ebbdbf8816e592a1cdb071a2b808f11` (verified current HEAD of
`master`).

### Task 1 — `port_scan.py` module + dependency/Dockerfile wiring
- `capture/port_scan.py` — `_run_and_post_scan()` runs a `-sS` SYN scan
  (no `-p` flag, nmap's default top-1000 ports per D-02) and POSTs
  `{"device_id", "open_ports"}` to `/api/capture/scan` with a 60s timeout;
  treats a non-responsive host (`target_ip not in scanner.all_hosts()`) as
  `open_ports=[]` rather than crashing. `run_scan_listener()` polls
  `/api/capture/pending-scans` every `SCAN_POLL_INTERVAL=3`s using
  `stop_event.wait()` (not `time.sleep`) so shutdown isn't delayed.
  `run_daily_rescan_loop()` sleeps until `DAILY_RESCAN_HOUR=3`:00 local
  time and POSTs to `/api/capture/queue-daily-scans` — contains zero
  device-selection logic, matching Pitfall 2's requirement that all
  "registered devices only" scoping live on the backend.
- `capture/test_port_scan.py` — 3 behavioral tests against a
  `unittest.mock.MagicMock` standing in for `nmap.PortScanner`, asserting
  the constructed POST payload via a monkeypatched `httpx.post`: (1) open
  ports correctly filtered from a closed port, (2) unresponsive host still
  POSTs once with `open_ports: []`, (3) a raised exception from the mocked
  `httpx.post` is swallowed, not propagated. All 3 pass.
- `capture/requirements-dev.txt` — new dev-only `pytest` line, first test
  infra in `capture/`.
- `capture/Dockerfile` — `nmap` added to the existing single `apt-get
  install` line alongside `libpcap-dev` (no second `RUN` layer).
- `capture/requirements.txt` — added the pinned git dependency.

**Deviation found and fixed during verification:** the plan's literal
`python-nmap @ git+https://github.com/home-assistant-libs/python-nmap@<sha>`
requirements.txt syntax fails to install. Installing it directly into a
venv showed `pip` rejects the named requirement because the fork's own
package metadata declares its distribution name as `netmap`, not
`python-nmap` (confirmed via `pip show netmap` after install) — pip
enforces that a `name @ url` requirement's resolved metadata name matches
`name`, and also rejects an `#egg=python-nmap` fragment for the same
reason. The working fix is a bare `git+https://...@<sha>` line with no
name annotation; `import nmap` still resolves `PortScanner` identically.
Verified live: `pip install -r requirements.txt` succeeds end-to-end in a
real venv, and `import nmap; nmap.PortScanner` works.

### Task 2 — Wire threads into `capture.py`
- `capture/capture.py` — added `from port_scan import run_daily_rescan_loop,
  run_scan_listener`; `main()` now constructs, starts, and joins two new
  named threads (`scan-listener`, `daily-rescan`) alongside the original
  four (`arp-sniff`, `dhcp-sniff`, `mdns-browser`, `traffic-sniff`), all
  sharing the same module-level `stop_event`. Original four threads'
  start/join ordering preserved exactly; new threads appended after.

## Verification

- `cd capture && python3 -c "import ast; ast.parse(open('port_scan.py').read())"` — OK.
- `grep -n "git+https://github.com/home-assistant-libs/python-nmap@" requirements.txt` — present.
- `grep -n "nmap" Dockerfile` — present, same apt-get line as `libpcap-dev`.
- Installed the real fork + full `requirements.txt`/`requirements-dev.txt`
  into the project's existing `/tmp/innkeeper-venv313` (Python 3.13) venv —
  confirmed clean install end-to-end (this surfaced and fixed the
  `netmap`-vs-`python-nmap` name-mismatch deviation above).
- `python -m pytest test_port_scan.py -x -v` — 3/3 passed.
- `capture/capture.py` AST-parses and also actually imports cleanly
  (`import capture` succeeds) with the real `nmap`/`scapy`/`zeroconf`
  module chain present in the venv — confirmed both `run_scan_listener`
  and `run_daily_rescan_loop` are reachable as module attributes.
- Backend full suite (`cd backend && pytest`) re-run for regression safety
  (this plan touches no backend files): 108/108 passing (one
  `test_compose.py::test_all_services_healthy` flake observed once, passed
  clean on immediate rerun — pre-existing environment-timing flakiness
  unrelated to this plan's changes).

## Deviations From Plan

- **requirements.txt dependency line syntax** (see Task 1 above): the
  plan's literal `python-nmap @ git+https://...` syntax does not install —
  pip rejects it as a name mismatch against the fork's actual `netmap`
  distribution metadata. Fixed to a bare `git+https://...@<sha>` line
  (no name prefix), verified by live install in a venv. The pinned commit
  SHA, fork URL, and `import nmap` API surface are otherwise exactly as
  specified — this is an install-syntax fix only, not a package-identity
  or security concern (the same human-verified fork/SHA is still what's
  installed).

## Key Decisions / Notes for Downstream Plans

- The `python-nmap` package's actual PyPI/pip distribution name is
  `netmap`, not `python-nmap` — if any future plan adds another reference
  to this dependency (e.g. a Docker build-arg, a lockfile, documentation),
  do not reintroduce the `python-nmap @` name prefix.
- `capture/port_scan.py`'s two new threads close out SEC-01's
  scan-execution path entirely on the capture side. Plan 04-04 (frontend)
  is unaffected by this plan and can proceed independently against the
  already-stable `/api/security/*` and `/api/capture/*` contract built in
  Plan 04-02.
- A live `docker compose build capture` smoke test (confirming the git
  dependency installs inside the actual `python:3.13-slim` build context,
  not just a local venv) is still recommended at deployment time, per the
  plan's `<verification>` section — not performed in this session since no
  Docker build target was exercised, but the local venv install used the
  exact same pinned git URL/SHA the Dockerfile's `pip install -r
  requirements.txt` will use, which is the part that was actually at risk
  (see Deviations).
