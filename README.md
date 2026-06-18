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

## Development (macOS only)

macOS can't run the capture container's real-LAN-traffic spike directly
under Docker Desktop (see why in the doc below). Local dev on a Mac uses a
Lima VM with bridged networking instead.

See **[docs/dev/mac_setup.md](docs/dev/mac_setup.md)** for the full setup —
one-time prerequisites, `.env` configuration, day-to-day `scripts/dev-vm.sh`
usage, and how to verify the stack is actually working.
