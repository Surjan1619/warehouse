"""Login, roles and admin-only user management."""
from tests.conftest import TEST_PASSWORD


async def login(client, username, password=TEST_PASSWORD):
    return await client.post("/auth/login", data={"username": username, "password": password})


# --- Login ---
async def test_login_returns_token_and_user(client, worker):
    response = await login(client, "worker")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["user"] == {"id": worker[0].id, "username": "worker", "role": "worker", "is_active": True}


async def test_login_failures_look_the_same(client, worker, make_user):
    await make_user("fired", is_active=False)
    wrong_password = await login(client, "worker", "wrong-password")
    unknown_user = await login(client, "nobody")
    deactivated = await login(client, "fired")

    for response in (wrong_password, unknown_user, deactivated):
        assert response.status_code == 400
        assert response.json()["detail"] == "Incorrect username or password"


async def test_me_returns_the_token_owner(client, worker):
    user, headers = worker
    response = await client.get("/auth/me", headers=headers)
    assert response.json()["id"] == user.id


# --- Access without a valid session ---
async def test_requests_without_token_are_rejected(client):
    for path in ("/stock-items/", "/materials/", "/users/", "/auth/me", "/cuts/"):
        assert (await client.get(path)).status_code == 401, path


async def test_garbage_token_is_rejected(client):
    response = await client.get("/stock-items/", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


async def test_public_pages_need_no_token(client):
    assert (await client.get("/")).status_code == 200


async def test_cors_preflight_passes_without_token(client):
    response = await client.options(
        "/stock-items/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_there_is_no_public_registration(client, admin):
    body = {"username": "intruder", "password": "secret-password", "role": "admin"}
    assert (await client.post("/auth/register", json=body)).status_code == 401
    assert (await client.post("/auth/register", json=body, headers=admin[1])).status_code == 404


# --- User management is admin-only ---
async def test_admin_creates_a_worker_who_can_log_in(client, admin):
    _, headers = admin
    response = await client.post("/users/", json={"username": "ivan", "password": "ivan-password"}, headers=headers)
    assert response.status_code == 201
    created = response.json()
    assert created["role"] == "worker" and created["is_active"] is True
    assert "password" not in response.text

    assert (await login(client, "ivan", "ivan-password")).status_code == 200


async def test_worker_cannot_manage_users(client, admin, worker):
    worker_user, headers = worker
    new_admin = {"username": "sneaky", "password": "sneaky-password", "role": "admin"}

    assert (await client.get("/users/", headers=headers)).status_code == 403
    assert (await client.post("/users/", json=new_admin, headers=headers)).status_code == 403
    assert (await client.patch(f"/users/{worker_user.id}", json={"role": "admin"}, headers=headers)).status_code == 403


async def test_worker_can_use_the_warehouse(client, worker):
    assert (await client.get("/stock-items/", headers=worker[1])).status_code == 200


async def test_user_creation_is_validated(client, admin, worker):
    _, headers = admin

    async def create(**body):
        return (await client.post("/users/", json=body, headers=headers)).status_code

    assert await create(username="worker", password="some-password") == 409  # name taken
    assert await create(username="petr", password="123") == 422  # too short
    assert await create(username="petr", password="some-password", role="boss") == 422
    assert await create(username="ab", password="some-password") == 422


async def test_admin_resets_a_password(client, admin, worker):
    worker_user, _ = worker
    response = await client.patch(f"/users/{worker_user.id}", json={"password": "brand-new-password"}, headers=admin[1])
    assert response.status_code == 200
    assert (await login(client, "worker")).status_code == 400
    assert (await login(client, "worker", "brand-new-password")).status_code == 200


async def test_deactivated_user_is_locked_out_at_once(client, admin, worker):
    worker_user, worker_headers = worker
    assert (await client.get("/stock-items/", headers=worker_headers)).status_code == 200

    response = await client.patch(f"/users/{worker_user.id}", json={"is_active": False}, headers=admin[1])
    assert response.json()["is_active"] is False

    # The token issued earlier stops working without waiting for it to expire
    assert (await client.get("/stock-items/", headers=worker_headers)).status_code == 401
    assert (await client.get("/auth/me", headers=worker_headers)).status_code == 401
    assert (await login(client, "worker")).status_code == 400

    await client.patch(f"/users/{worker_user.id}", json={"is_active": True}, headers=admin[1])
    assert (await login(client, "worker")).status_code == 200


async def test_admin_cannot_lock_themselves_out(client, admin):
    admin_user, headers = admin
    assert (await client.patch(f"/users/{admin_user.id}", json={"is_active": False}, headers=headers)).status_code == 400
    assert (await client.patch(f"/users/{admin_user.id}", json={"role": "worker"}, headers=headers)).status_code == 400
    assert (await client.get("/users/", headers=headers)).status_code == 200


async def test_unknown_user_is_404(client, admin):
    response = await client.patch("/users/999", json={"is_active": False}, headers=admin[1])
    assert response.status_code == 404
