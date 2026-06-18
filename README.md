# Innkeeper

Self-hosted home network monitoring and management platform.

## Production (Linux host)

Innkeeper's actual deployment target is a real Linux host (per `D-01`/`D-02`
in `01-RESEARCH.md`) — no VM layer, no Lima, no `socket_vmnet`. There,
`network_mode: host` in `docker-compose.yml` works natively, so the entire
setup is:

```sh
# Install Docker + Compose plugin (e.g. via Docker's official apt repo)
docker compose up
```

Everything below this section is Mac-only developer tooling and does not
apply on Linux.

## Development (Lima VM, macOS only)

**Why:** Docker Desktop on macOS isolates containers behind NAT and cannot
deliver real LAN ARP/broadcast traffic to a `network_mode: host` container
(confirmed in `01-RESEARCH.md`). Verifying the Phase 1 capture spike (D-05:
capturing a real ARP packet into `arp_events`) requires a genuine Linux
network namespace with a bridged, LAN-routable IP — so local development
on a Mac uses a Lima VM instead of Docker Desktop directly. This is a
workaround for macOS's virtualization limits, not part of the product or
the production deployment.

**One-time prerequisites:**

```sh
brew install lima
brew install socket_vmnet   # required for Lima's bridged network mode
```

**Usage:**

```sh
scripts/dev-vm.sh up      # create/start the VM, bring up db/api/frontend/capture
scripts/dev-vm.sh status  # check VM + container health, see the VM's LAN IP
scripts/dev-vm.sh ssh     # shell into the VM
scripts/dev-vm.sh down    # stop the stack and VM (non-destructive)
```

The frontend is reachable at the VM's bridged LAN IP on port `9999` (printed
by `up`/`status`) — not `localhost`, since the VM has its own network
identity distinct from the Mac host.
