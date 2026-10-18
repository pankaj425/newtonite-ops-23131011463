import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import { atLeast, roleForTeam, useAuth } from "../auth.jsx";
import ErrorBanner from "../components/ErrorBanner";

const TYPES = ["incident", "customer_issue", "payment", "compliance", "task"];
const PRIORITIES = ["low", "medium", "high", "urgent"];

function toIso(value) {
  return value ? new Date(value).toISOString() : null;
}

function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}`;
}

export default function ItemForm({ mode }) {
  const isEdit = mode === "edit";
  const { id } = useParams();
  const navigate = useNavigate();
  const { memberships } = useAuth();
  const editableTeams = memberships.filter((m) => atLeast(m.role, "member"));

  const [form, setForm] = useState({
    title: "",
    description: "",
    type: "task",
    priority: "medium",
    team_id: editableTeams[0]?.team_id ?? "",
    assignee_id: "",
    due_at: "",
  });
  const [item, setItem] = useState(null);
  const [members, setMembers] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [idemKey, setIdemKey] = useState(() => crypto.randomUUID());

  const loadItem = async () => {
    const loaded = await api(`/items/${id}`);
    setItem(loaded);
    setForm({
      title: loaded.title,
      description: loaded.description,
      type: loaded.type,
      priority: loaded.priority,
      team_id: loaded.team_id,
      assignee_id: loaded.assignee_id ? String(loaded.assignee_id) : "",
      due_at: toLocalInput(loaded.due_at),
    });
  };

  useEffect(() => {
    if (isEdit) {
      loadItem().catch(setError);
    }
  }, [isEdit, id]);

  useEffect(() => {
    if (!form.team_id) {
      setMembers([]);
      return;
    }
    api(`/teams/${form.team_id}/members`)
      .then(setMembers)
      .catch(() => setMembers([]));
  }, [form.team_id]);

  useEffect(() => {
    if (!isEdit) setIdemKey(crypto.randomUUID());
  }, [JSON.stringify(form), isEdit]);

  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const canChangeAssignee = atLeast(roleForTeam(memberships, Number(form.team_id)), "lead");

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isEdit) {
        const payload = {
          version: item.version,
          title: form.title,
          description: form.description,
          priority: form.priority,
          due_at: toIso(form.due_at),
        };
        if (canChangeAssignee) {
          payload.assignee_id = form.assignee_id ? Number(form.assignee_id) : null;
        }
        const updated = await api(`/items/${id}`, { method: "PATCH", body: payload });
        navigate(`/items/${updated.id}`);
      } else {
        const payload = {
          title: form.title,
          description: form.description,
          type: form.type,
          priority: form.priority,
          team_id: Number(form.team_id),
          assignee_id: form.assignee_id ? Number(form.assignee_id) : null,
          due_at: toIso(form.due_at),
        };
        const created = await api(`/items`, {
          method: "POST",
          body: payload,
          idempotencyKey: idemKey,
        });
        navigate(`/items/${created.id}`);
      }
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (isEdit && !item) {
    return (
      <div className="panel">
        <ErrorBanner error={error} onReload={() => loadItem().catch(setError)} />
        {!error && <p className="muted">Loading…</p>}
      </div>
    );
  }

  if (!isEdit && editableTeams.length === 0) {
    return (
      <div className="panel">
        <h2>Cannot create work items</h2>
        <p className="muted">Your role is viewer in every team, so you cannot create items.</p>
        <Link to="/items">Back to work items</Link>
      </div>
    );
  }

  return (
    <div>
      <div className="toolbar">
        <h1>{isEdit ? "Edit work item" : "New work item"}</h1>
      </div>
      <ErrorBanner error={error} onReload={isEdit ? () => loadItem().catch(setError) : undefined} />

      <form className="panel" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="title">Title</label>
          <input
            id="title"
            value={form.title}
            maxLength={300}
            required
            onChange={(e) => set("title", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={form.description}
            maxLength={10000}
            onChange={(e) => set("description", e.target.value)}
          />
        </div>
        <div className="row">
          {!isEdit && (
            <div className="field">
              <label htmlFor="type">Type</label>
              <select id="type" value={form.type} onChange={(e) => set("type", e.target.value)}>
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="field">
            <label htmlFor="priority">Priority</label>
            <select
              id="priority"
              value={form.priority}
              onChange={(e) => set("priority", e.target.value)}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          {!isEdit && (
            <div className="field">
              <label htmlFor="team">Team</label>
              <select
                id="team"
                value={form.team_id}
                onChange={(e) => set("team_id", Number(e.target.value))}
              >
                {editableTeams.map((m) => (
                  <option key={m.team_id} value={m.team_id}>
                    {m.team_name} ({m.role})
                  </option>
                ))}
              </select>
            </div>
          )}
          {(canChangeAssignee || !isEdit) && (
            <div className="field">
              <label htmlFor="assignee">Assignee</label>
              <select
                id="assignee"
                value={form.assignee_id}
                onChange={(e) => set("assignee_id", e.target.value)}
              >
                <option value="">Unassigned</option>
                {members.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.name} ({member.role})
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="field">
            <label htmlFor="due">Due date</label>
            <input
              id="due"
              type="datetime-local"
              value={form.due_at}
              onChange={(e) => set("due_at", e.target.value)}
            />
          </div>
        </div>

        <div className="actions">
          <button type="submit" disabled={busy}>
            {busy ? "Saving…" : isEdit ? "Save changes" : "Create work item"}
          </button>
          <Link className="btn secondary" to={isEdit ? `/items/${id}` : "/items"}>
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
