export default function ErrorBanner({ error, onReload }) {
  if (!error) return null;
  const isStale = error.code === "version_conflict";
  const isConflict =
    error.code === "already_claimed" || error.code === "claim_conflict";

  return (
    <div className={`alert ${isStale || isConflict ? "warn" : "error"}`}>
      <div className="title">
        {isStale
          ? "This item changed on the server"
          : isConflict
            ? "Conflict"
            : "Request failed"}
      </div>
      <div>{error.message}</div>
      {isStale && error.details?.current_version !== undefined && (
        <div className="meta">
          Current version: {error.details.current_version}
        </div>
      )}
      {isStale && onReload && (
        <div style={{ marginTop: 8 }}>
          <button type="button" onClick={onReload}>
            Reload latest
          </button>
        </div>
      )}
    </div>
  );
}
