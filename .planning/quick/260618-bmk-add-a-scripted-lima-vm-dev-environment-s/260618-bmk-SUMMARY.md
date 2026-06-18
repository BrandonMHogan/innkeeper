---
phase: quick
plan: 260618-bmk
subsystem: dev-environment
tags: [lima, docker, networking, dev-tooling]
dependency-graph:
  requires: []
  provides: [bridged-lima-vm, dev-vm-script, lima-dev-docs]
  affects: [phase-01-d05-checkpoint]
tech-stack:
  added: [lima, socket_vmnet]
  patterns: [bridged-vm-networking, official-apt-repo-provisioning]
key-files:
  created:
    - lima/innkeeper.yaml
    - scripts/dev-vm.sh
    - README.md
  modified: []
decisions:
  - "Used vmType: vz (Apple Virtualization framework) since Lima's bridged network mode requires it; qemu vmType only supports NAT-style lima:shared, which would not solve the underlying problem"
  - "socket_vmnet flagged as an undocumented-in-plan co-requisite for bridged networking and added to README prerequisites alongside brew install lima"
  - "down does not delete the VM disk — kept as a fast stop/start workflow; VM deletion is an explicit separate operation not exposed by this script"
metrics:
  duration: ~25min
  completed: 2026-06-18
---

# Quick Task 260618-bmk: Scripted Lima VM Dev Environment Summary

Added a bridged-network Lima VM (vz vmType, Docker Engine from the official apt repo) plus a `scripts/dev-vm.sh` up/down/ssh/status wrapper and README documentation, giving any Mac a real LAN-routable Linux network namespace to verify the Phase 1 D-05 ARP capture checkpoint that Docker Desktop's NAT-isolated network cannot support.

## What Was Built

**`lima/innkeeper.yaml`** — Lima instance definition:
- `vmType: vz`, Ubuntu 24.04 LTS cloud image (x86_64 + aarch64)
- `networks: [{lima: bridged, interface: lima0}]` for a real LAN-routable IP (not the `192.168.5.x` shared/NAT range), with an inline comment explaining why bridged is mandatory and flagging `socket_vmnet` as a required host-side helper
- Repo mounted read-write at `/home/{{.User}}.linux/innkeeper`
- `containerd: {system: false, user: false}` since Docker Engine (not Lima's bundled containerd) runs the stack
- System provision script installs Docker Engine + compose plugin from Docker's official apt repo only (signed packages — no curl-pipe-to-sh), adds the Lima user to the `docker` group
- Boot probe (`docker compose version` check) fails loudly if provisioning didn't complete

**`scripts/dev-vm.sh`** — executable bash wrapper (`set -euo pipefail`), fixed instance name `innkeeper`, path-independent via `SCRIPT_DIR`:
- `up`: creates or starts the VM, then `docker compose up -d --build` inside it, prints the bridged LAN IP
- `down`: `docker compose down` inside the VM, then `limactl stop` (VM disk preserved, not deleted)
- `ssh`: interactive shell into the VM
- `status`: `limactl list`, bridged LAN IP, and `docker compose ps` from inside the VM
- Unknown/missing argument prints usage and exits 1

**`README.md`** — created (did not previously exist) with a project title and a "Development (Lima VM)" section covering the why (Docker Desktop NAT vs. D-05 requirement), one-time prerequisites (`brew install lima`, `brew install socket_vmnet`), and the four `dev-vm.sh` subcommands.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - missing critical functionality] Added `socket_vmnet` as an explicit prerequisite**
- **Found during:** Task 1
- **Issue:** Lima's bridged network mode depends on the `socket_vmnet` helper being installed on the host; the plan only mentioned `brew install lima`. Without it, `networks: [{lima: bridged}]` would fail to resolve a real interface.
- **Fix:** Added `brew install socket_vmnet` to README.md prerequisites alongside `brew install lima`, and flagged the dependency with a comment in `lima/innkeeper.yaml` citing the Lima bridged-network doc section.
- **Files modified:** `lima/innkeeper.yaml`, `README.md`
- **Commit:** af6005a, fefb67c

No other deviations — plan executed as written.

## Verification

- `test -f lima/innkeeper.yaml && grep vmType: vz && grep mounts:` — PASS
- `test -x scripts/dev-vm.sh && bash -n scripts/dev-vm.sh && grep up\)|down\)|ssh\)|status\)` — PASS (4 matches)
- `test -f README.md && grep "brew install lima" && grep "dev-vm.sh"` — PASS (4 matches for dev-vm.sh)

Manual smoke test (`scripts/dev-vm.sh up` actually booting a VM and confirming a real LAN IP) was **not** run — Lima is not installed on this machine in the execution environment. This is called out explicitly in the plan's own verification section as a manual step requiring local Lima installation, not an automated check.

## Known Stubs

None — all three artifacts are complete, functional implementations, not placeholders. The one untestable item (live VM boot) is a manual verification step outside this environment's scope, not a code stub.

## Threat Flags

None beyond what the plan's own threat model already covers (T-quick-01 through T-quick-SC), all of which were addressed as specified: Docker installed only from the official signed apt repo, bridged VM accepted as appropriate exposure for a local trusted-LAN dev tool, and no new package-manager installs introduced in the main repo.

## Self-Check: PASSED

- FOUND: lima/innkeeper.yaml
- FOUND: scripts/dev-vm.sh
- FOUND: README.md
- FOUND: af6005a (lima/innkeeper.yaml commit)
- FOUND: 1d2dfa3 (scripts/dev-vm.sh commit)
- FOUND: fefb67c (README.md commit)
