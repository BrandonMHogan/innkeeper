from src.modules.linked_apps.linked_manifest import LinkedModuleManifest


async def _login(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})
    login_response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert login_response.status_code == 200


async def test_list_linked_apps_returns_empty_list_when_authenticated(client):
    await _login(client)

    response = await client.get("/api/modules/linked-apps/")

    assert response.status_code == 200
    assert response.json() == []


def test_linked_module_manifest_round_trips_all_fields():
    manifest = LinkedModuleManifest(
        id="jellyfin",
        name="Jellyfin",
        icon_url="https://example.com/icon.png",
        target_url="https://jellyfin.local",
    )

    dumped = manifest.model_dump()

    assert dumped == {
        "id": "jellyfin",
        "name": "Jellyfin",
        "icon_url": "https://example.com/icon.png",
        "target_url": "https://jellyfin.local",
    }


async def test_list_linked_apps_requires_authentication(client):
    response = await client.get("/api/modules/linked-apps/")

    assert response.status_code == 401
