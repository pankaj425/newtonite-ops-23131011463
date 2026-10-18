from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Membership, User
from app.schemas.team import TeamMemberOut
from app.services.permissions import require_membership

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_id}/members", response_model=list[TeamMemberOut])
def team_members(
    team_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TeamMemberOut]:
    require_membership(db, user, team_id)
    rows = db.execute(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.team_id == team_id)
        .order_by(User.name)
    ).all()
    return [
        TeamMemberOut(id=member.id, name=member.name, email=member.email, role=role)
        for member, role in rows
    ]
