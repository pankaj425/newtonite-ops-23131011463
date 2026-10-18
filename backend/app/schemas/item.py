from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ItemType, Priority, Status


class WorkItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    type: ItemType
    priority: Priority
    status: Status
    team_id: int
    assignee_id: int | None
    created_by_id: int
    due_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class WorkItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10000)
    type: ItemType
    priority: Priority = Priority.medium
    team_id: int
    assignee_id: int | None = None
    due_at: datetime | None = None


class WorkItemUpdate(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    priority: Priority | None = None
    assignee_id: int | None = None
    due_at: datetime | None = None


class TransitionRequest(BaseModel):
    to_status: Status
    version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=2000)


class PaginatedItems(BaseModel):
    items: list[WorkItemOut]
    total: int
    page: int
    page_size: int
    pages: int
