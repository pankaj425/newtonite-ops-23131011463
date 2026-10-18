from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.api.errors import AppError
from app.models import ItemType, Priority, Status, User, WorkItem
from app.services import items as items_service


def test_two_simultaneous_claims_only_one_succeeds(seeded, session_factory):
    """Real threads with separate sessions exercise PostgreSQL row locking."""
    barrier = Barrier(2)

    def claim(user_id: int):
        db = session_factory()
        try:
            user = db.get(User, user_id)
            barrier.wait()
            try:
                items_service.claim_item(db, user, seeded.item_open)
                return "ok"
            except AppError as exc:
                return exc.status_code
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, [seeded.member_id, seeded.lead_id]))

    assert results.count("ok") == 1
    assert results.count(409) == 1

    check = session_factory()
    try:
        item = check.get(WorkItem, seeded.item_open)
        assert item.assignee_id in {seeded.member_id, seeded.lead_id}
        assert item.version == 2
    finally:
        check.close()


def test_claim_increments_version(client, seeded, auth_headers):
    response = client.post(
        f"/items/{seeded.item_open}/claim", headers=auth_headers(seeded.tokens["member"])
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignee_id"] == seeded.member_id
    assert body["version"] == 2


def test_repeated_claim_returns_conflict(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["member"])
    assert client.post(f"/items/{seeded.item_open}/claim", headers=headers).status_code == 200
    again = client.post(f"/items/{seeded.item_open}/claim", headers=headers)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_claimed"


def test_viewer_cannot_claim(client, seeded, auth_headers):
    response = client.post(
        f"/items/{seeded.item_open}/claim", headers=auth_headers(seeded.tokens["viewer"])
    )
    assert response.status_code == 403


def test_cannot_claim_already_assigned(client, seeded, auth_headers):
    response = client.post(
        f"/items/{seeded.item_assigned}/claim", headers=auth_headers(seeded.tokens["member"])
    )
    assert response.status_code == 409


def test_cannot_claim_resolved_item(client, seeded, auth_headers, db):
    item = WorkItem(
        title="Resolved item",
        description="x",
        type=ItemType.task,
        priority=Priority.low,
        status=Status.resolved,
        team_id=seeded.payments_team_id,
        assignee_id=None,
        created_by_id=seeded.lead_id,
        version=1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    response = client.post(
        f"/items/{item.id}/claim", headers=auth_headers(seeded.tokens["member"])
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "claim_conflict"
