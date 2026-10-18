"""Resource-level authorization boundaries.

These tests exercise the 401 / 403 / 404 / 422 responses that protect the
team-scoped resources. They complement ``test_workflow.py`` (transition rules)
and ``test_items_crud.py`` (happy paths).
"""

from app.auth.security import create_access_token


# --- Authentication (401) -------------------------------------------------


def test_missing_token_is_unauthorized(client, seeded):
    assert client.get("/items").status_code == 401
    assert client.get(f"/items/{seeded.item_open}").status_code == 401
    write = client.post("/items", json={"title": "x", "type": "task", "team_id": 1})
    assert write.status_code == 401


def test_invalid_token_is_unauthorized(client, seeded):
    headers = {"Authorization": "Bearer not-a-real-token"}
    response = client.get("/items", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_expired_token_is_unauthorized(client, seeded, auth_headers):
    expired, _ = create_access_token(seeded.admin_id, expires_minutes=-1)
    response = client.get("/me", headers=auth_headers(expired))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


# --- Cross-team isolation (404, existence not leaked) ----------------------


def test_outsider_cannot_read_foreign_item_or_children(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["outsider"])
    assert client.get(f"/items/{seeded.item_open}", headers=headers).status_code == 404
    assert client.get(f"/items/{seeded.item_open}/activity", headers=headers).status_code == 404
    assert client.get(f"/items/{seeded.item_open}/comments", headers=headers).status_code == 404


def test_outsider_cannot_write_to_foreign_item(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["outsider"])
    comment = client.post(
        f"/items/{seeded.item_open}/comments", json={"body": "sneaky"}, headers=headers
    )
    assert comment.status_code == 404

    claim = client.post(f"/items/{seeded.item_open}/claim", headers=headers)
    assert claim.status_code == 404

    edit = client.patch(
        f"/items/{seeded.item_open}", json={"version": 1, "title": "hijack"}, headers=headers
    )
    assert edit.status_code == 404


def test_outsider_cannot_read_foreign_team_members(client, seeded, auth_headers):
    response = client.get(
        f"/teams/{seeded.payments_team_id}/members", headers=auth_headers(seeded.tokens["outsider"])
    )
    assert response.status_code == 404


def test_item_list_is_scoped_to_membership(client, seeded, auth_headers):
    response = client.get("/items", headers=auth_headers(seeded.tokens["outsider"]))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == seeded.item_support


# --- Role boundaries (403) -------------------------------------------------


def test_viewer_cannot_mutate(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["viewer"])

    create = client.post(
        "/items",
        json={"title": "nope", "type": "task", "team_id": seeded.payments_team_id},
        headers=headers,
    )
    assert create.status_code == 403

    claim = client.post(f"/items/{seeded.item_open}/claim", headers=headers)
    assert claim.status_code == 403

    comment = client.post(
        f"/items/{seeded.item_open}/comments", json={"body": "hi"}, headers=headers
    )
    assert comment.status_code == 403

    edit = client.patch(
        f"/items/{seeded.item_assigned}", json={"version": 1, "title": "nope"}, headers=headers
    )
    assert edit.status_code == 403


def test_member_cannot_transition_unassigned_item(client, seeded, auth_headers):
    response = client.post(
        f"/items/{seeded.item_open}/transition",
        json={"to_status": "in_progress", "version": 1},
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 403


def test_member_cannot_approve(client, seeded, auth_headers):
    response = client.post(
        f"/items/{seeded.item_awaiting}/transition",
        json={"to_status": "resolved", "version": 1},
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 403


def test_member_cannot_reassign_item(client, seeded, auth_headers):
    response = client.patch(
        f"/items/{seeded.item_assigned}",
        json={"version": 1, "assignee_id": seeded.lead_id},
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 403


# --- Assignee validation (422) ---------------------------------------------


def test_assignee_must_have_member_role(client, seeded, auth_headers):
    lead = auth_headers(seeded.tokens["lead"])
    created = client.post(
        "/items",
        json={
            "title": "Assigned to viewer",
            "type": "task",
            "team_id": seeded.payments_team_id,
            "assignee_id": seeded.viewer_id,
        },
        headers=lead,
    )
    assert created.status_code == 422
    assert created.json()["error"]["code"] == "invalid_assignee"

    patched = client.patch(
        f"/items/{seeded.item_open}",
        json={"version": 1, "assignee_id": seeded.viewer_id},
        headers=lead,
    )
    assert patched.status_code == 422
    assert patched.json()["error"]["code"] == "invalid_assignee"


def test_assignee_must_belong_to_team(client, seeded, auth_headers):
    response = client.patch(
        f"/items/{seeded.item_open}",
        json={"version": 1, "assignee_id": seeded.outsider_id},
        headers=auth_headers(seeded.tokens["lead"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_assignee"
