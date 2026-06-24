import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getStoriesPage, generateDaily } from "../api.js";
import { useAuth } from "../auth.jsx";

const PAGE = 20;
const RATING_OPTIONS = [
  { label: "All", value: "" },
  { label: "PG", value: "pg" },
  { label: "Mature", value: "mature" },
];

export default function StoriesList() {
  const { user } = useAuth();
  const [stories, setStories] = useState(null);
  const [total, setTotal] = useState(0);
  const [rating, setRating] = useState(""); // "" | "pg" | "mature"
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);

  // admin generate state
  const [generating, setGenerating] = useState(false);
  const [genNote, setGenNote] = useState(null);

  // Refetch from scratch whenever the rating filter changes.
  const reload = useCallback((r) => {
    setStories(null);
    setError(null);
    getStoriesPage({ rating: r || undefined, limit: PAGE, offset: 0 })
      .then(({ items, total }) => {
        setStories(items);
        setTotal(total);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    reload(rating);
  }, [rating, reload]);

  function loadMore() {
    if (loadingMore || !stories) return;
    setLoadingMore(true);
    getStoriesPage({ rating: rating || undefined, limit: PAGE, offset: stories.length })
      .then(({ items, total }) => {
        setStories((prev) => [...prev, ...items]);
        setTotal(total);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoadingMore(false));
  }

  async function handleGenerate() {
    setGenerating(true);
    setGenNote(null);
    try {
      const res = await generateDaily();
      setGenNote(res.count > 0 ? `Added ${res.count} prompts` : "Already generated");
      reload(rating);
    } catch (e) {
      setGenNote(e.message);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <section className="page-narrow">
      <div className="list-head">
        <h1>Stories</h1>
        {user?.is_admin && (
          <div className="admin-gen">
            <button
              type="button"
              className="ai-btn"
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? "Generating…" : "✨ Generate today's prompts"}
            </button>
            {genNote && <span className="muted gen-note">{genNote}</span>}
          </div>
        )}
      </div>

      <div className="seg-control" role="group" aria-label="Filter by rating">
        {RATING_OPTIONS.map((opt) => (
          <button
            key={opt.value || "all"}
            type="button"
            className={"seg-btn" + (rating === opt.value ? " active" : "")}
            onClick={() => setRating(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {error ? (
        <p className="error">Error: {error}</p>
      ) : !stories ? (
        <p className="muted">Loading stories…</p>
      ) : stories.length === 0 ? (
        <p className="muted">No stories yet. Check back tomorrow.</p>
      ) : (
        <>
          <ul className="story-list">
            {stories.map((s) => (
              <li key={s.id} className="story-card">
                <Link to={`/stories/${s.id}`}>
                  <div className="story-card-top">
                    <div className="story-date">{s.publish_date}</div>
                    <div className="badges">
                      {s.genre && <span className="badge genre">{s.genre}</span>}
                      {s.rating && (
                        <span className={"badge rating " + s.rating}>
                          {s.rating === "mature" ? "Mature" : "PG"}
                        </span>
                      )}
                    </div>
                  </div>
                  <h2>{s.title}</h2>
                  <p className="blurb">{s.blurb}</p>
                </Link>
              </li>
            ))}
          </ul>
          {stories.length < total && (
            <div className="load-more-row">
              <button
                type="button"
                className="ghost-btn"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
