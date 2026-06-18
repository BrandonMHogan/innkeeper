---
phase: quick
plan: 260618-bmk
type: execute
wave: 1
depends_on: []
files_modified:
  - lima/innkeeper.yaml
  - scripts/dev-vm.sh
  - README.md
autonomous: true
requirements: [D-01, D-03, D-05, D-18]

must_haves:
  truths:
    - "Running `scripts/dev-vm.sh up` from any Mac creates a Lima VM with a real bridged LAN IP (not Docker Desktop NAT) and brings up the full docker-compose stack inside it"
    - "Running `scripts/dev-vm.sh down` stops and deletes the VM cleanly"
    - "Running `scripts/dev-vm.sh ssh` opens a shell inside the VM"
    - "Running `scripts/dev-vm.sh status` reports whether the VM is running and shows its LAN IP"
    - "A developer reading README.md knows to run `brew install lima` once before first use"
    - "The repo is mounted into the VM so docker compose builds use live source, matching D-18's mounted-volume dev workflow"
  artifacts:
    - path: "lima/innkeeper.yaml"
      provides: "Lima VM definition: Linux guest, vz vmType, bridged network mode (socket_vmnet or lima's built-in bridged network), Docker provisioned via the built-in template merge or provision script, repo mount"
      contains: "networks:"
    - path: "scripts/dev-vm.sh"
      provides: "Wrapper script with up/down/ssh/status subcommands driving limactl against lima/innkeeper.yaml"
      contains: "limactl"
    - path: "README.md"
      provides: "One-time brew install lima prerequisite note plus dev-vm.sh usage instructions"
      contains: "brew install lima"
  key_links:
    - from: "scripts/dev-vm.sh"
      to: "lima/innkeeper.yaml"
      via: "limactl start/stop/delete --name innkeeper lima/innkeeper.yaml"
      pattern: "limactl (start|stop|delete).*innkeeper"
    - from: "scripts/dev-vm.sh"
      to: "docker compose"
      via: "limactl shell innkeeper -- docker compose -f /path/in/vm/docker-compose.yml up"
      pattern: "docker compose"
---

<objective>
Add a scripted Lima VM dev environment so the Phase 1 docker-compose stack (db/api/frontend/capture) can be verified on a real Linux network namespace from any Mac, replacing Docker Desktop's isolated NAT (which silently drops `network_mode: host` and cannot see real LAN ARP/broadcast traffic — confirmed in 01-RESEARCH.md and locked by D-01/D-03).

Purpose: Unblocks the Phase 1 D-05 go/no-go checkpoint — capturing a real ARP packet from the LAN into `arp_events` — which requires a genuine Linux host network namespace with a real LAN-routable IP, not Docker Desktop's NAT-bridged macOS VM.

Output: `lima/innkeeper.yaml` (bridged-network Lima VM template with Docker provisioned), `scripts/dev-vm.sh` (up/down/ssh/status wrapper), and a README note documenting the one-time `brew install lima` prerequisite.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docker-compose.yml
@.env.example
@.planning/phases/01-foundation-capture-feasibility/01-RESEARCH.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create the Lima VM template with bridged networking and Docker provisioning</name>
  <files>lima/innkeeper.yaml</files>
  <action>
