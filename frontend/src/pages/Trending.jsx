import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getLeaderboard } from "../api.js";
import "./Trending.css";

function snippet(text, max = 160) {
  if (!text) return "";
  const t = text.trim();
  return t.length > max ? t.slice(0, max).trimEnd() + "…" : t;
}

export default function Trending() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    getLeaderboard()
      .then((data) => {
        if (alive) setItems(data);
      })
      .catch((err) => {
        if (alive) setError(err.message || "Failed to load leaderboard");
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="trending">
      <h1 className="trending-title">🔥 Trending branches</h1>
      <p className="trending-sub muted">
        The most-loved story paths across every prompt.
      </p>

      {error && <p className="error">{error}</p>}
      {!error && items === null && <p className="muted">Loading…</p>}
      {!error && items !== null && items.length === 0 && (
        <p className="muted">No branches yet — go write one!</p>
      )}

      {!error && items && items.length > 0 && (
        <ol className="trending-list">
          {items.map((it, i) => (
            <li key={it.node_id} className="trending-row">
              <Link
                to={`/stories/${it.story_id}/nodes/${it.node_id}`}
                className="trending-link"
              >
                <span className="trending-rank">#{i + 1}</span>
                <span className="trending-body">
                  <span className="trending-story muted">{it.story_title}</span>
                  {it.edge_prompt && (
                    <span className="trending-prompt">“{it.edge_prompt}”</span>
                  )}
                  {it.content && (
                    <span className="trending-snippet">
                      {snippet(it.content)}
                    </span>
                  )}
                  <span className="trending-meta muted">
                    ▲ {it.score} · 👁 {it.view_count}
                    {it.author ? ` · by @${it.author}` : ""}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
