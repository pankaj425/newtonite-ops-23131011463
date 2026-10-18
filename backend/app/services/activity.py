from typing import Any

from sqlalchemy.orm import Session

from app.models import ActivityEvent, ActivityEventType


def record_event(
    db: Session,
    *,
    work_item_id: int,
    actor_id: int | None,
    event_type: ActivityEventType,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> ActivityEvent:
    """Add an activity event to the current transaction.

    The caller owns the transaction: the event is committed together with the
    work-item change it describes, so history cannot diverge from the item.
    """
    event = ActivityEvent(
        work_item_id=work_item_id,
        actor_id=actor_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(event)
    return event
