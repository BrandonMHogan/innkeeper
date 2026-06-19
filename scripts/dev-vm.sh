#!/usr/bin/env bash
#
# dev-vm.sh — wraps limactl so the Innkeeper Lima dev VM + docker-compose
# stack behaves like a single `docker compose up`/`down` command.
#
# One-time prerequisite (see README.md "Development (Lima VM)" section):
#   brew install lima
#   brew install socket_vmnet   # required for Lima's bridged network mode
#
# This script assumes lima/innkeeper.yaml (see that file) defines the
# `innkeeper` Lima instance with bridged networking and a Docker Engine
# provisioned via the official apt repo, with the repo mounted read-write.
#
# Subcommands: up | down | ssh | status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIMA_YAML="$SCRIPT_DIR/../lima/innkeeper.yaml"
INSTANCE="innkeeper"

# Must match `mounts: mountPoint` in lima/innkeeper.yaml — kept as a single
# variable here so it only needs updating in one place if the mount point
# in the Lima YAML changes.
REPO_MOUNT="/innkeeper"

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") <up|down|ssh|status>

  up      Create (if needed) and start the innkeeper Lima VM, then bring up
          the full docker-compose stack (db, api, frontend, capture) inside it.
  down    Stop the docker-compose stack and stop the VM (VM disk is preserved
          for a fast restart on the next 'up' — does not delete the VM).
  ssh     Open an interactive shell inside the VM.
  status  Show whether the VM is running, its bridged LAN IP, and
          'docker compose ps' output from inside the VM.
EOF
  exit 1
}

instance_exists() {
  limactl list --json 2>/dev/null | grep -q "\"name\":\"${INSTANCE}\""
}

instance_running() {
  limactl list --json 2>/dev/null | grep "\"name\":\"${INSTANCE}\"" | grep -q "\"status\":\"Running\""
}

vm_lan_ip() {
  # The bridged interface is configured as "lima0" in lima/innkeeper.yaml.
  limactl shell "$INSTANCE" -- sh -c "ip -4 addr show lima0 2>/dev/null | grep -oE 'inet [0-9.]+' | awk '{print \$2}'" || true
}

cmd_up() {
  if ! instance_exists; then
    echo "Creating and starting Lima instance '${INSTANCE}' (first boot + provisioning)..."
    limactl start --name="$INSTANCE" --tty=false "$LIMA_YAML"
  elif ! instance_running; then
    echo "Starting existing Lima instance '${INSTANCE}'..."
    limactl start "$INSTANCE"
  else
    echo "Lima instance '${INSTANCE}' is already running."
  fi

  echo "Bringing up docker compose stack inside the VM..."
  # `sg docker -c` (not plain `bash -c`): a freshly-provisioned VM's first
  # `limactl shell` session predates the docker-group membership the
  # provisioning script just granted (group changes don't retroactively
  # apply to an already-established session) — see docs/dev/mac_setup.md
  # "permission denied" troubleshooting note. `sg docker` activates the
  # group for this one command without needing a brand-new SSH session.
  limactl shell "$INSTANCE" -- sg docker -c "cd '${REPO_MOUNT}' && docker compose up -d --build"

  local ip
  ip="$(vm_lan_ip)"
  echo
  echo "VM is up. Bridged LAN IP: ${ip:-<unavailable>}"
  echo "Frontend should be reachable at http://${ip:-<vm-ip>}:9999"
}

cmd_down() {
  if instance_running; then
    echo "Stopping docker compose stack inside the VM..."
    limactl shell "$INSTANCE" -- sg docker -c "cd '${REPO_MOUNT}' && docker compose down" || true
    echo "Stopping Lima instance '${INSTANCE}'..."
    limactl stop "$INSTANCE"
  else
    echo "Lima instance '${INSTANCE}' is not running."
  fi
}

cmd_ssh() {
  # sg docker activates the docker group for this session — see the cmd_up
  # comment above on why a freshly-provisioned VM's session doesn't have it
  # by default.
  exec limactl shell "$INSTANCE" -- sg docker -c bash
}

cmd_status() {
  limactl list "$INSTANCE" || echo "Lima instance '${INSTANCE}' does not exist yet. Run '$(basename "$0") up' first."

  if instance_running; then
    local ip
    ip="$(vm_lan_ip)"
    echo
    echo "Bridged LAN IP: ${ip:-<unavailable>}"
    echo
    echo "docker compose ps:"
    limactl shell "$INSTANCE" -- sg docker -c "cd '${REPO_MOUNT}' && docker compose ps" || true
  fi
}

case "${1:-}" in
  up) cmd_up ;;
  down) cmd_down ;;
  ssh) cmd_ssh ;;
  status) cmd_status ;;
  *) usage ;;
esac
