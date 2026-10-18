import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.models import ActivityEvent


def event_types(client, seeded, headers, item_id):
    response = client.get(f"/items/{item_id}/activity", headers=headers)
    assert response.status_code == 200
    return [event["event_type"] for event in response.json()]


def event_count(db, item_id):
    return db.execute(
        select(func.count()).select_from(ActivityEvent).where(ActivityEvent.work_item_id == item_id)
    ).scalar_one()


def test_item_created_event_is_recorded(client, seeded, auth_headers):
    response = client.post(
        "/items",
        json={
            "title": "Tracked item",
            "description": "d",
            "type": "task",
            "priority": "medium",
            "team_id": seeded.payments_team_id,
        },
        headers=auth_headers(seeded.tokens["member"]),
    )
    item_id = response.json()["id"]
    events = event_types(client, seeded, auth_headers(seeded.tokens["member"]), item_id)
    assert events == ["item_created"]


def test_priority_and_assignee_changes_are_recorded(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["lead"])
    response = client.patch(
        f"/items/{seeded.item_open}",
        json={"version": 1, "priority": "low", "assignee_id": seeded.member_id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    events = event_types(client, seeded, headers, seeded.item_open)
    assert "priority_changed" in events
    assert "assignee_changed" in events


def test_comment_is_recorded_and_does_not_bump_version(client, seeded, auth_headers):
    headers = auth_headers(seeded.tokens["member"])
    response = client.post(
        f"/items/{seeded.item_assigned}/comments", json={"body": "Looking into it"}, headers=headers
    )
    assert response.status_code == 201, response.text
    events = event_types(client, seeded, headers, seeded.item_assigned)
    assert "comment_added" in events

    item = client.get(f"/items/{seeded.item_assigned}", headers=headers).json()
    assert item["version"] == 1


def test_failed_transition_writes_no_activity(client, seeded, auth_headers, db):
    headers = auth_headers(seeded.tokens["lead"])
    first = client.post(
        f"/items/{seeded.item_awaiting}/transition",
        json={"to_status": "resolved", "version": 1},
        headers=headers,
    )
    assert first.status_code == 200
    count_after_success = event_count(db, seeded.item_awaiting)
    assert count_after_success == 2  # status_changed + approval_granted

    stale = client.post(
        f"/items/{seeded.item_awaiting}/transition",
        json={"to_status": "in_progress", "version": 1, "reason": "stale"},
        headers=headers,
    )
    assert stale.status_code == 409
    assert event_count(db, seeded.item_awaiting) == count_after_success


def test_failed_update_writes_no_activity(client, seeded, auth_headers, db):
    headers = auth_headers(seeded.tokens["lead"])
    before = event_count(db, seeded.item_open)
    response = client.patch(
        f"/items/{seeded.item_open}",
        json={"version": 1, "assignee_id": seeded.outsider_id},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_assignee"
    assert event_count(db, seeded.item_open) == before


def test_activity_events_are_append_only_in_database(client, seeded, auth_headers, db):
    response = client.post(
        "/items",
        json={
            "title": "Append only",
            "description": "d",
            "type": "task",
            "priority": "medium",
            "team_id": seeded.payments_team_id,
        },
        headers=auth_headers(seeded.tokens["member"]),
    )
    assert response.status_code == 201

    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE activity_events SET event_type = 'tampered'"))
        db.commit()
    db.rollback()
