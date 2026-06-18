"""Integration test for the full docker-compose.yml topology (PLAT-02).

Docker 29.1.3 and Docker Compose v2.40.3 are confirmed present in the
execution sandbox (01-RESEARCH.md Environment Availability table), so this
test runs for real against the repo-root docker-compose.yml rather than
skipping. A defensive skipif guard is retained only for environments where
Docker is genuinely absent.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

EXPECTED_SERVICES = {"db", "api", "frontend", "capture"}


def _docker_available() -> bool:
    return shutil.which("docker") is not None


@pytest.mark.skipif(not _docker_available(), reason="Docker not installed in this environment")
def test_all_services_healthy():
    # 1. The compose file must parse as valid Compose schema.
    config_result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert config_result.returncode == 0, (
        f"docker compose config failed:\nstdout={config_result.stdout}\nstderr={config_result.stderr}"
    )

    try:
        # 2. Bring the full stack up and wait for healthy/running state.
        up_result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "60",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert up_result.returncode == 0, (
            f"docker compose up failed:\nstdout={up_result.stdout}\nstderr={up_result.stderr}"
        )

        # 3. All 4 services must be present and not exited/unhealthy.
        ps_result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "--format", "json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert ps_result.returncode == 0, f"docker compose ps failed: {ps_result.stderr}"

        services_seen = {}
        for line in ps_result.stdout.strip().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            services_seen[entry["Service"]] = entry

        assert EXPECTED_SERVICES.issubset(services_seen.keys()), (
            f"Expected services {EXPECTED_SERVICES}, saw {set(services_seen.keys())}"
        )

        for name, entry in services_seen.items():
            state = entry.get("State", "").lower()
            health = entry.get("Health", "").lower()
            assert state != "exited", f"Service {name} exited unexpectedly: {entry}"
            assert health != "unhealthy", f"Service {name} is unhealthy: {entry}"

    finally:
        # 4. Always clean up, even on assertion failure.
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
