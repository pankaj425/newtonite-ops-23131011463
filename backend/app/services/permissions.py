from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import forbidden, not_found
from app.models import Membership, Role, User
from app.models.enums import ROLE_ORDER


def role_at_least(role: Role, minimum: Role) -> bool:
    return ROLE_ORDER[role] >= ROLE_ORDER[minimum]


def get_membership(db: Session, user_id: int, team_id: int) -> Membership | None:
    return db.execute(
        select(Membership).where(
            Membership.user_id == user_id, Membership.team_id == team_id
        )
    ).scalar_one_or_none()


def team_ids_for_user(db: Session, user_id: int) -> list[int]:
    return list(
        db.execute(select(Membership.team_id).where(Membership.user_id == user_id)).scalars()
    )


def require_membership(
    db: Session, user: User, team_id: int, minimum: Role = Role.viewer
) -> Membership:
    """Return the user's membership, or raise.

    A user outside the team receives 404 so the existence of foreign teams and
    items is not leaked. A user inside the team with an insufficient role
    receives 403.
    """
    membership = get_membership(db, user.id, team_id)
    if membership is None:
        raise not_found("Team not found")
    if not role_at_least(membership.role, minimum):
        raise forbidden("Your role in this team is insufficient for this action")
    return membership
