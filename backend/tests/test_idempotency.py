from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.models import User, WorkItem


def payload(seeded, title="Idempotent item"):
    return {
        "title": title,
        "description": "created with an idempotency key",
        "type": "task",
        "priority": "medium",
        "team_id": seeded.payments_team_id,
    }


def count_items_by_title(db, title):
    return db.execute(
        select(func.count()).select_from(WorkItem).where(WorkItem.title == title)
    ).scalar_one()


def test_repeat_same_key_same_payload_creates_one_item(client, seeded, auth_headers, db):
    headers = {**auth_headers(seeded.tokens["member"]), "Idempotency-Key": "key-1"}
    first = client.post("/items", json=payload(seeded), headers=headers)
    second = client.post("/items", json=payload(seeded), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert count_items_by_title(db, "Idempotent item") == 1


def test_same_key_different_payload_is_rejected(client, seeded, auth_headers, db):
    headers = {**auth_headers(seeded.tokens["member"]), "Idempotency-Key": "key-2"}
    first = client.post("/items", json=payload(seeded, title="Original"), headers=headers)
    assert first.status_code == 201

    second = client.post("/items", json=payload(seeded, title="Different"), headers=headers)
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "idempotency_key_reuse"

    assert count_items_by_title(db, "Original") == 1
    assert count_items_by_title(db, "Different") == 0


def test_different_keys_create_different_items(client, seeded, auth_headers, db):
    member = auth_headers(seeded.tokens["member"])
    first = client.post(
        "/items", json=payload(seeded), headers={**member, "Idempotency-Key": "key-a"}
    )
    second = client.post(
        "/items", json=payload(seeded), headers={**member, "Idempotency-Key": "key-b"}
    )
    assert first.json()["id"] != second.json()["id"]
    assert count_items_by_title(db, "Idempotent item") == 2


def test_without_key_creates_duplicates(client, seeded, auth_headers, db):
    member = auth_headers(seeded.tokens["member"])
    client.post("/items", json=payload(seeded), headers=member)
    client.post("/items", json=payload(seeded), headers=member)
    assert count_items_by_title(db, "Idempotent item") == 2


def test_keys_are_scoped_per_user(client, seeded, auth_headers, db):
    # Members may only create in their own teams; use lead and admin of Payments.
    lead_headers = {**auth_headers(seeded.tokens["lead"]), "Idempotency-Key": "shared-key"}
    admin_headers = {**auth_headers(seeded.tokens["admin"]), "Idempotency-Key": "shared-key"}

    first = client.post("/items", json=payload(seeded, title="By lead"), headers=lead_headers)
    second = client.post("/items", json=payload(seeded, title="By admin"), headers=admin_headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_concurrent_same_key_creates_only_one(client, seeded, auth_headers, db):
    headers = {**auth_headers(seeded.tokens["member"]), "Idempotency-Key": "concurrent-key"}
    body = payload(seeded, title="Concurrent")

    def send():
        return client.post("/items", json=body, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: send(), range(2)))

    statuses = sorted(r.status_code for r in responses)
    assert statuses[0] in (201, 409)
    assert all(s in (201, 409) for s in statuses)
    assert count_items_by_title(db, "Concurrent") == 1
