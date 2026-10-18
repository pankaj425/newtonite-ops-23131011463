from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ItemType, Priority, Status
from app.models.user import utcnow


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        Index("ix_work_items_team_status", "team_id", "status"),
        Index("ix_work_items_team_created", "team_id", "created_at"),
        Index("ix_work_items_assignee", "assignee_id"),
        Index("ix_work_items_priority", "priority"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    type: Mapped[ItemType] = mapped_column(
        SAEnum(ItemType, name="item_type", native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority, name="priority", native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Priority.medium,
    )
    status: Mapped[Status] = mapped_column(
        SAEnum(Status, name="status", native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Status.open,
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    team: Mapped["Team"] = relationship(back_populates="work_items")
    assignee: Mapped["User | None"] = relationship(foreign_keys=[assignee_id])
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="work_item", cascade="all, delete-orphan"
    )
    activity_events: Mapped[list["ActivityEvent"]] = relationship(
        back_populates="work_item", cascade="all, delete-orphan"
    )
