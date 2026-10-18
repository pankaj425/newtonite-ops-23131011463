"""Seed demo teams, users, memberships, and sample work items.

Run from the backend directory:

    python scripts/seed.py

The script is idempotent: re-running it will not duplicate teams, users,
memberships, or sample items.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    ItemType,
    Membership,
    Priority,
    Role,
    Status,
    Team,
    User,
    WorkItem,
)

DEMO_PASSWORD = "Password123!"

TEAMS = ["Payments", "Support", "Compliance"]

USERS = [
    {
        "email": "admin@newtonite.dev",
        "name": "Ada Admin",
        "roles": {"Payments": Role.admin, "Support": Role.lead},
    },
    {
        "email": "lead@newtonite.dev",
        "name": "Leo Lead",
        "roles": {"Payments": Role.lead},
    },
    {
        "email": "member@newtonite.dev",
        "name": "Mira Member",
        "roles": {"Payments": Role.member, "Support": Role.member},
    },
    {
        "email": "viewer@newtonite.dev",
        "name": "Vic Viewer",
        "roles": {"Payments": Role.viewer},
    },
    {
        "email": "other@newtonite.dev",
        "name": "Omar Other",
        "roles": {"Compliance": Role.member},
    },
]

ITEMS = [
    {
        "title": "Duplicate charge on invoice #4482",
        "description": "Customer was charged twice for the same subscription renewal.",
        "type": ItemType.customer_issue,
        "priority": Priority.urgent,
        "status": Status.open,
        "team": "Payments",
        "assignee": None,
        "created_by": "admin@newtonite.dev",
        "due_in_days": 1,
    },
    {
        "title": "Settlement file failed to upload",
        "description": "The nightly settlement upload rejected the file with a checksum error.",
        "type": ItemType.payment,
        "priority": Priority.high,
        "status": Status.in_progress,
        "team": "Payments",
        "assignee": "member@newtonite.dev",
        "created_by": "lead@newtonite.dev",
        "due_in_days": 2,
    },
    {
        "title": "Update PCI-DSS compliance checklist",
        "description": "Annual checklist needs sign-off after the latest audit findings.",
        "type": ItemType.compliance,
        "priority": Priority.medium,
        "status": Status.awaiting_approval,
        "team": "Payments",
        "assignee": "member@newtonite.dev",
        "created_by": "lead@newtonite.dev",
        "due_in_days": 5,
    },
    {
        "title": "Customer cannot reset password",
        "description": "Reset email never arrives for two customers on the same domain.",
        "type": ItemType.customer_issue,
        "priority": Priority.high,
        "status": Status.open,
        "team": "Support",
        "assignee": None,
        "created_by": "admin@newtonite.dev",
        "due_in_days": 3,
    },
    {
        "title": "Onboarding call follow-up",
        "description": "Send the recap and next steps to the newly onboarded merchant.",
        "type": ItemType.task,
        "priority": Priority.low,
        "status": Status.resolved,
        "team": "Support",
        "assignee": "member@newtonite.dev",
        "created_by": "admin@newtonite.dev",
        "due_in_days": -1,
    },
    {
        "title": "Quarterly access review",
        "description": "Review privileged access for the finance systems.",
        "type": ItemType.compliance,
        "priority": Priority.medium,
        "status": Status.open,
        "team": "Compliance",
        "assignee": None,
        "created_by": "other@newtonite.dev",
        "due_in_days": 10,
    },
]


def get_or_create_team(db: Session, name: str) -> Team:
    team = db.execute(select(Team).where(Team.name == name)).scalar_one_or_none()
    if team is None:
        team = Team(name=name)
        db.add(team)
        db.flush()
    return team


def get_or_create_user(db: Session, email: str, name: str) -> User:
    user = db.execute(
        select(User).where(func.lower(User.email) == email.lower())
    ).scalar_one_or_none()
    if user is None:
        user = User(email=email, name=name, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()
    return user


def upsert_membership(db: Session, user: User, team: Team, role: Role) -> None:
    membership = db.execute(
        select(Membership).where(
            Membership.user_id == user.id, Membership.team_id == team.id
        )
    ).scalar_one_or_none()
    if membership is None:
        db.add(Membership(user_id=user.id, team_id=team.id, role=role))
    else:
        membership.role = role


def seed() -> None:
    db = SessionLocal()
    try:
        teams = {name: get_or_create_team(db, name) for name in TEAMS}
        users: dict[str, User] = {}
        for spec in USERS:
            users[spec["email"]] = get_or_create_user(db, spec["email"], spec["name"])
            for team_name, role in spec["roles"].items():
                upsert_membership(db, users[spec["email"]], teams[team_name], role)
        db.flush()

        now = datetime.now(timezone.utc)
        for spec in ITEMS:
            team = teams[spec["team"]]
            exists = db.execute(
                select(WorkItem).where(
                    WorkItem.team_id == team.id, WorkItem.title == spec["title"]
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue
            created_by = users[spec["created_by"]]
            assignee = users[spec["assignee"]] if spec["assignee"] else None
            db.add(
                WorkItem(
                    title=spec["title"],
                    description=spec["description"],
                    type=spec["type"],
                    priority=spec["priority"],
                    status=spec["status"],
                    team_id=team.id,
                    assignee_id=assignee.id if assignee else None,
                    created_by_id=created_by.id,
                    due_at=now + timedelta(days=spec["due_in_days"]),
                    version=1,
                )
            )

        db.commit()
    finally:
        db.close()

    print("Seed complete.")
    print("\nDemo accounts (password for all: %s)" % DEMO_PASSWORD)
    for spec in USERS:
        roles = ", ".join(f"{team}:{role.value}" for team, role in spec["roles"].items())
        print(f"  - {spec['email']:<26} {spec['name']:<14} ({roles})")


if __name__ == "__main__":
    seed()
