from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Comment body must not be empty or whitespace only.")
        return value


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_item_id: int
    author_id: int | None
    body: str
    created_at: datetime
