from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Membership, Team, User
from app.schemas import MeOut, TeamOut, UserOut
from app.services.accounts import memberships_for_user

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
def read_me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MeOut:
    return MeOut(
        user=UserOut.model_validate(user),
        memberships=memberships_for_user(db, user.id),
    )


@router.get("/teams", response_model=list[TeamOut])
def my_teams(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[TeamOut]:
    teams = (
        db.execute(
            select(Team)
            .join(Membership, Membership.team_id == Team.id)
            .where(Membership.user_id == user.id)
            .order_by(Team.name)
        )
        .scalars()
        .all()
    )
    return [TeamOut.model_validate(team) for team in teams]
