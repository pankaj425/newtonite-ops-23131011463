export default function Pagination({ page, pages, total, pageSize, onChange }) {
  if (!total) return null;
  const last = Math.max(pages, 1);
  return (
    <div className="pager">
      <span className="muted">
        Page {page} of {last} · {total} item{total === 1 ? "" : "s"}
      </span>
      <button
        type="button"
        className="secondary"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Previous
      </button>
      <button
        type="button"
        className="secondary"
        disabled={page >= last}
        onClick={() => onChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
}
