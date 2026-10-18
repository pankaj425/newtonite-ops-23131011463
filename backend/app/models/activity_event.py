from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ActivityEventType
from app.models.user import utcnow


class ActivityEvent(Base):
    """Append-only audit trail. The application never updates or deletes these rows.

    The database additionally enforces append-only semantics with a trigger created
    in the initial migration.
    """

    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[ActivityEventType] = mapped_column(
        SAEnum(
            ActivityEventType,
            name="activity_event_type",
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )

    work_item: Mapped["WorkItem"] = relationship(back_populates="activity_events")
    actor: Mapped["User | None"] = relationship()
