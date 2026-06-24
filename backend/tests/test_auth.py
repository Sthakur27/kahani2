def test_signup_login_me(client, auth):
    headers, username = auth()
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == username


def test_signup_validation(client):
    r = client.post("/api/auth/signup", json={"username": "a", "password": "x"})
    assert r.status_code == 400
    assert "error" in r.json()


def test_duplicate_username(client, auth):
    _, username = auth()
    r = client.post("/api/auth/signup", json={"username": username, "password": "pass1234"})
    assert r.status_code == 409


def test_login_bad_password(client, auth):
    _, username = auth()
    r = client.post("/api/auth/login", json={"username": username, "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
