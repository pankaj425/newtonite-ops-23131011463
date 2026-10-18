def create(client, seeded, headers, title, **overrides):
    payload = {
        "title": title,
        "description": "generated for tests",
        "type": "task",
        "priority": "medium",
        "team_id": seeded.payments_team_id,
    }
    payload.update(overrides)
    response = client.post("/items", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_search_filters_by_title(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["member"])
    response = client.get("/items?search=Settlement", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == seeded.item_assigned


def test_filter_by_status_and_priority(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["lead"])
    urg = client.get("/items?priority=urgent", headers=headers).json()
    assert all(item["priority"] == "urgent" for item in urg["items"])
    assert {item["id"] for item in urg["items"]} == {seeded.item_open}

    awaiting = client.get("/items?status=awaiting_approval", headers=headers).json()
    assert all(item["status"] == "awaiting_approval" for item in awaiting["items"])


def test_pagination(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["member"])
    for i in range(3):
        create(client, seeded, headers, f"Paged item {i}")

    first = client.get("/items?page=1&page_size=2", headers=headers).json()
    assert first["page"] == 1
    assert first["page_size"] == 2
    assert len(first["items"]) == 2
    assert first["total"] == 6
    assert first["pages"] == 3

    last = client.get("/items?page=3&page_size=2", headers=headers).json()
    assert len(last["items"]) == 2
    ids = {item["id"] for item in first["items"]} | {item["id"] for item in last["items"]}
    assert len(ids) == 4


def test_unassigned_urgent_view(client, seeded, auth_headers):
    response = client.get("/items?view=unassigned_urgent", headers=auth_headers(seeded.tokens["member"]))
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {seeded.item_open}


def test_assigned_to_me_view(client, seeded, auth_headers):
    response = client.get("/items?view=assigned_to_me", headers=auth_headers(seeded.tokens["member"]))
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {seeded.item_assigned, seeded.item_awaiting}


def test_awaiting_my_approval_view(client, seeded, auth_headers):
    member_view = client.get(
        "/items?view=awaiting_my_approval", headers=auth_headers(seeded.tokens["member"])
    ).json()
    assert member_view["items"] == []

    lead_view = client.get(
        "/items?view=awaiting_my_approval", headers=auth_headers(seeded.tokens["lead"])
    ).json()
    assert {item["id"] for item in lead_view["items"]} == {seeded.item_awaiting}


def test_search_never_crosses_teams(client, seeded, auth_headers, db):
    create(
        client,
        seeded,
        auth_headers(seeded.tokens["outsider"]),
        "Secret support item",
        team_id=seeded.support_team_id,
    )
    # The member is not in Support, so the search must not reveal the item.
    response = client.get("/items?search=Secret", headers=auth_headers(seeded.tokens["member"]))
    assert response.status_code == 200
    assert response.json()["total"] == 0
