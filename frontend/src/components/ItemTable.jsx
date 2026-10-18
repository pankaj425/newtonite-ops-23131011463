import { Link } from "react-router-dom";

function PriorityBadge({ value }) {
  return <span className={`badge ${value}`}>{value}</span>;
}

export default function ItemTable({ items, emptyText = "No work items." }) {
  if (!items || items.length === 0) {
    return <p className="muted">{emptyText}</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Priority</th>
          <th>Status</th>
          <th>Assignee</th>
          <th>Version</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td>
              <Link to={`/items/${item.id}`}>{item.title}</Link>
            </td>
            <td>{item.type.replace("_", " ")}</td>
            <td>
              <PriorityBadge value={item.priority} />
            </td>
            <td>
              <span className="badge status">{item.status.replace("_", " ")}</span>
            </td>
            <td>{item.assignee_id ? `#${item.assignee_id}` : <span className="muted">unassigned</span>}</td>
            <td>v{item.version}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
