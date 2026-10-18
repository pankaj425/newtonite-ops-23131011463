from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Membership, Team


def memberships_for_user(db: Session, user_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Membership, Team.name)
        .join(Team, Team.id == Membership.team_id)
        .where(Membership.user_id == user_id)
        .order_by(Team.name)
    ).all()
    return [
        {
            "id": membership.id,
            "user_id": membership.user_id,
            "team_id": membership.team_id,
            "team_name": team_name,
            "role": membership.role,
        }
        for membership, team_name in rows
    ]
