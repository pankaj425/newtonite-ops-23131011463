def base_payload(seeded, **overrides):
    data = {
        "title": "New work item",
        "description": "something to do",
        "type": "task",
        "priority": "medium",
        "team_id": seeded.payments_team_id,
    }
    data.update(overrides)
    return data


def test_member_can_create_item(client, seeded, auth_headers):
    response = client.post(
        "/items", json=base_payload(seeded), headers=auth_headers(seeded.tokens["member"])
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "open"
    assert body["version"] == 1
    assert body["created_by_id"] == seeded.member_id
    assert body["team_id"] == seeded.payments_team_id


def test_viewer_cannot_create_item(client, seeded, auth_headers):
    response = client.post(
        "/items", json=base_payload(seeded), headers=auth_headers(seeded.tokens["viewer"])
    )
    assert response.status_code == 403


def test_non_member_cannot_create_item_in_team(client, seeded, auth_headers):
    response = client.post(
        "/items", json=base_payload(seeded), headers=auth_headers(seeded.tokens["outsider"])
    )
    assert response.status_code == 404


def test_invalid_enum_is_rejected(client, seeded, auth_headers):
    response = client.post(
        "/items",
        json=base_payload(seeded, priority="immediately"),
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 422


def test_get_item_detail(client, seeded, auth_headers):
    response = client.get(
        f"/items/{seeded.item_open}", headers=auth_headers(seeded.tokens["member"])
    )
    assert response.status_code == 200
    assert response.json()["id"] == seeded.item_open


def test_outsider_gets_404_for_read_and_write(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["outsider"])
    assert client.get(f"/items/{seeded.item_open}", headers=headers).status_code == 404
    assert (
        client.patch(
            f"/items/{seeded.item_open}", json={"version": 1, "title": "hijack"}, headers=headers
        ).status_code
        == 404
    )
    assert client.post(f"/items/{seeded.item_open}/claim", headers=headers).status_code == 404
    assert (
        client.post(
            f"/items/{seeded.item_open}/transition",
            json={"to_status": "in_progress", "version": 1},
            headers=headers,
        ).status_code
        == 404
    )


def test_member_updates_own_item_and_increments_version(client, seeded, auth_headers):
    response = client.patch(
        f"/items/{seeded.item_assigned}",
        json={"version": 1, "title": "Settlement upload v2"},
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Settlement upload v2"
    assert body["version"] == 2


def test_member_cannot_change_assignee(client, seeded, auth_headers):
    response = client.patch(
        f"/items/{seeded.item_assigned}",
        json={"version": 1, "assignee_id": seeded.lead_id},
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 403


def test_lead_can_change_assignee(client, seeded, auth_headers):
    response = client.patch(
        f"/items/{seeded.item_open}",
        json={"version": 1, "assignee_id": seeded.member_id},
        headers=auth_headers(seeded.tokens["lead"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["assignee_id"] == seeded.member_id


def test_viewer_cannot_edit(client, seeded, auth_headers):
    response = client.patch(
        f"/items/{seeded.item_open}",
        json={"version": 1, "title": "nope"},
        headers=auth_headers(seeded.tokens["viewer"]),
    )
    assert response.status_code == 403


def test_viewer_cannot_comment(client, seeded, auth_headers):
    response = client.post(
        f"/items/{seeded.item_open}/comments",
        json={"body": "hello"},
        headers=auth_headers(seeded.tokens["viewer"]),
    )
    assert response.status_code == 403


def test_list_scopes_to_user_teams(client, seeded, auth_headers):
    response = client.get("/items", headers=auth_headers(seeded.tokens["member"]))
    assert response.status_code == 200
    team_ids = {item["team_id"] for item in response.json()["items"]}
    assert seeded.support_team_id not in team_ids
    assert team_ids <= {seeded.payments_team_id}


def test_team_filter_cannot_widen_access(client, seeded, auth_headers):
    response = client.get(
        f"/items?team_id={seeded.support_team_id}",
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0
