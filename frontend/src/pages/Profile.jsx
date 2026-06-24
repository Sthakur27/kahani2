import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { getMyViews, getMyVotes, getMyNodes } from "../api.js";
import "./Profile.css";

const TABS = ["Read", "Votes", "Wrote"];

const LOADERS = {
  Read: getMyViews,
  Votes: getMyVotes,
  Wrote: getMyNodes,
};

const EMPTY = {
  Read: "You haven't read any branches yet.",
  Votes: "You haven't voted on any branches yet.",
  Wrote: "You haven't written any branches yet.",
};

function snippet(text, max = 140) {
  if (!text) return "";
  const t = text.trim();
  return t.length > max ? t.slice(0, max).trimEnd() + "…" : t;
}

function shortDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString();
}

function Meta({ tab, item }) {
  if (tab === "Read") {
    return (
      <span className="profile-meta muted">
        ▲ {item.score} · 👁 {item.view_count} · viewed {shortDate(item.viewed_at)}
      </span>
    );
  }
  if (tab === "Votes") {
    const up = item.value === 1;
    return (
      <span className="profile-meta muted">
        <span className={up ? "vote-up" : "vote-down"}>
          {up ? "▲ upvoted" : "▼ downvoted"}
        </span>{" "}
        · ▲ {item.score} · 👁 {item.view_count} · voted {shortDate(item.voted_at)}
      </span>
    );
  }
  // Wrote
  return (
    <span className="profile-meta muted">
      ▲ {item.score} · 👁 {item.view_count} · {item.child_count} continuation
      {item.child_count === 1 ? "" : "s"} · written {shortDate(item.created_at)}
    </span>
  );
}

function Row({ tab, item }) {
  return (
    <li className="profile-row">
      <Link
        to={`/stories/${item.story_id}/nodes/${item.node_id}`}
        className="profile-link"
      >
        <span className="profile-story muted">{item.story_title}</span>
        {item.edge_prompt ? (
          <span className="profile-prompt">“{item.edge_prompt}”</span>
        ) : (
          item.content && (
            <span className="profile-prompt">{snippet(item.content, 80)}</span>
          )
        )}
        {item.content && (
          <span className="profile-snippet">{snippet(item.content)}</span>
        )}
        <Meta tab={tab} item={item} />
      </Link>
    </li>
  );
}

export default function Profile() {
  const { user } = useAuth();
  const [tab, setTab] = useState("Read");
  // Per-tab cache: { Read: { items, error }, ... }
  const [data, setData] = useState({});

  useEffect(() => {
    if (!user) return;
    if (data[tab]) return; // already loaded (or attempted)
    let alive = true;
    LOADERS[tab]()
      .then((items) => {
        if (alive) setData((d) => ({ ...d, [tab]: { items, error: null } }));
      })
      .catch((err) => {
        if (alive)
          setData((d) => ({
            ...d,
            [tab]: { items: null, error: err.message || "Failed to load" },
          }));
      });
    return () => {
      alive = false;
    };
  }, [user, tab, data]);

  if (!user) {
    return (
      <div className="profile">
        <h1 className="profile-title">👤 Your history</h1>
        <p className="profile-sub muted">
          <Link to="/login" className="link-like">
            Log in
          </Link>{" "}
          to see the branches you've read, voted on, and written.
        </p>
      </div>
    );
  }

  const current = data[tab];

  return (
    <div className="profile">
      <h1 className="profile-title">👤 {user.username}</h1>
      <p className="profile-sub muted">
        Everything you've read, voted on, and written.
      </p>

      <div className="profile-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={t === tab}
            className={"profile-tab" + (t === tab ? " is-active" : "")}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {current?.error && <p className="error">{current.error}</p>}
      {!current && <p className="muted">Loading…</p>}
      {current && !current.error && current.items?.length === 0 && (
        <p className="muted">{EMPTY[tab]}</p>
      )}
      {current && !current.error && current.items?.length > 0 && (
        <ul className="profile-list">
          {current.items.map((it) => (
            <Row key={it.node_id} tab={tab} item={it} />
          ))}
        </ul>
      )}
    </div>
  );
}
