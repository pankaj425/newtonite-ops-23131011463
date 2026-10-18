from enum import Enum


class Role(str, Enum):
    viewer = "viewer"
    member = "member"
    lead = "lead"
    admin = "admin"


class ItemType(str, Enum):
    incident = "incident"
    customer_issue = "customer_issue"
    payment = "payment"
    compliance = "compliance"
    task = "task"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Status(str, Enum):
    open = "open"
    in_progress = "in_progress"
    awaiting_approval = "awaiting_approval"
    resolved = "resolved"
    closed = "closed"


class ActivityEventType(str, Enum):
    item_created = "item_created"
    item_updated = "item_updated"
    assignee_changed = "assignee_changed"
    priority_changed = "priority_changed"
    due_date_changed = "due_date_changed"
    status_changed = "status_changed"
    comment_added = "comment_added"
    approval_granted = "approval_granted"
    approval_rejected = "approval_rejected"
    item_claimed = "item_claimed"


ROLE_ORDER: dict[Role, int] = {
    Role.viewer: 0,
    Role.member: 1,
    Role.lead: 2,
    Role.admin: 3,
}
