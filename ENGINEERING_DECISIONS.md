# Engineering Decisions

This document explains the decisions behind the implementation. Each entry
records the **context**, the **options** considered, the **choice** made, and
the **trade-off** accepted. It reflects the code that is actually in the
repository.

---

## 1. Data model and activity history

**Context.** Work items change frequently and the advisory requires an
auditable history that can never silently diverge from the item.

**Options.**
- Store history inside the `work_items` row (e.g. a JSON column).
- A separate `activity_events` table written in the same transaction.
- Event sourcing (the item's state is derived entirely from events).

**Choice.** A separate, append-only `activity_events` table. Each important
change writes a row in the **same transaction** as the item update; if either
fails, both roll back. The table is append-only and this is enforced in the
database by a `BEFORE UPDATE OR DELETE` trigger created in the initial
migration, in addition to application discipline.

**Trade-off.** Full event sourcing would give perfect reconstruction but adds
significant complexity for little benefit here. The chosen approach keeps reads
simple (the item row is the current state) while preserving an immutable audit
trail. The trigger adds a small write-path cost and means history cannot be
edited even by an administrator, which is intentional.

**Related:** roles are stored **per membership** (`user_id`, `team_id`, `role`),
so one user can be a lead in one team and a viewer in another.

---

## 2. Concurrency control for claims and edits

**Context.** Two users may try to claim the same unassigned item, and two
editors may submit updates based on a stale view of the item.

**Options.**
- Pessimistic locking (`SELECT ... FOR UPDATE`).
- Optimistic concurrency with a `version` column.
- A single atomic conditional `UPDATE` and check the affected row count.

**Choice.**
- **Claim** uses a single atomic statement:
  `UPDATE work_items SET assignee_id = :uid, version = version + 1
   WHERE id = :id AND assignee_id IS NULL AND status IN ('open','in_progress')`.
  A row count of `0` means someone else won → `409`. The `item_claimed`
  activity event is written in the same transaction.
- **Edits and transitions** use optimistic concurrency. `PATCH /items/{id}` and
  `POST /items/{id}/transition` require a `version` field in the body. The update
  is applied only `WHERE version = :version`; a row count of `0` returns `409`
  with `current_version` and the current item, so the client can reload.
- **Where `version` applies:** required for `PATCH` and `transition`; **not**
  required for `claim` (the atomic guard is the condition), but a successful
  claim **increments** `version` so other open editors become stale. Comments do
  not change the item and do **not** bump `version`.

**Trade-off.** Optimistic concurrency pushes conflict handling to the client
(show "reload latest") but avoids long-held locks and works well for low
contention. The atomic claim avoids a read-modify-write race entirely. The
version field is a small schema cost.

**Tests:** `tests/test_claim_concurrency.py` (two real threads, separate
sessions) and `tests/test_version_conflict.py`.

---

## 3. Team-based authorization

**Context.** Permissions must be enforced on the server, and item existence must
not leak across teams.

**Options.**
- A single global role per user.
- Per-membership roles with a permission matrix checked on every request.
- A policy engine or ABAC library.

**Choice.** Per-membership roles ordered `viewer < member < lead < admin`, with
explicit checks in `app/services/permissions.py` and `app/services/items.py`.
**Admin powers apply only to teams where the user holds an admin membership;
there is no global super-admin and no cross-team access.**

**Response code decision.**
- Items/teams **outside** the user's teams return **`404 Not Found`** so their
  existence is not leaked (consistent for reads and writes).
- Users who can see an item but lack the role for an action receive **`403`**.

**Final permission matrix**

| Action | Viewer | Member | Lead | Admin |
|---|:--:|:--:|:--:|:--:|
| Read items, comments, activity (own team) | ✅ | ✅ | ✅ | ✅ |
| Create item | ❌ | ✅ | ✅ | ✅ |
| Edit title / description / priority / due date | ❌ | ✅ (created or assigned) | ✅ (any team item) | ✅ (any team item) |
| Change assignee | ❌ | ❌ | ✅ | ✅ |
| Claim unassigned item | ❌ | ✅ | ✅ | ✅ |
| Add comment | ❌ | ✅ | ✅ | ✅ |
| `open → in_progress`, `in_progress → awaiting_approval` | ❌ | ✅ (assignee) | ✅ | ✅ |
| Approve / reject | ❌ | ❌ | ✅ | ✅ |
| `resolved → closed`, reopen `resolved → in_progress` | ❌ | ❌ | ✅ | ✅ |
| Access items of another team | ❌ | ❌ | ❌ | ❌ |

**Trade-off.** Hand-written checks are easy to read and audit but must be applied
consistently; a policy engine would centralise them but adds an abstraction the
team does not need at this size. Team scoping is applied **before** any filter in
`list_items`, so filters can never widen access.

**Tests:** `tests/test_items_crud.py`, `tests/test_workflow.py`.

---

## 4. Workflow and approval rules

**Context.** Status changes must follow a controlled workflow with a Lead-only
approval step.

**Options.**
- Scatter transition checks across endpoints.
- One declarative transition table consulted by a single service function.

**Choice.** A single `TRANSITIONS` table in `app/services/workflow.py` of
`(source, target, min_role, assignee_can, requires_assignee, requires_reason,
is_approval, is_rejection)`. The API never hard-codes rules; it looks them up.

| From | To | Who | Conditions |
|---|---|---|---|
| `open` | `in_progress` | Assignee, Lead, Admin | must have an assignee |
| `in_progress` | `awaiting_approval` | Assignee, Lead, Admin | — |
| `awaiting_approval` | `resolved` | Lead, Admin | **approval granted** |
| `awaiting_approval` | `in_progress` | Lead, Admin | **approval rejected**; reason required |
| `resolved` | `closed` | Lead, Admin | terminal |
| `resolved` | `in_progress` | Lead, Admin | reopen; reason required |
| `closed` | — | nobody | terminal |

Invalid transitions return **`422`** (`invalid_transition`). Approval and
rejection each write an extra `approval_granted` / `approval_rejected` event in
addition to the `status_changed` event.

**Self-approval decision: disabled.** A Lead or Admin cannot approve
(`awaiting_approval → resolved`) an item they are themselves assigned to; that
attempt returns `403`. This is the stricter default.

**Trade-off.** The declarative table is very testable and impossible to drift
between endpoints, at the cost of one small indirection layer. Disabling
self-approval is safer for an approval workflow but means a lone lead assigned to
an item needs a second lead to approve it.

**Tests:** `tests/test_workflow.py`.

---

## 5. Idempotency design

**Context.** A client may retry `POST /items` after a timeout and must not create
duplicate items.

**Options.**
- Ignore duplicates (unsafe).
- Dedupe on a natural key (e.g. title) — too lossy.
- An `Idempotency-Key` header with a stored response.

**Choice.** An `idempotency_keys` table, unique on `(user_id, key)`.
- A SHA-256 **hash of the request payload** is stored with the key.
- **Same key + same payload:** the stored response (status `201`, same item id)
  is returned; no new item is created.
- **Same key + different payload:** `422` (`idempotency_key_reuse`); nothing is
  created.
- **Concurrent same-key requests:** the unique constraint lets exactly one
  request reserve the key; the other blocks until the first commits and then
  replays the stored result (or receives `409` while the first is still in
  flight).
- Keys **expire** after `IDEMPOTENCY_TTL_HOURS` (default 24) and are treated as
  fresh afterwards.
- Claim and transition do **not** take idempotency keys; they are already guarded
  by state checks and `version`, and a repeated claim returns `409`.

**Trade-off.** Reservation rows and the payload hash add storage and one extra
write per create, but make retries safe. Storing the response body means replays
are exact. Expiry keeps the table from growing forever.

**Tests:** `tests/test_idempotency.py` (including a concurrent same-key test).

---

## 6. Pagination and search strategy

**Context.** Lists must be searchable, filterable, and paginated without
widening access.

**Options.**
- Offset/limit pagination.
- Cursor/keyset pagination.
- Client-side filtering.

**Choice.** **Offset/limit** pagination (`page`, `page_size`, capped at 100) with
a matching `COUNT(*)` for `total` and computed `pages`. Filters
(`status`, `priority`, `type`, `team_id`, `assignee_id`, `search`) are combined
with `AND`; `search` is a substring `ILIKE` over title and description. **Team
scoping is applied first**, then filters, then ordering
(`created_at DESC, id DESC`) and the page window. Passing a `team_id` outside the
user's teams yields an empty page rather than an error.

**Trade-off.** Offset pagination is simple and lets users jump to a page, but it
can shift if rows are inserted concurrently and is less efficient at deep
offsets. Keyset pagination would be more stable and scalable but is harder to
combine with arbitrary filters and page numbers; for this dataset offset
pagination is the right simplicity/stability balance.

**Tests:** `tests/test_search_pagination.py`.

---

## 7. What we intentionally did not build

- **No refresh tokens, SSO, or password reset.** Demo/login auth only, with
  short-lived access tokens; a real product needs a refresh flow.
- **No real async job runner / outbox.** The optional `jobs`/`outbox_events`
  behaviour was left out; the core behaviours chosen are claim concurrency,
  optimistic concurrency, idempotent create, server-enforced workflow, and
  resource-level authorization (five behaviours).
- **No WebSockets or polling.** The UI loads data on demand; real-time push is
  out of scope.
- **No email/SMS notifications, file attachments, or mobile app.**
- **No dedicated search engine.** Substring `ILIKE` only.
- **No optimistic-lock retry loop on the client.** On `409` the UI shows the
  current version and offers a "Reload latest" action instead of auto-merging.

These are also listed in the "Known limitations" section of the `README.md`.
