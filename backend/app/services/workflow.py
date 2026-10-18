"""Single source of truth for the work-item workflow.

Every status transition, its minimum role, and its extra conditions live in the
``TRANSITIONS`` table below. The API layer never hard-codes transition rules; it
looks them up here so the workflow cannot drift between endpoints.
"""

from dataclasses import dataclass

from app.models import Role, Status
from app.services.permissions import role_at_least


@dataclass(frozen=True)
class Transition:
    source: Status
    target: Status
    min_role: Role  # role that may perform it regardless of assignment (leads/admins)
    assignee_can: bool  # whether the current assignee (member+) may perform it
    requires_assignee: bool = False
    requires_reason: bool = False
    is_approval: bool = False
    is_rejection: bool = False


TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        source=Status.open,
        target=Status.in_progress,
        min_role=Role.lead,
        assignee_can=True,
        requires_assignee=True,
    ),
    Transition(
        source=Status.in_progress,
        target=Status.awaiting_approval,
        min_role=Role.lead,
        assignee_can=True,
    ),
    Transition(
        source=Status.awaiting_approval,
        target=Status.resolved,
        min_role=Role.lead,
        assignee_can=False,
        is_approval=True,
    ),
    Transition(
        source=Status.awaiting_approval,
        target=Status.in_progress,
        min_role=Role.lead,
        assignee_can=False,
        requires_reason=True,
        is_rejection=True,
    ),
    Transition(
        source=Status.resolved,
        target=Status.closed,
        min_role=Role.lead,
        assignee_can=False,
    ),
    Transition(
        source=Status.resolved,
        target=Status.in_progress,
        min_role=Role.lead,
        assignee_can=False,
        requires_reason=True,
    ),
)


def find_transition(source: Status, target: Status) -> Transition | None:
    for transition in TRANSITIONS:
        if transition.source == source and transition.target == target:
            return transition
    return None


def can_perform(transition: Transition, role: Role, is_assignee: bool) -> bool:
    if role_at_least(role, transition.min_role):
        return True
    if transition.assignee_can and is_assignee and role_at_least(role, Role.member):
        return True
    return False
