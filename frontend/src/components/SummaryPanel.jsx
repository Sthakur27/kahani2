// Shows the LLM "story so far" recap for the current node. Falls back to a
// placeholder when there's no summary yet (e.g. at the story root, or before
// the summary has been generated).
export default function SummaryPanel({ summary }) {
  return (
    <section className="summary-panel">
      <h4 className="sidebar-title">Summary</h4>
      {summary ? (
        <div className="summary-content">
          <p>{summary}</p>
        </div>
      ) : (
        <div className="summary-placeholder">
          <p className="muted">
            A recap of the story so far will appear here as you branch in.
          </p>
        </div>
      )}
    </section>
  );
}
