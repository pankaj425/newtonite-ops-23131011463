import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import ErrorBanner from "../components/ErrorBanner";
import ItemTable from "../components/ItemTable";

const VIEWS = [
  { key: "assigned_to_me", title: "Assigned to me", desc: "Open work that is assigned to you" },
  { key: "unassigned_urgent", title: "Unassigned urgent", desc: "Urgent items nobody has claimed" },
  { key: "awaiting_my_approval", title: "Awaiting my approval", desc: "Items waiting on your approval" },
];

export default function Dashboard() {
  const [data, setData] = useState({});
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all(
      VIEWS.map((view) =>
        api(`/items?view=${view.key}&page_size=5`).then((result) => [view.key, result]),
      ),
    )
      .then((entries) => setData(Object.fromEntries(entries)))
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="toolbar">
        <h1>Dashboard</h1>
        <div className="spacer" />
        <Link className="btn" to="/items/new">
          New work item
        </Link>
      </div>

      <ErrorBanner error={error} />

      <div className="cards">
        {VIEWS.map((view) => (
          <div className="card" key={view.key}>
            <div className="value">{data[view.key]?.total ?? (loading ? "…" : 0)}</div>
            <div className="label">{view.title}</div>
          </div>
        ))}
      </div>

      {VIEWS.map((view) => (
        <div className="panel" key={view.key}>
          <h2>{view.title}</h2>
          <p className="muted">{view.desc}</p>
          <ItemTable
            items={data[view.key]?.items || []}
            emptyText={loading ? "Loading…" : "Nothing here right now."}
          />
        </div>
      ))}
    </div>
  );
}
