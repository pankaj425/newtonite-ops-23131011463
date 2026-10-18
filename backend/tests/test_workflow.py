from app.models import ItemType, Priority, Status, WorkItem


def transition(client, seeded, headers, item_id, to_status, version, reason=None):
    payload = {"to_status": to_status, "version": version}
    if reason is not None:
        payload["reason"] = reason
    return client.post(f"/items/{item_id}/transition", json=payload, headers=headers)


def activity(client, seeded, headers, item_id):
    response = client.get(f"/items/{item_id}/activity", headers=headers)
    assert response.status_code == 200
    return [event["event_type"] for event in response.json()]


def test_invalid_transition_open_to_closed(client, seeded, auth_headers):
    response = transition(
        client, seeded, auth_headers(seeded.tokens["lead"]), seeded.item_open, "closed", 1
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_transition"


def test_transition_requires_assignee(client, seeded, auth_headers):
    response = transition(
        client, seeded, auth_headers(seeded.tokens["lead"]), seeded.item_open, "in_progress", 1
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "assignee_required"


def test_viewer_cannot_transition(client, seeded, auth_headers):
    response = transition(
        client, seeded, auth_headers(seeded.tokens["viewer"]), seeded.item_assigned, "awaiting_approval", 1
    )
    assert response.status_code == 403


def test_assignee_moves_to_awaiting_approval(client, seeded, auth_headers):
    response = transition(
        client, seeded, auth_headers(seeded.tokens["member"]), seeded.item_assigned, "awaiting_approval", 1
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "awaiting_approval"
    assert response.json()["version"] == 2


def test_non_lead_cannot_approve(client, seeded, auth_headers):
    response = transition(
        client, seeded, auth_headers(seeded.tokens["member"]), seeded.item_awaiting, "resolved", 1
    )
    assert response.status_code == 403


def test_lead_approves_and_logs_event(client, seeded, auth_headers):
    lead = auth_headers(seeded.tokens["lead"])
    response = transition(client, seeded, lead, seeded.item_awaiting, "resolved", 1)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved"
    events = activity(client, seeded, lead, seeded.item_awaiting)
    assert "status_changed" in events
    assert "approval_granted" in events


def test_rejection_requires_reason(client, seeded, auth_headers):
    response = transition(
        client, seeded, auth_headers(seeded.tokens["lead"]), seeded.item_awaiting, "in_progress", 1
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "reason_required"


def test_rejection_moves_back_and_logs_event(client, seeded, auth_headers):
    lead = auth_headers(seeded.tokens["lead"])
    response = transition(
        client, seeded, lead, seeded.item_awaiting, "in_progress", 1, reason="Not enough evidence"
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in_progress"
    events = activity(client, seeded, lead, seeded.item_awaiting)
    assert "approval_rejected" in events


def test_self_approval_is_forbidden(client, seeded, auth_headers, db):
    item = WorkItem(
        title="Lead-owned approval",
        description="x",
        type=ItemType.task,
        priority=Priority.medium,
        status=Status.awaiting_approval,
        team_id=seeded.payments_team_id,
        assignee_id=seeded.lead_id,
        created_by_id=seeded.lead_id,
        version=1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    response = transition(
        client, seeded, auth_headers(seeded.tokens["lead"]), item.id, "resolved", 1
    )
    assert response.status_code == 403


def test_resolved_can_be_closed_and_is_terminal(client, seeded, auth_headers):
    lead = auth_headers(seeded.tokens["lead"])
    closed = transition(client, seeded, lead, seeded.item_awaiting, "resolved", 1)
    assert closed.status_code == 200
    assert closed.json()["version"] == 2

    final = transition(client, seeded, lead, seeded.item_awaiting, "closed", 2)
    assert final.status_code == 200
    assert final.json()["status"] == "closed"

    reopened = transition(client, seeded, lead, seeded.item_awaiting, "in_progress", 3, reason="Reopen")
    assert reopened.status_code == 422
    assert reopened.json()["error"]["code"] == "invalid_transition"
