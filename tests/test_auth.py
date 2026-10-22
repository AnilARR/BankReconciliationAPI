from tests.conftest import PASSWORD


def test_login_and_me(client, admin_headers):
    response = client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_wrong_password(client):
    response = client.post("/api/v1/auth/token", data={"username": "admin", "password": "nope"})
    assert response.status_code == 401


def test_inactive_user_cannot_login(client):
    response = client.post("/api/v1/auth/token", data={"username": "disabled", "password": PASSWORD})
    assert response.status_code == 401


def test_endpoints_require_token(client):
    assert client.get("/api/v1/transactions").status_code == 401
    assert client.get("/api/v1/transactions", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_admin_creates_user(client, admin_headers):
    payload = {"username": "new.analyst", "password": "long-enough-pw", "role": "analyst"}
    response = client.post("/api/v1/auth/users", json=payload, headers=admin_headers)
    assert response.status_code == 201
    assert client.post("/api/v1/auth/users", json=payload, headers=admin_headers).status_code == 409
    login = client.post("/api/v1/auth/token", data={"username": "new.analyst", "password": "long-enough-pw"})
    assert login.status_code == 200


def test_non_admin_cannot_create_user(client, analyst_headers):
    payload = {"username": "someone", "password": "long-enough-pw"}
    assert client.post("/api/v1/auth/users", json=payload, headers=analyst_headers).status_code == 403
