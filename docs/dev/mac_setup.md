# macOS Dev Environment Setup (Lima VM)

This doc is **Mac-only developer tooling** — it has nothing to do with the
real product or its deployment. See the "Production (Linux host)" section
in the root `README.md` for that; on a real Linux host you just run
`docker compose up` with no VM, no Lima, no `socket_vmnet`.

## Why this exists

Docker Desktop on macOS runs containers inside a hidden, NAT-isolated Linux
VM. `network_mode: host` does **not** give a container the Mac's real,
LAN-routable network interface — it's silently scoped to Docker Desktop's
internal NAT namespace, so real LAN ARP/broadcast traffic never reaches a
capture container running under Docker Desktop. Innkeeper's capture service
needs to see genuine LAN traffic (this is the Phase 1 D-05 go/no-go gate),
so local development on a Mac uses a real Linux VM (via [Lima](https://lima-vm.io/))
with **bridged** networking instead — that gives the VM a real, LAN-routable
IP, reproducing what a genuine Linux deployment host sees.

## One-time setup

These steps only need to be done once per Mac. They were worked out and
verified live while standing up Phase 1's docker-compose stack — every
command below is exactly what was run, in order, including the dead ends
(documented so you don't have to rediscover them).

### 1. Install Lima and socket_vmnet

```sh
brew install lima socket_vmnet
```

`socket_vmnet` is the helper Lima uses for bridged networking (a real LAN
IP, not Lima's own NAT-style `shared` network — which has the same
isolation problem as Docker Desktop).

### 2. Set up `socket_vmnet` for bridged networking

Lima's bridged mode requires `socket_vmnet`'s binary **and every parent
directory in its path** to be owned by root and non-writable by your user
(it's invoked via `sudo`, so nothing in that path can be tampered with).
Homebrew's `Cellar` directories are user-owned by design (so `brew upgrade`
works), which conflicts with that requirement.

**Do not `chown` Homebrew's Cellar directories** — it works, but it breaks
`brew upgrade socket_vmnet` afterward, and Lima's check cascades up the
*entire* path chain (chowning just the binary isn't enough; you'd end up
chowning `Cellar/socket_vmnet/<version>/`, then `Cellar/socket_vmnet/`, and
so on). The correct fix (and what Lima's own docs recommend) is to install
a copy into a dedicated root-owned location outside Homebrew:

```sh
# Find your installed version first:
ls /opt/homebrew/Cellar/socket_vmnet/

# Install a root-owned copy (replace <version> below):
sudo mkdir -p /opt/socket_vmnet/bin
sudo cp /opt/homebrew/Cellar/socket_vmnet/<version>/bin/socket_vmnet /opt/socket_vmnet/bin/socket_vmnet
sudo chown -R root:wheel /opt/socket_vmnet
sudo chmod 755 /opt/socket_vmnet/bin/socket_vmnet

# Point Lima's network config at the new path:
sed -i '' 's#socketVMNet: .*#socketVMNet: "/opt/socket_vmnet/bin/socket_vmnet"#' ~/.lima/_config/networks.yaml

# Generate and install the sudoers rule that lets Lima invoke it passwordlessly:
limactl sudoers | sudo tee /etc/sudoers.d/lima
```

If `~/.lima/_config/networks.yaml` doesn't exist yet, run any `limactl`
command once first (e.g. `limactl --version`) to let Lima create its
default config, then run the steps above.

**Verify it worked:** `limactl sudoers | sudo tee /etc/sudoers.d/lima` should
print sudoers rules for `bridged`/`host`/`shared` network daemons with no
`FATA` error lines above them. If you see `file ... is not owned by "root"`,
the path in step 2 still has a user-owned ancestor directory — re-check
with `ls -ld /opt/socket_vmnet /opt/socket_vmnet/bin`.

### 3. Start the VM

```sh
scripts/dev-vm.sh up
```

First run downloads an Ubuntu 24.04 cloud image and provisions Docker
inside the VM (a few minutes). Subsequent runs are fast (a few seconds).

This prints the VM's bridged LAN IP — note it down, you'll need it to open
the app in a browser (e.g. `http://10.0.0.161:9999`).

## Day-to-day usage

```sh
scripts/dev-vm.sh up      # create/start the VM, bring up db/api/frontend/capture
scripts/dev-vm.sh status  # check VM + container health, see the VM's LAN IP
scripts/dev-vm.sh ssh     # shell into the VM
scripts/dev-vm.sh down    # stop the stack and VM (non-destructive — disk/data preserved)
```

The repo is mounted live at `/innkeeper` inside the VM — edits on your Mac
are immediately visible inside the VM (it's a real bind mount, not a copy).

## `.env` setup

Copy `.env.example` to `.env` and fill in:

| Variable | Value |
|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` | any value, e.g. `innkeeper` |
| `POSTGRES_PASSWORD` | generate one: `openssl rand -hex 24` |
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<password>@db:5432/<db>` — must match the three values above |
| `SESSION_SECRET` | generate one: `openssl rand -hex 32` |
| `API_PORT` | `8000` (default) |
| `PUBLIC_API_URL` | **leave empty.** Frontend and API are same-origin via an nginx proxy (`/api/` → `api:8000`) — this avoids a cross-origin `SameSite=Lax` cookie bug that silently breaks login. Do not set this to the VM's IP; it doesn't need it. |
| `FRONTEND_URL` | `http://<vm-bridged-ip>:9999` — must match exactly what's in your browser's address bar, since the backend's CORS check compares against this literally. Get the IP from `scripts/dev-vm.sh status`. |

**Heredoc gotcha:** if you build `.env` by pasting a multi-line `cat > .env
<<EOF ... EOF` block into a terminal, some terminals auto-indent pasted
lines, which becomes literal leading whitespace in the file and breaks
`KEY=value` parsing. After writing `.env`, sanity-check with:

```sh
grep -nc '^[[:space:]]' .env   # should print 0
sed -n 's/^\([A-Z_]*\)=.*/\1/p' .env | cat -n   # should list exactly the var names, nothing else
```

If you see stray non-variable lines (e.g. a literal `EOF`), the heredoc
didn't close cleanly the first time — clean up with:
`grep -E '^[A-Z_]+=' .env > .env.cleaned && mv .env.cleaned .env`

## Bringing up the stack

```sh
scripts/dev-vm.sh up
```

Or manually, inside the VM:

```sh
scripts/dev-vm.sh ssh
cd /innkeeper
docker compose up -d --build
docker compose ps
```

If you ever see `permission denied while trying to connect to the docker
API at unix:///var/run/docker.sock` when running `docker compose` by hand
inside the VM, your shell session predates the VM's docker-group
provisioning taking effect. Either start a fresh `scripts/dev-vm.sh ssh`
session, or run the command prefixed with `sg docker -c '...'` once.

## Verifying it's actually working

1. **Containers healthy:** `docker compose ps` inside the VM — all 4
   services (`db`, `api`, `frontend`, `capture`) should show `Up` (`db`
   additionally shows `healthy`).
2. **Browser flow:** open `http://<vm-bridged-ip>:9999/setup` from your Mac
   (or any other device on the same LAN — that's the whole point of
   bridged networking). Set a password, confirm redirect to `/login`, log
   in, confirm redirect to `/dashboard`.
3. **D-05 go/no-go gate (real ARP capture):** force some ARP traffic and
   check the database:
   ```sh
   # Inside the VM:
   sudo ip neigh del <your-gateway-ip> dev lima0
   ping -c 2 -I lima0 <your-gateway-ip>

   cd /innkeeper
   docker compose exec db psql -U innkeeper -d innkeeper -c "SELECT * FROM arp_events;"
   ```
   You should see at least one row.
4. **Clean shutdown:** `docker compose down` should complete in well under
   30 seconds — the capture container has a graceful SIGTERM handler and
   should never hang.

## Known issues already fixed in `lima/innkeeper.yaml`

These were real bugs hit while setting this up for the first time — already
fixed in the committed config, documented here so you recognize them if
you ever see similar symptoms after editing the YAML yourself:

- **`message:` field doesn't support `{{.User}}` templating** (only
  `mounts.mountPoint` does) — caused a fatal template error on every
  `limactl start`. Fixed by using a fixed `/innkeeper` mount point instead
  of templating the path.
- **The Lima guest user is not reliably uid 1000.** Lima matches the guest
  UID to your host UID by default (e.g. `501` on a single-user Mac), so a
  provisioning script that assumes uid 1000 silently grants Docker group
  membership to the wrong (or a nonexistent) user. Fixed by detecting the
  primary user via the home-directory suffix Lima always adds (`.guest` or
  `.linux`), not a hardcoded UID.