Create `lima/innkeeper.yaml` as a Lima instance config (Lima YAML schema, `vmType: vz`, `os: Linux`) that satisfies the same constraint D-01/D-03 assume for production: a real Linux host network namespace with a LAN-routable IP, so `network_mode: host` + `CAP_NET_RAW`/`CAP_NET_ADMIN` actually see real LAN ARP/broadcast traffic (Docker Desktop's NAT cannot — confirmed in 01-RESEARCH.md).

Key requirements for the YAML:
- `vmType: vz` (Apple Virtualization framework — required for Lima's `bridged` network mode on macOS; the default qemu vmType only supports Lima's NAT-style `lima:shared` network).
- `networks:` section using Lima's bridged network mode (`lima:<bridge-interface>` or the `socket_vmnet`-backed bridged config, e.g. `socket: ...` per Lima's bridged-network docs) so the guest gets a DHCP lease and a real LAN IP, not the `192.168.5.x` shared/NAT range. Add a comment above this block explaining why bridged (not shared/NAT) is mandatory — this is the entire point of the VM, per the constraint section.
- Base image: an `images:` entry pointing at the current default Lima Ubuntu LTS template location (use the same image reference Lima's own `templates/default.yaml` uses, since Lima ships that as the baseline — do not invent a URL; reference `template://default` via `LIMA_TEMPLATE` import or copy the images block from `limactl info` template list if available, falling back to the well-known Ubuntu cloud image releases URL pattern documented in Lima's own templates).
- `mounts:` entry for the repo root, writable: true, so the VM sees live source matching D-18 (mounted volumes for live code reload).
- `provision:` script (mode: system) that installs Docker Engine + the `docker compose` plugin via the official Docker apt repo (not Docker Desktop, not snap) on the Ubuntu guest, and adds the default Lima user to the `docker` group so `docker` works without sudo over SSH.
- `containerd:` system: false (Lima's bundled containerd is not needed; we use the provisioned Docker Engine instead) — set this explicitly to avoid Lima auto-starting its own containerd which is unnecessary here.
- `cpus`, `memory: "4GiB"`, `disk: "30GiB"` sized reasonably for running 4 docker-compose services plus Postgres.
- A `probes:` or `provision` (mode: dependency / boot) check that exits non-zero with a clear message if `docker compose version` is not available after provisioning, so failures surface immediately rather than silently.

Reference Lima's official YAML schema and the bridged-networking guide via Context7 or `lima.dev` docs if available; do not guess flag names — if a definitive bridged network YAML key cannot be confirmed, use Lima's documented `networks: - lima: shared` as bridged equivalent only after confirming via docs lookup, and add a comment flagging the assumption with the exact doc anchor checked.
  </action>
  <verify>
    <automated>test -f lima/innkeeper.yaml && grep -c "vmType: vz" lima/innkeeper.yaml | grep -v '^0$' && grep -c "mounts:" lima/innkeeper.yaml | grep -v '^0$'</automated>
  </verify>
  <done>lima/innkeeper.yaml exists, specifies vmType vz, a bridged (non-NAT) network entry with an explanatory comment, a repo mount, and a Docker Engine provisioning script targeting the official apt repo.</done>
</task>

<task type="auto">
  <name>Task 2: Build the dev-vm.sh wrapper script with up/down/ssh/status subcommands</name>
  <files>scripts/dev-vm.sh</files>
  <action>
Create `scripts/dev-vm.sh`, an executable bash script (`set -euo pipefail`, `#!/usr/bin/env bash`) that wraps `limactl` so the full Lima VM + docker-compose stack feels like a single `docker compose up`/`down` command. Use a fixed instance name `innkeeper` and reference `lima/innkeeper.yaml` via a path resolved relative to the script's own location (`SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`) so it works regardless of the caller's cwd.

Subcommands (dispatch on `$1`):
- `up`: If `limactl list --json` shows no `innkeeper` instance, run `limactl start --name=innkeeper "$SCRIPT_DIR/../lima/innkeeper.yaml"` (first boot + provisioning). If it exists but is stopped, `limactl start innkeeper`. After the VM is running, exec `limactl shell innkeeper -- bash -c 'cd /path/to/mounted/repo && docker compose up -d --build'` (use the actual mount point configured in Task 1's YAML — keep this path as a script-level variable `REPO_MOUNT` so it only needs updating in one place if the mount point changes). Print the VM's bridged LAN IP at the end (via `limactl shell innkeeper -- hostname -I` or equivalent) so the developer knows where to reach the frontend on :9999.
- `down`: Run `limactl shell innkeeper -- bash -c 'cd $REPO_MOUNT && docker compose down'` if the instance is running, then `limactl stop innkeeper`. Do NOT delete the VM disk on `down` (that is a separate, explicit operation) — `down` only stops compose + the VM so `up` is fast on the next run.
- `ssh`: Exec `limactl shell innkeeper` (or `limactl shell innkeeper -- bash` for an interactive login shell) to drop the developer into the VM.
- `status`: Run `limactl list innkeeper` and, if running, also print the bridged LAN IP and `docker compose ps` output from inside the VM so the developer can see container health at a glance.
- Any other/missing argument: print a usage block listing the four subcommands and exit 1.

Add a top-of-file comment documenting the one-time prerequisite (`brew install lima`) and that this script assumes `lima/innkeeper.yaml` (created in Task 1) defines the `innkeeper` Lima instance with bridged networking. Make the file executable (`chmod +x`).
  </action>
  <verify>
    <automated>test -x scripts/dev-vm.sh && bash -n scripts/dev-vm.sh && grep -E "up\)|down\)|ssh\)|status\)" scripts/dev-vm.sh | grep -v '^#' | wc -l | grep -v '^0$'</automated>
  </verify>
  <done>scripts/dev-vm.sh is executable, passes a bash syntax check (`bash -n`), and implements up/down/ssh/status subcommands that drive limactl against the Task 1 YAML and run docker compose inside the VM.</done>
</task>

<task type="auto">
  <name>Task 3: Document the Lima prerequisite and usage in README</name>
  <files>README.md</files>
  <action>
Check whether `README.md` already exists at the repo root (read it first if so; create new if not). Add a "Development (Lima VM)" section — append if other content exists, or create a minimal README with a project title line plus this section if the file does not exist yet. The section must cover, per the constraint that this directly unblocks D-05:

1. Why: Docker Desktop on macOS isolates containers behind NAT and cannot deliver real LAN ARP/broadcast traffic to a `network_mode: host` container (per 01-RESEARCH.md's confirmed limitation) — so verifying the Phase 1 capture spike (D-05: real ARP packet captured into `arp_events`) requires a genuine Linux network namespace with a bridged LAN IP.
2. One-time prerequisite: `brew install lima`.
3. Usage: `scripts/dev-vm.sh up` to create/start the VM and bring up the full docker-compose stack inside it (db, api, frontend, capture); `scripts/dev-vm.sh status` to check VM/container health and see the assigned LAN IP; `scripts/dev-vm.sh ssh` to shell into the VM; `scripts/dev-vm.sh down` to stop the stack and VM (non-destructive — VM disk is preserved for fast restart).
4. Note that the frontend will be reachable at the VM's bridged LAN IP on port 9999 (not localhost, since the VM has its own network identity distinct from the Mac host) — per D-12/D-13's host-IP-based access pattern, now satisfied by the VM's own LAN IP rather than the Mac's.

Keep this section concise (under ~25 lines) — it is operational documentation, not a tutorial.
  </action>
  <verify>
    <automated>test -f README.md && grep -c "brew install lima" README.md | grep -v '^0$' && grep -c "dev-vm.sh" README.md | grep -v '^0$'</automated>
  </verify>
  <done>README.md contains a Development section documenting the brew install lima prerequisite, the why (Docker Desktop NAT limitation blocking D-05 verification), and the four dev-vm.sh subcommands.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|--------------|
| Mac host → Lima VM | Lima VM is provisioned with a bridged network adapter that places it directly on the user's real LAN, exposed to the same broadcast domain as the home router and all other devices |
| Lima VM → docker-compose stack | The capture container inside the VM runs with CAP_NET_RAW/CAP_NET_ADMIN and host networking, identical to the production topology in D-03 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|------------------|
| T-quick-01 | Tampering | lima/innkeeper.yaml provisioning script | mitigate | Provision script installs Docker only from the official Docker apt repository (signed packages), not third-party scripts or curl-pipe-to-sh patterns |
| T-quick-02 | Information Disclosure | Bridged VM on real LAN | accept | This is a local dev tool on the developer's own trusted home network; the VM is no more exposed than the Mac host itself already is on that LAN |
| T-quick-03 | Elevation of Privilege | dev-vm.sh / limactl shell | accept | limactl shell access is equivalent to local SSH to a VM the developer owns; no remote exposure, no new attack surface beyond what `docker compose up` directly on a Linux box would already have |
| T-quick-SC | Tampering | No new package-manager installs in this plan (apt packages installed inside the VM via Task 1's provision script, not via npm/pip/cargo in the main repo) | accept | Docker Engine + compose plugin from Docker's official apt repo is a well-known, signed, standard install path — not a third-party/unverified package |
</threat_model>

<verification>
1. `lima/innkeeper.yaml` exists, specifies `vmType: vz`, a bridged network block with an explanatory comment, a repo mount, and a Docker Engine provisioning script.
2. `scripts/dev-vm.sh` is executable, passes `bash -n` syntax check, and implements all four subcommands (up/down/ssh/status) dispatching to `limactl`.
3. `README.md` documents the `brew install lima` prerequisite and the four dev-vm.sh subcommands.
4. Manual smoke test (requires Lima installed locally, not run by the automated verify commands): `scripts/dev-vm.sh up` boots a VM with a real LAN IP (not `192.168.5.x` Lima-shared range), `docker compose ps` inside the VM shows all 4 services running, `scripts/dev-vm.sh down` and `scripts/dev-vm.sh ssh` behave as documented.
</verification>

<success_criteria>
- A developer on any Mac with `brew install lima` can run `scripts/dev-vm.sh up` and get a Linux VM with a real bridged LAN IP running the full 4-service docker-compose stack, mounted to live repo source.
- This VM is sufficient to execute the Phase 1 D-05 go/no-go checkpoint (real ARP packet → `arp_events` row) which Docker Desktop's NAT network cannot support.
- `down`/`ssh`/`status` round out a complete, documented dev workflow with no manual VM setup steps beyond the one-time `brew install lima`.
</success_criteria>

<output>
Create `.planning/quick/260618-bmk-add-a-scripted-lima-vm-dev-environment-s/260618-bmk-SUMMARY.md` when done
</output>
