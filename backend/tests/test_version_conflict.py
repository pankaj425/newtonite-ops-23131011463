def test_stale_patch_is_rejected_and_data_unchanged(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["member"])

    first = client.patch(
        f"/items/{seeded.item_assigned}", json={"version": 1, "title": "First edit"}, headers=headers
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2

    stale = client.patch(
        f"/items/{seeded.item_assigned}", json={"version": 1, "title": "Stale edit"}, headers=headers
    )
    assert stale.status_code == 409
    body = stale.json()["error"]
    assert body["code"] == "version_conflict"
    assert body["details"]["current_version"] == 2
    assert body["details"]["current_item"]["title"] == "First edit"

    current = client.get(f"/items/{seeded.item_assigned}", headers=headers).json()
    assert current["title"] == "First edit"
    assert current["version"] == 2


def test_patch_without_version_is_rejected(client, seeded, auth_headers):
    response = client.patch(
        f"/items/{seeded.item_assigned}",
        json={"title": "No version"},
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 422


def test_stale_transition_is_rejected(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["lead"])

    first = client.post(
        f"/items/{seeded.item_awaiting}/transition",
        json={"to_status": "resolved", "version": 1},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2

    stale = client.post(
        f"/items/{seeded.item_awaiting}/transition",
        json={"to_status": "in_progress", "version": 1, "reason": "too late"},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"
