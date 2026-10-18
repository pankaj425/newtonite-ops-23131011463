from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import ItemType, Priority, Status, User
from app.schemas import (
    ActivityOut,
    CommentCreate,
    CommentOut,
    PaginatedItems,
    TransitionRequest,
    WorkItemCreate,
    WorkItemOut,
    WorkItemUpdate,
)
from app.services import items as item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=PaginatedItems)
def list_items(
    view: str | None = Query(default=None, pattern="^(assigned_to_me|unassigned_urgent|awaiting_my_approval)$"),
    team_id: int | None = None,
    status: Status | None = None,
    priority: Priority | None = None,
    item_type: ItemType | None = Query(default=None, alias="type"),
    assignee_id: int | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedItems:
    result = item_service.list_items(
        db,
        user,
        view=view,
        team_id=team_id,
        status=status,
        priority=priority,
        item_type=item_type,
        assignee_id=assignee_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return PaginatedItems.model_validate(result)


@router.post("", response_model=WorkItemOut, status_code=201)
def create_item(
    payload: WorkItemCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    status_code, body = item_service.create_item(db, user, payload, idempotency_key)
    return JSONResponse(status_code=status_code, content=body)


@router.get("/{item_id}", response_model=WorkItemOut)
def get_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkItemOut:
    item = item_service.get_visible_item(db, user, item_id)
    return WorkItemOut.model_validate(item_service.serialize_item(item))


@router.patch("/{item_id}", response_model=WorkItemOut)
def update_item(
    item_id: int,
    payload: WorkItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkItemOut:
    return WorkItemOut.model_validate(item_service.update_item(db, user, item_id, payload))


@router.post("/{item_id}/claim", response_model=WorkItemOut)
def claim_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkItemOut:
    return WorkItemOut.model_validate(item_service.claim_item(db, user, item_id))


@router.post("/{item_id}/transition", response_model=WorkItemOut)
def transition_item(
    item_id: int,
    payload: TransitionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkItemOut:
    return WorkItemOut.model_validate(
        item_service.transition_item(db, user, item_id, payload)
    )


@router.get("/{item_id}/activity", response_model=list[ActivityOut])
def get_activity(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ActivityOut]:
    return [ActivityOut.model_validate(event) for event in item_service.get_activity(db, user, item_id)]


@router.get("/{item_id}/comments", response_model=list[CommentOut])
def get_comments(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    return [
        CommentOut.model_validate(comment)
        for comment in item_service.get_comments(db, user, item_id)
    ]


@router.post("/{item_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    item_id: int,
    payload: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    return CommentOut.model_validate(
        item_service.add_comment(db, user, item_id, payload.body)
    )
