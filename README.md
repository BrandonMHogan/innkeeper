# Innkeeper

Self-hosted home network monitoring and management platform.

## Development (Lima VM)

**Why:** Docker Desktop on macOS isolates containers behind NAT and cannot
deliver real LAN ARP/broadcast traffic to a `network_mode: host` container
(confirmed in `01-RESEARCH.md`). Verifying the Phase 1 capture spike (D-05:
capturing a real ARP packet into `arp_events`) requires a genuine Linux
network namespace with a bridged, LAN-routable IP — so local development
uses a Lima VM instead of Docker Desktop directly.

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
