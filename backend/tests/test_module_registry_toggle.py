import pytest

from src.host.registry import ModuleRegistry
from typing import Protocol, runtime_checkable


@runtime_checkable
class SomeProtocol(Protocol):
    def do_thing(self) -> None: ...


class SomeImpl:
    def do_thing(self) -> None:
        pass


def test_register_then_resolve_returns_same_instance():
    registry = ModuleRegistry()
    instance = SomeImpl()

    registry.register(SomeProtocol, instance)

    assert registry.resolve(SomeProtocol) is instance


def test_register_same_protocol_twice_raises_runtime_error_naming_both():
    registry = ModuleRegistry()
    first = SomeImpl()
    second = SomeImpl()

    registry.register(SomeProtocol, first)

    with pytest.raises(RuntimeError) as exc_info:
        registry.register(SomeProtocol, second)

    message = str(exc_info.value)
    assert repr(first) in message
    assert repr(second) in message


def test_resolve_unregistered_protocol_raises_runtime_error_not_keyerror():
    registry = ModuleRegistry()

    with pytest.raises(RuntimeError) as exc_info:
        registry.resolve(SomeProtocol)

    assert "SomeProtocol" in str(exc_info.value)
    assert not isinstance(exc_info.value, KeyError)


# --- Plan 06: GET /api/modules/ + POST /api/modules/{id}/toggle ---------
#
# These tests exercise backend/src/routes/modules.py against the actual
# live app (src.main.app, via the `client` fixture) — the manifest list is
# already wired in by main.py's _load_native_modules()/modules.set_manifests()
# call, so no throwaway manifests/registry are constructed here; this is an
# end-to-end check of the host-level settings router against the five real
# native+linked modules (device_identity, devices, traffic, security,
# linked_apps) booted by Plan 05's ModuleLoader wiring.


async def _login(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})
    login_response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert login_response.status_code == 200


async def test_list_modules_excludes_device_identity_support_module(client):
    await _login(client)

    response = await client.get("/api/modules/")
    assert response.status_code == 200

    body = response.json()
    ids = {m["id"] for m in body}

    assert "device_identity" not in ids
    assert {"devices", "traffic", "security", "linked_apps"} <= ids
    for entry in body:
        assert "display_name" in entry
        assert "enabled" in entry


async def test_toggle_devices_flips_state_and_back(client):
    await _login(client)

    first = await client.post("/api/modules/devices/toggle", json={})
    assert first.status_code == 200
    first_body = first.json()
    assert "requires_confirmation" not in first_body
    assert first_body["enabled"] is False

    second = await client.post("/api/modules/devices/toggle", json={})
    assert second.status_code == 200
    assert second.json()["enabled"] is True


async def test_toggle_device_identity_requires_confirmation_naming_dependents(client):
    await _login(client)

    response = await client.post("/api/modules/device_identity/toggle", json={})
    assert response.status_code == 200

    body = response.json()
    assert body["requires_confirmation"] is True
    assert set(body["dependents"]) == {"devices", "traffic", "security"}

    confirmed = await client.post("/api/modules/device_identity/toggle", json={"confirm": True})
    assert confirmed.status_code == 200
    assert confirmed.json()["enabled"] is False


async def test_toggling_devices_off_immediately_404s_next_request_no_restart(client):
    await _login(client)

    toggle_off = await client.post("/api/modules/devices/toggle", json={})
    assert toggle_off.json()["enabled"] is False

    disabled_response = await client.get("/api/modules/devices/")
    assert disabled_response.status_code == 404

    toggle_on = await client.post("/api/modules/devices/toggle", json={})
    assert toggle_on.json()["enabled"] is True

    enabled_response = await client.get("/api/modules/devices/")
    assert enabled_response.status_code == 200
