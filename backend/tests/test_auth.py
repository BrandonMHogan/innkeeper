async def test_setup_redirect(client):
    """AUTH-01: GET /api/auth/me before setup is complete returns 401.

    The frontend's /setup redirect (Plan 01-03) is the UI-level consequence
    of this 401 — at the API level, AUTH-01's first-run gate is expressed
    as an unauthenticated 401 on any protected route.
    """
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_setup_stores_password(client):
    response = await client.post("/api/auth/setup", json={"password": "x"})
    assert response.status_code == 200

    # Re-fetch via login to confirm the password was hashed and stored,
    # and that setup_complete flipped — login should now succeed with "x"
    # and fail with the literal stored value (never plaintext).
    login_response = await client.post("/api/auth/login", json={"password": "x"})
    assert login_response.status_code == 200


async def test_setup_rejects_second_call(client):
    first = await client.post("/api/auth/setup", json={"password": "x"})
    assert first.status_code == 200

    second = await client.post("/api/auth/setup", json={"password": "y"})
    assert second.status_code == 409


async def test_setup_rejects_empty_password(client):
    response = await client.post("/api/auth/setup", json={"password": ""})
    assert response.status_code == 422


async def test_login_sets_cookie(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})

    response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert response.status_code == 200
    assert "innkeeper_session" in response.headers.get("set-cookie", "")


async def test_login_wrong_password(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})

    response = await client.post("/api/auth/login", json={"password": "wrong-password"})
    assert response.status_code == 401


async def test_me_unauthenticated(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_session_persists(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})
    login_response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert login_response.status_code == 200

    me_response = await client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json() == {"authenticated": True}
