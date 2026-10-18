"""Shared pytest fixtures.

Tests run against a dedicated PostgreSQL database (never SQLite) because the
concurrency and row-locking behaviour we care about only exists on a real
database engine.

Set ``TEST_DATABASE_URL`` before running pytest, for example:

    TEST_DATABASE_URL=postgresql+psycopg2://newtonite:newtonite@localhost:5433/newtonite_test
"""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://newtonite:newtonite@localhost:5433/newtonite_test",
)
# The application reads DATABASE_URL; point it at the test database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("IDEMPOTENCY_TTL_HOURS", "24")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.auth.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
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

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
TestingSessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)

TABLES = (
    "activity_events, comments, idempotency_keys, work_items, memberships, teams, users"
)


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")


def _truncate() -> None:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session_factory():
    return TestingSessionLocal


@pytest.fixture()
def seeded():
    """Reset the database and insert a known set of teams, users, and items."""
    _truncate()
    db = TestingSessionLocal()
    try:
        payments = Team(name="Payments")
        support = Team(name="Support")
        db.add_all([payments, support])
        db.flush()

        def make_user(email: str, name: str) -> User:
            user = User(email=email, name=name, password_hash=hash_password("Password123!"))
            db.add(user)
            db.flush()
            return user

        admin = make_user("admin@test.dev", "Ada Admin")
        lead = make_user("lead@test.dev", "Leo Lead")
        member = make_user("member@test.dev", "Mira Member")
        viewer = make_user("viewer@test.dev", "Vic Viewer")
        outsider = make_user("outsider@test.dev", "Omar Outsider")

        db.add_all(
            [
                Membership(user_id=admin.id, team_id=payments.id, role=Role.admin),
                Membership(user_id=lead.id, team_id=payments.id, role=Role.lead),
                Membership(user_id=member.id, team_id=payments.id, role=Role.member),
                Membership(user_id=viewer.id, team_id=payments.id, role=Role.viewer),
                Membership(user_id=outsider.id, team_id=support.id, role=Role.member),
            ]
        )
        db.flush()

        def make_item(**kwargs) -> WorkItem:
            item = WorkItem(**kwargs)
            db.add(item)
            db.flush()
            return item

        item_open = make_item(
            title="Duplicate charge",
            description="Customer charged twice",
            type=ItemType.customer_issue,
            priority=Priority.urgent,
            status=Status.open,
            team_id=payments.id,
            assignee_id=None,
            created_by_id=lead.id,
            version=1,
        )
        item_assigned = make_item(
            title="Settlement upload",
            description="Upload failing",
            type=ItemType.payment,
            priority=Priority.high,
            status=Status.in_progress,
            team_id=payments.id,
            assignee_id=member.id,
            created_by_id=lead.id,
            version=1,
        )
        item_awaiting = make_item(
            title="PCI checklist",
            description="Needs sign-off",
            type=ItemType.compliance,
            priority=Priority.medium,
            status=Status.awaiting_approval,
            team_id=payments.id,
            assignee_id=member.id,
            created_by_id=lead.id,
            version=1,
        )
        item_support = make_item(
            title="Support item",
            description="In the support team",
            type=ItemType.task,
            priority=Priority.low,
            status=Status.open,
            team_id=support.id,
            assignee_id=None,
            created_by_id=outsider.id,
            version=1,
        )
        db.commit()

        data = SimpleNamespace(
            payments_team_id=payments.id,
            support_team_id=support.id,
            admin_id=admin.id,
            lead_id=lead.id,
            member_id=member.id,
            viewer_id=viewer.id,
            outsider_id=outsider.id,
            item_open=item_open.id,
            item_assigned=item_assigned.id,
            item_awaiting=item_awaiting.id,
            item_support=item_support.id,
        )
        data.tokens = {
            "admin": create_access_token(admin.id)[0],
            "lead": create_access_token(lead.id)[0],
            "member": create_access_token(member.id)[0],
            "viewer": create_access_token(viewer.id)[0],
            "outsider": create_access_token(outsider.id)[0],
        }
        return data
    finally:
        db.close()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers():
    return auth
