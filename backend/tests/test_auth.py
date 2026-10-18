def test_login_success_returns_token_and_memberships(client, seeded):
    response = client.post(
        "/auth/login", json={"email": "admin@test.dev", "password": "Password123!"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["email"] == "admin@test.dev"
    roles = {(m["team_name"], m["role"]) for m in body["memberships"]}
    assert ("Payments", "admin") in roles


def test_login_rejects_bad_password(client, seeded):
    response = client.post(
        "/auth/login", json={"email": "admin@test.dev", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_login_rejects_unknown_email(client, seeded):
    response = client.post(
        "/auth/login", json={"email": "nobody@test.dev", "password": "Password123!"}
    )
    assert response.status_code == 401


def test_me_requires_token(client, seeded):
    assert client.get("/me").status_code == 401


def test_me_rejects_invalid_token(client, seeded):
    response = client.get("/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_me_returns_user_and_memberships(client, seeded, auth_headers):
    response = client.get("/me", headers=auth_headers(seeded.tokens["member"]))
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == seeded.member_id
    assert any(
        m["team_id"] == seeded.payments_team_id and m["role"] == "member"
        for m in body["memberships"]
    )


def test_teams_endpoint_scopes_to_membership(client, seeded, auth_headers):
    response = client.get("/teams", headers=auth_headers(seeded.tokens["outsider"]))
    assert response.status_code == 200
    names = [team["name"] for team in response.json()]
    assert names == ["Support"]
