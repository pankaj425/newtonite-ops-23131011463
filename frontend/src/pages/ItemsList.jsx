import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, buildQuery } from "../api";
import { useAuth } from "../auth.jsx";
import ErrorBanner from "../components/ErrorBanner";
import ItemTable from "../components/ItemTable";
import Pagination from "../components/Pagination";

const EMPTY_FILTERS = {
  view: "",
  search: "",
  status: "",
  priority: "",
  type: "",
  team_id: "",
};

export default function ItemsList() {
  const { memberships } = useAuth();
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 0, page_size: 10 });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api(`/items${buildQuery({ ...filters, page, page_size: 10 })}`)
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [filters, page]);

  function update(key, value) {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value }));
  }

  return (
    <div>
      <div className="toolbar">
        <h1>Work items</h1>
        <div className="spacer" />
        <Link className="btn" to="/items/new">
          New work item
        </Link>
      </div>

      <div className="panel">
        <div className="toolbar">
          <div className="field">
            <label>Search</label>
            <input
              value={filters.search}
              placeholder="Title or description"
              onChange={(e) => update("search", e.target.value)}
            />
          </div>
          <div className="field">
            <label>View</label>
            <select value={filters.view} onChange={(e) => update("view", e.target.value)}>
              <option value="">All items</option>
              <option value="assigned_to_me">Assigned to me</option>
              <option value="unassigned_urgent">Unassigned urgent</option>
              <option value="awaiting_my_approval">Awaiting my approval</option>
            </select>
          </div>
          <div className="field">
            <label>Status</label>
            <select value={filters.status} onChange={(e) => update("status", e.target.value)}>
              <option value="">Any</option>
              {["open", "in_progress", "awaiting_approval", "resolved", "closed"].map((s) => (
                <option key={s} value={s}>
                  {s.replace("_", " ")}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Priority</label>
            <select value={filters.priority} onChange={(e) => update("priority", e.target.value)}>
              <option value="">Any</option>
              {["low", "medium", "high", "urgent"].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Type</label>
            <select value={filters.type} onChange={(e) => update("type", e.target.value)}>
              <option value="">Any</option>
              {["incident", "customer_issue", "payment", "compliance", "task"].map((t) => (
                <option key={t} value={t}>
                  {t.replace("_", " ")}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Team</label>
            <select value={filters.team_id} onChange={(e) => update("team_id", e.target.value)}>
              <option value="">All my teams</option>
              {memberships.map((m) => (
                <option key={m.team_id} value={m.team_id}>
                  {m.team_name}
                </option>
              ))}
            </select>
          </div>
          <button type="button" className="secondary" onClick={() => { setFilters(EMPTY_FILTERS); setPage(1); }}>
            Clear
          </button>
        </div>

        <ErrorBanner error={error} />
        <ItemTable
          items={data.items}
          emptyText={loading ? "Loading…" : "No matching work items."}
        />
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          pageSize={data.page_size}
          onChange={setPage}
        />
      </div>
    </div>
  );
}
