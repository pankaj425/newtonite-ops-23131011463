import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import { atLeast, roleForTeam, useAuth } from "../auth.jsx";
import ErrorBanner from "../components/ErrorBanner";

const NEXT = {
  open: ["in_progress"],
  in_progress: ["awaiting_approval"],
  awaiting_approval: ["resolved", "in_progress"],
  resolved: ["closed", "in_progress"],
  closed: [],
};

const ASSIGNEE_NEXT = {
  open: ["in_progress"],
  in_progress: ["awaiting_approval"],
};

const REASON_REQUIRED = new Set(["awaiting_approval->in_progress", "resolved->in_progress"]);

const LABELS = {
  "open->in_progress": "Start progress",
  "in_progress->awaiting_approval": "Request approval",
  "awaiting_approval->resolved": "Approve",
  "awaiting_approval->in_progress": "Reject",
  "resolved->closed": "Close",
  "resolved->in_progress": "Reopen",
};

function allowedTargets(item, role, isAssignee) {
  if (!item) return [];
  const base = NEXT[item.status] || [];
  if (atLeast(role, "lead")) {
    return base.filter((target) => !(target === "resolved" && isAssignee));
  }
  if (isAssignee && atLeast(role, "member")) {
    return (ASSIGNEE_NEXT[item.status] || []).filter((target) => base.includes(target));
  }
  return [];
}

export default function ItemDetail() {
  const { id } = useParams();
  const { user, memberships } = useAuth();
  const [item, setItem] = useState(null);
  const [comments, setComments] = useState([]);
  const [activity, setActivity] = useState([]);
  const [members, setMembers] = useState([]);
  const [commentBody, setCommentBody] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    const loaded = await api(`/items/${id}`);
    const [loadedComments, loadedActivity] = await Promise.all([
      api(`/items/${id}/comments`),
      api(`/items/${id}/activity`),
    ]);
    setItem(loaded);
    setComments(loadedComments);
    setActivity(loadedActivity);
    try {
      setMembers(await api(`/teams/${loaded.team_id}/members`));
    } catch {
      setMembers([]);
    }
  }, [id]);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  if (!item) {
    return (
      <div className="panel">
        <ErrorBanner error={error} onReload={() => load().catch(setError)} />
        {!error && <p className="muted">Loading…</p>}
      </div>
    );
  }

  const role = roleForTeam(memberships, item.team_id);
  const isAssignee = item.assignee_id === user.id;
  const canEdit =
    atLeast(role, "lead") ||
    (atLeast(role, "member") && (item.created_by_id === user.id || isAssignee));
  const canClaim =
    atLeast(role, "member") &&
    !item.assignee_id &&
    ["open", "in_progress"].includes(item.status);
  const targets = allowedTargets(item, role, isAssignee);
  const teamName = memberships.find((m) => m.team_id === item.team_id)?.team_name || `Team ${item.team_id}`;
  const nameFor = (uid) => members.find((m) => m.id === uid)?.name || (uid ? `#${uid}` : "unassigned");

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const claim = () => run(() => api(`/items/${id}/claim`, { method: "POST" }));

  const transition = (to) =>
    run(async () => {
      const needsReason = REASON_REQUIRED.has(`${item.status}->${to}`);
      await api(`/items/${id}/transition`, {
        method: "POST",
        body: { to_status: to, version: item.version, reason: needsReason ? reason : undefined },
      });
      setReason("");
    });

  const addComment = (event) => {
    event.preventDefault();
    if (!commentBody.trim()) return;
    run(async () => {
      await api(`/items/${id}/comments`, { method: "POST", body: { body: commentBody } });
      setCommentBody("");
    });
  };

  return (
    <div>
      <div className="toolbar">
        <Link to="/items" className="muted">
          ← Back to work items
        </Link>
        <div className="spacer" />
        {canEdit && (
          <Link className="btn secondary" to={`/items/${item.id}/edit`}>
            Edit
          </Link>
        )}
      </div>

      <ErrorBanner error={error} onReload={() => load().catch(setError)} />

      <div className="panel">
        <h1>{item.title}</h1>
        <p className="muted">
          {teamName} · {item.type.replace("_", " ")} · created by {nameFor(item.created_by_id)} · v
          {item.version}
        </p>
        <div className="actions" style={{ marginBottom: 12 }}>
          <span className={`badge ${item.priority}`}>{item.priority}</span>
          <span className="badge status">{item.status.replace("_", " ")}</span>
          {item.due_at && <span className="badge">Due {new Date(item.due_at).toLocaleDateString()}</span>}
        </div>
        <p style={{ whiteSpace: "pre-wrap" }}>{item.description || "No description."}</p>
        <p className="muted">Assignee: {nameFor(item.assignee_id)}</p>

        <div className="actions">
          {canClaim && (
            <button type="button" onClick={claim} disabled={busy}>
              Claim this item
            </button>
          )}
          {targets.map((to) => (
            <button
              key={to}
              type="button"
              className={to === "in_progress" && item.status === "awaiting_approval" ? "danger" : ""}
              onClick={() => transition(to)}
              disabled={busy || (REASON_REQUIRED.has(`${item.status}->${to}`) && !reason.trim())}
            >
              {LABELS[`${item.status}->${to}`] || `Move to ${to}`}
            </button>
          ))}
        </div>
        {targets.some((to) => REASON_REQUIRED.has(`${item.status}->${to}`)) && (
          <div className="field" style={{ marginTop: 12 }}>
            <label>Reason (required for rejection / reopen)</label>
            <input value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
        )}
        {targets.length === 0 && !canClaim && (
          <p className="muted">No actions available for your role at this status.</p>
        )}
      </div>

      <div className="panel">
        <h2>Comments</h2>
        {comments.length === 0 && <p className="muted">No comments yet.</p>}
        {comments.map((comment) => (
          <div className="comment" key={comment.id}>
            <div className="meta">
              {nameFor(comment.author_id)} · {new Date(comment.created_at).toLocaleString()}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{comment.body}</div>
          </div>
        ))}
        {atLeast(role, "member") ? (
          <form onSubmit={addComment}>
            <div className="field">
              <label htmlFor="comment">Add a comment</label>
              <textarea
                id="comment"
                value={commentBody}
                onChange={(e) => setCommentBody(e.target.value)}
              />
            </div>
            <button type="submit" disabled={busy || !commentBody.trim()}>
              Post comment
            </button>
          </form>
        ) : (
          <p className="muted">Viewers cannot comment.</p>
        )}
      </div>

      <div className="panel">
        <h2>Activity</h2>
        <ul className="timeline">
          {activity.map((event) => (
            <li key={event.id}>
              <div>
                <strong>{event.event_type}</strong>
              </div>
              <div className="meta">
                {nameFor(event.actor_id)} · {new Date(event.created_at).toLocaleString()}
              </div>
              {(event.old_value || event.new_value) && (
                <div className="meta">
                  {event.old_value ? JSON.stringify(event.old_value) : "—"} →{" "}
                  {event.new_value ? JSON.stringify(event.new_value) : "—"}
                </div>
              )}
            </li>
          ))}
        </ul>
        {activity.length === 0 && <p className="muted">No activity recorded.</p>}
      </div>
    </div>
  );
}
