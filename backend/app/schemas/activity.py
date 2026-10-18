from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import ActivityEventType


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_item_id: int
    actor_id: int | None
    event_type: ActivityEventType
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    created_at: datetime
