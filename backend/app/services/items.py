from datetime import datetime
from math import ceil
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import conflict, forbidden, invalid, not_found
from app.models import (
    ActivityEvent,
    ActivityEventType,
    Comment,
    IdempotencyKey,
    ItemType,
    Membership,
    Priority,
    Role,
    Status,
    User,
    WorkItem,
)
from app.services import idempotency as idem
from app.services.activity import record_event
from app.services.permissions import (
    get_membership,
    role_at_least,
    require_membership,
    team_ids_for_user,
)
from app.services.workflow import can_perform, find_transition


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def serialize_item(item: WorkItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "type": item.type.value,
        "priority": item.priority.value,
        "status": item.status.value,
        "team_id": item.team_id,
        "assignee_id": item.assignee_id,
        "created_by_id": item.created_by_id,
        "due_at": _iso(item.due_at),
        "version": item.version,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def serialize_comment(comment: Comment) -> dict[str, Any]:
    return {
        "id": comment.id,
        "work_item_id": comment.work_item_id,
        "author_id": comment.author_id,
        "body": comment.body,
        "created_at": _iso(comment.created_at),
    }


def serialize_activity(event: ActivityEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "work_item_id": event.work_item_id,
        "actor_id": event.actor_id,
        "event_type": event.event_type.value,
        "old_value": event.old_value,
        "new_value": event.new_value,
        "created_at": _iso(event.created_at),
    }


def get_visible_item(db: Session, user: User, item_id: int) -> WorkItem:
    """Fetch an item, enforcing team membership.

    Items outside the user's teams return 404 so their existence is not leaked.
    """
    item = db.get(WorkItem, item_id)
    if item is None:
        raise not_found("Work item not found")
    if get_membership(db, user.id, item.team_id) is None:
        raise not_found("Work item not found")
    return item


def _version_conflict(db: Session, item_id: int):
    db.rollback()
    current = db.get(WorkItem, item_id)
    details: dict[str, Any] = {}
    if current is not None:
        details = {"current_version": current.version, "current_item": serialize_item(current)}
    return conflict(
        "version_conflict",
        "The item was modified by someone else. Reload the latest version and retry.",
        details,
    )


def _validate_assignee(db: Session, team_id: int, assignee_id: int) -> None:
    membership = get_membership(db, assignee_id, team_id)
    if membership is None:
        raise invalid("invalid_assignee", "The assignee is not a member of this team.")
    if not role_at_least(membership.role, Role.member):
        raise invalid(
            "invalid_assignee",
            "The assignee must have at least the member role in this team.",
        )


def _replay_or_conflict(record: IdempotencyKey, req_hash: str) -> tuple[int, dict[str, Any]]:
    if record.request_hash != req_hash:
        raise invalid(
            "idempotency_key_reuse",
            "This Idempotency-Key was already used with a different request body.",
        )
    if record.response_body is None:
        raise conflict(
            "idempotency_conflict",
            "A request with this Idempotency-Key is currently in progress. Retry shortly.",
        )
    return record.response_status or 201, record.response_body


def create_item(
    db: Session,
    user: User,
    payload: Any,
    idempotency_key: str | None = None,
) -> tuple[int, dict[str, Any]]:
    require_membership(db, user, payload.team_id, Role.member)
    if payload.assignee_id is not None:
        _validate_assignee(db, payload.team_id, payload.assignee_id)

    reserved: IdempotencyKey | None = None
    if idempotency_key:
        req_hash = idem.request_hash(payload.model_dump(mode="json"))
        existing = idem.find_key(db, user.id, idempotency_key)
        if existing is not None:
            if idem.is_expired(existing):
                db.delete(existing)
                db.flush()
            else:
                return _replay_or_conflict(existing, req_hash)

        reserved = IdempotencyKey(user_id=user.id, key=idempotency_key, request_hash=req_hash)
        db.add(reserved)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = idem.find_key(db, user.id, idempotency_key)
            if existing is None:
                raise conflict(
                    "idempotency_conflict",
                    "A concurrent request with this Idempotency-Key is in progress. Retry shortly.",
                )
            return _replay_or_conflict(existing, req_hash)

    item = WorkItem(
        title=payload.title,
        description=payload.description or "",
        type=payload.type,
        priority=payload.priority,
        status=Status.open,
        team_id=payload.team_id,
        assignee_id=payload.assignee_id,
        created_by_id=user.id,
        due_at=payload.due_at,
        version=1,
    )
    db.add(item)
    db.flush()

    record_event(
        db,
        work_item_id=item.id,
        actor_id=user.id,
        event_type=ActivityEventType.item_created,
        new_value={
            "title": item.title,
            "type": item.type.value,
            "priority": item.priority.value,
            "status": item.status.value,
            "team_id": item.team_id,
            "assignee_id": item.assignee_id,
        },
    )

    body = serialize_item(item)
    if reserved is not None:
        reserved.response_status = 201
        reserved.response_body = body

    db.commit()
    db.refresh(item)
    return 201, serialize_item(item)


def list_items(
    db: Session,
    user: User,
    *,
    view: str | None = None,
    team_id: int | None = None,
    status: Status | None = None,
    priority: Priority | None = None,
    item_type: ItemType | None = None,
    assignee_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    scoped_team_ids = team_ids_for_user(db, user.id)

    if view == "awaiting_my_approval":
        memberships = db.execute(
            select(Membership.team_id, Membership.role).where(Membership.user_id == user.id)
        ).all()
        scoped_team_ids = [team for team, role in memberships if role_at_least(role, Role.lead)]

    conditions = [WorkItem.team_id.in_(scoped_team_ids)] if scoped_team_ids else []

    if team_id is not None:
        if team_id not in scoped_team_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}
        conditions.append(WorkItem.team_id == team_id)
    if status is not None:
        conditions.append(WorkItem.status == status)
    if priority is not None:
        conditions.append(WorkItem.priority == priority)
    if item_type is not None:
        conditions.append(WorkItem.type == item_type)
    if assignee_id is not None:
        conditions.append(WorkItem.assignee_id == assignee_id)
    if search:
        like = f"%{search.strip()}%"
        conditions.append(or_(WorkItem.title.ilike(like), WorkItem.description.ilike(like)))

    if view == "assigned_to_me":
        conditions.append(WorkItem.assignee_id == user.id)
        conditions.append(WorkItem.status != Status.closed)
    elif view == "unassigned_urgent":
        conditions.append(WorkItem.assignee_id.is_(None))
        conditions.append(WorkItem.priority == Priority.urgent)
        conditions.append(WorkItem.status.notin_([Status.resolved, Status.closed]))
    elif view == "awaiting_my_approval":
        conditions.append(WorkItem.status == Status.awaiting_approval)

    if not scoped_team_ids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

    total = db.execute(select(func.count()).select_from(WorkItem).where(*conditions)).scalar_one()

    stmt = (
        select(WorkItem)
        .where(*conditions)
        .order_by(WorkItem.created_at.desc(), WorkItem.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.execute(stmt).scalars().all()

    return {
        "items": [serialize_item(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


def update_item(db: Session, user: User, item_id: int, payload: Any) -> dict[str, Any]:
    item = get_visible_item(db, user, item_id)
    membership = get_membership(db, user.id, item.team_id)
    role = membership.role
    is_lead = role_at_least(role, Role.lead)
    is_owner = item.created_by_id == user.id or item.assignee_id == user.id
    provided = payload.model_fields_set

    if role_at_least(role, Role.member) is False:
        raise forbidden("Viewers cannot edit work items.")
    if not is_lead and not is_owner:
        raise forbidden("You may only edit items you created or are assigned to.")
    if (
        "assignee_id" in provided
        and payload.assignee_id != item.assignee_id
        and not is_lead
    ):
        raise forbidden("Only a lead or admin can change the assignee.")

    if payload.version != item.version:
        raise _version_conflict(db, item.id)

    changes: dict[str, Any] = {}
    events: list[tuple[ActivityEventType, dict | None, dict | None]] = []

    if "title" in provided and payload.title is not None and payload.title != item.title:
        changes["title"] = payload.title
        events.append(
            (ActivityEventType.item_updated, {"title": item.title}, {"title": payload.title})
        )
    if (
        "description" in provided
        and payload.description is not None
        and payload.description != item.description
    ):
        changes["description"] = payload.description
        events.append(
            (
                ActivityEventType.item_updated,
                {"description": item.description},
                {"description": payload.description},
            )
        )
    if "priority" in provided and payload.priority is not None and payload.priority != item.priority:
        changes["priority"] = payload.priority
        events.append(
            (
                ActivityEventType.priority_changed,
                {"priority": item.priority.value},
                {"priority": payload.priority.value},
            )
        )
    if "due_at" in provided and payload.due_at != item.due_at:
        changes["due_at"] = payload.due_at
        events.append(
            (
                ActivityEventType.due_date_changed,
                {"due_at": _iso(item.due_at)},
                {"due_at": _iso(payload.due_at)},
            )
        )
    if "assignee_id" in provided and payload.assignee_id != item.assignee_id:
        if payload.assignee_id is not None:
            _validate_assignee(db, item.team_id, payload.assignee_id)
        changes["assignee_id"] = payload.assignee_id
        events.append(
            (
                ActivityEventType.assignee_changed,
                {"assignee_id": item.assignee_id},
                {"assignee_id": payload.assignee_id},
            )
        )

    if not changes:
        return serialize_item(item)

    result = db.execute(
        update(WorkItem)
        .where(WorkItem.id == item.id, WorkItem.version == payload.version)
        .values(**changes, version=WorkItem.version + 1)
    )
    if result.rowcount == 0:
        raise _version_conflict(db, item.id)

    for event_type, old_value, new_value in events:
        record_event(
            db,
            work_item_id=item.id,
            actor_id=user.id,
            event_type=event_type,
            old_value=old_value,
            new_value=new_value,
        )

    db.commit()
    db.refresh(item)
    return serialize_item(item)


def claim_item(db: Session, user: User, item_id: int) -> dict[str, Any]:
    item = get_visible_item(db, user, item_id)
    require_membership(db, user, item.team_id, Role.member)

    result = db.execute(
        update(WorkItem)
        .where(
            WorkItem.id == item.id,
            WorkItem.assignee_id.is_(None),
            WorkItem.status.in_([Status.open, Status.in_progress]),
        )
        .values(assignee_id=user.id, version=WorkItem.version + 1)
    )
    if result.rowcount == 0:
        db.rollback()
        current = db.get(WorkItem, item_id)
        if current is not None and current.assignee_id is not None:
            raise conflict(
                "already_claimed",
                "This item has already been claimed.",
                {"assignee_id": current.assignee_id},
            )
        raise conflict(
            "claim_conflict",
            "The item cannot be claimed in its current state.",
            {"status": current.status.value if current is not None else None},
        )

    record_event(
        db,
        work_item_id=item.id,
        actor_id=user.id,
        event_type=ActivityEventType.item_claimed,
        old_value={"assignee_id": None},
        new_value={"assignee_id": user.id},
    )
    db.commit()
    db.refresh(item)
    return serialize_item(item)


def transition_item(db: Session, user: User, item_id: int, payload: Any) -> dict[str, Any]:
    item = get_visible_item(db, user, item_id)
    membership = get_membership(db, user.id, item.team_id)
    role = membership.role
    rule = find_transition(item.status, payload.to_status)
    if rule is None:
        raise invalid(
            "invalid_transition",
            f"Cannot move a work item from '{item.status.value}' to '{payload.to_status.value}'.",
        )

    is_assignee = item.assignee_id == user.id
    if not can_perform(rule, role, is_assignee):
        raise forbidden("Your role cannot perform this transition.")
    if rule.requires_assignee and item.assignee_id is None:
        raise invalid(
            "assignee_required", "Assign the item (claim it) before moving it to in_progress."
        )
    if rule.requires_reason and not (payload.reason and payload.reason.strip()):
        raise invalid("reason_required", "A reason is required for this transition.")
    if rule.is_approval and is_assignee:
        raise forbidden(
            "Self-approval is disabled: you cannot approve an item you are assigned to."
        )

    if payload.version != item.version:
        raise _version_conflict(db, item.id)

    old_status = item.status
    result = db.execute(
        update(WorkItem)
        .where(
            WorkItem.id == item.id,
            WorkItem.version == payload.version,
            WorkItem.status == old_status,
        )
        .values(status=payload.to_status, version=WorkItem.version + 1)
    )
    if result.rowcount == 0:
        raise _version_conflict(db, item.id)

    status_new: dict[str, Any] = {"status": payload.to_status.value}
    if payload.reason:
        status_new["reason"] = payload.reason
    record_event(
        db,
        work_item_id=item.id,
        actor_id=user.id,
        event_type=ActivityEventType.status_changed,
        old_value={"status": old_status.value},
        new_value=status_new,
    )
    if rule.is_approval:
        record_event(
            db,
            work_item_id=item.id,
            actor_id=user.id,
            event_type=ActivityEventType.approval_granted,
            new_value={"status": payload.to_status.value, "reason": payload.reason},
        )
    elif rule.is_rejection:
        record_event(
            db,
            work_item_id=item.id,
            actor_id=user.id,
            event_type=ActivityEventType.approval_rejected,
            new_value={"status": payload.to_status.value, "reason": payload.reason},
        )

    db.commit()
    db.refresh(item)
    return serialize_item(item)


def add_comment(db: Session, user: User, item_id: int, body: str) -> dict[str, Any]:
    item = get_visible_item(db, user, item_id)
    require_membership(db, user, item.team_id, Role.member)

    comment = Comment(work_item_id=item.id, author_id=user.id, body=body)
    db.add(comment)
    db.flush()
    record_event(
        db,
        work_item_id=item.id,
        actor_id=user.id,
        event_type=ActivityEventType.comment_added,
        new_value={"comment_id": comment.id},
    )
    db.commit()
    db.refresh(comment)
    return serialize_comment(comment)


def get_activity(db: Session, user: User, item_id: int) -> list[dict[str, Any]]:
    item = get_visible_item(db, user, item_id)
    events = (
        db.execute(
            select(ActivityEvent)
            .where(ActivityEvent.work_item_id == item.id)
            .order_by(ActivityEvent.created_at.asc(), ActivityEvent.id.asc())
        )
        .scalars()
        .all()
    )
    return [serialize_activity(event) for event in events]


def get_comments(db: Session, user: User, item_id: int) -> list[dict[str, Any]]:
    item = get_visible_item(db, user, item_id)
    comments = (
        db.execute(
            select(Comment)
            .where(Comment.work_item_id == item.id)
            .order_by(Comment.created_at.asc(), Comment.id.asc())
        )
        .scalars()
        .all()
    )
    return [serialize_comment(comment) for comment in comments]
