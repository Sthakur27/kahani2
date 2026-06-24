import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useNavigate, useLocation } from "react-router-dom";
import { getStory, getNodesPage, getNode, getNodePath, draftNode, createNode } from "../api.js";
import HistoryNav from "../components/HistoryNav.jsx";
import SummaryPanel from "../components/SummaryPanel.jsx";
import AddOptionForm from "../components/AddOptionForm.jsx";
import VoteButtons from "../components/VoteButtons.jsx";
import StoryMapModal from "../components/StoryMapModal.jsx";
import { useAuth } from "../auth.jsx";

const PAGE = 15;

// Render an edge effect as a short chip in campaign "build" mode. Returns
// { label, tone } or null for silent effects (flags).
function effectChip(e) {
  if (e.type === "hp_delta")
    return { label: `${e.amount > 0 ? "+" : ""}${e.amount} HP`, tone: e.amount < 0 ? "bad" : "good" };
  if (e.type === "max_hp_delta")
    return { label: `${e.amount > 0 ? "+" : ""}${e.amount} max HP`, tone: "good" };
  if (e.type === "heal_full") return { label: "Fully healed", tone: "good" };
  if (e.type === "stat_delta")
    return { label: `${e.amount > 0 ? "+" : ""}${e.amount} ${e.stat?.toUpperCase()}`, tone: "good" };
  if (e.type === "grant_item") return { label: "Item", tone: "good" };
  if (e.type === "consume_item") return { label: "Uses an item", tone: "" };
  if (e.type === "end_run") return { label: "Ends the story", tone: "" };
  return null; // set_flag etc. — silent
}

// The mechanics row shown on a choice in campaign mode: destination kind +
// the effects taking it applies (+ a check tag once roll edges land).
function ChoiceMechanics({ node }) {
  const edge = node.edge || {};
  const chips = (edge.effects || []).map(effectChip).filter(Boolean);
  const showKind = node.kind && node.kind !== "story";
  const roll = edge.kind === "roll" && edge.check_stat;
  if (!showKind && !chips.length && !roll) return null;
  return (
    <div className="choice-mechanics">
      {roll && (
        <span className="check-tag">
          {edge.check_stat.toUpperCase()} {edge.check_dc}
        </span>
      )}
      {showKind && <span className={"node-kind kind-" + node.kind}>{node.kind}</span>}
      {chips.map((c, i) => (
        <span key={i} className={"fx" + (c.tone ? " fx-" + c.tone : "")}>
          {c.label}
        </span>
      ))}
    </div>
  );
}

const BAND_ORDER = ["crit_success", "success", "fail", "crit_fail"];
const BAND_LABEL = {
  crit_success: "Crit success",
  success: "Success",
  fail: "Fail",
  crit_fail: "Crit fail",
};

// Group choices by their inbound edge so a roll edge (which has several outcome
// nodes) shows as ONE choice, while plain edges stay one node each.
function groupByEdge(items) {
  const groups = [];
  const byEdge = new Map();
  for (const n of items) {
    const key = n.edge?.edge_id ?? `n${n.id}`;
    let g = byEdge.get(key);
    if (!g) {
      g = { key, edge: n.edge || {}, items: [] };
      byEdge.set(key, g);
      groups.push(g);
    }
    g.items.push(n);
  }
  return groups;
}

function BranchCard({ n, campaign, onEnter }) {
  return (
    <li className="node-card clickable" onClick={() => onEnter(n)}>
      {n.edge_prompt && <div className="edge-prompt">“{n.edge_prompt}”</div>}
      {campaign && <ChoiceMechanics node={n} />}
      <p>{n.content}</p>
      <div className="node-meta">
        <span className="score">▲ {n.score}</span>
        <span className="muted">👁 {n.view_count}</span>
        <span className="muted">
          {n.child_count} continuation{n.child_count === 1 ? "" : "s"}
        </span>
        {n.author && <span className="byline">by @{n.author}</span>}
      </div>
    </li>
  );
}

// A roll edge in build mode: the check + each authored outcome band leading to
// its passage (clickable to explore that result).
function RollChoiceCard({ group, onEnter }) {
  const edge = group.edge || {};
  const label = group.items[0]?.edge_prompt || "Skill check";
  const items = [...group.items].sort(
    (a, b) => BAND_ORDER.indexOf(a.edge?.band) - BAND_ORDER.indexOf(b.edge?.band)
  );
  return (
    <li className="node-card roll-card">
      <div className="edge-prompt">“{label}”</div>
      <div className="choice-mechanics">
        {edge.check_stat && (
          <span className="check-tag">
            {edge.check_stat.toUpperCase()} {edge.check_dc}
          </span>
        )}
        <span className="muted">🎲 roll · {items.length} outcomes</span>
      </div>
      <ul className="roll-outcomes">
        {items.map((n) => (
          <li
            key={n.id}
            className="roll-outcome clickable"
            onClick={() => onEnter(n)}
          >
            <span className={"band-tag band-" + n.edge?.band}>
              {BAND_LABEL[n.edge?.band] || n.edge?.band}
            </span>
            {(n.edge?.effects || [])
              .map(effectChip)
              .filter(Boolean)
              .map((c, i) => (
                <span key={i} className={"fx" + (c.tone ? " fx-" + c.tone : "")}>
                  {c.label}
                </span>
              ))}
            <span className="roll-snippet">
              {n.content.slice(0, 90)}
              {n.content.length > 90 ? "…" : ""}
            </span>
          </li>
        ))}
      </ul>
    </li>
  );
}

export default function StoryView() {
  const { id, nodeId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [story, setStory] = useState(null);
  const [path, setPath] = useState([]); // nodes from root → current position
  // Paginated options at the current position.
  const [branches, setBranches] = useState({ items: [], total: 0, offset: 0 });
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [adding, setAdding] = useState(false);
  const [nodeVote, setNodeVote] = useState(null); // {score, myVote} for the current node
  const [mapOpen, setMapOpen] = useState(false);
  const [error, setError] = useState(null);
  const [continuing, setContinuing] = useState(false);
  const [continueNote, setContinueNote] = useState(null);

  const current = path.length ? path[path.length - 1] : null;
  const currentId = current ? current.id : null;

  // Load the first page of options for a given parent (resets paging).
  const loadBranches = useCallback(
    (parentId) => {
      setLoadingBranches(true);
      getNodesPage(id, parentId, { limit: PAGE, offset: 0 })
        .then(({ items, total }) =>
          setBranches({ items, total, offset: items.length })
        )
        .catch((e) => setError(e.message))
        .finally(() => setLoadingBranches(false));
    },
    [id]
  );

  const loadMoreBranches = useCallback(
    (parentId) => {
      setLoadingMore(true);
      setBranches((prev) => {
        getNodesPage(id, parentId, { limit: PAGE, offset: prev.offset })
          .then(({ items, total }) =>
            setBranches((p) => ({
              items: [...p.items, ...items],
              total,
              offset: p.offset + items.length,
            }))
          )
          .catch((e) => setError(e.message))
          .finally(() => setLoadingMore(false));
        return prev;
      });
    },
    [id]
  );

  useEffect(() => {
    getStory(id).then(setStory).catch((e) => setError(e.message));
  }, [id]);

  // The URL is the source of truth for where you are in the tree. Rebuild the
  // path (and load the right branches) from :nodeId, so a refresh stays put.
  useEffect(() => {
    setAdding(false);
    setError(null);
    if (nodeId) {
      getNodePath(nodeId)
        .then((nodes) => setPath(nodes))
        .catch((e) => setError(e.message));
      loadBranches(Number(nodeId));
    } else {
      setPath([]);
      loadBranches(undefined); // top-level nodes
    }
  }, [id, nodeId, loadBranches]);

  // On every node page, fetch this user's existing vote (+ fresh score) so the
  // thumbs reflect whether they've already voted.
  useEffect(() => {
    if (currentId == null) {
      setNodeVote(null);
      return;
    }
    let cancelled = false;
    // optimistic until fetch
    setNodeVote({ score: current.score ?? 0, myVote: null, views: current.view_count ?? 0 });
    getNode(currentId)
      .then((d) => {
        if (!cancelled)
          setNodeVote({ score: d.score, myVote: d.my_vote, views: d.view_count });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [currentId]); // eslint-disable-line react-hooks/exhaustive-deps

  function enterBranch(node) {
    navigate(`/stories/${id}/nodes/${node.id}`);
  }

  async function handleAiContinue() {
    setContinueNote(null);
    setContinuing(true);
    const parentNodeId = current ? current.id : null;
    try {
      const draft = await draftNode({
        story_id: story.id,
        parent_node_id: parentNodeId,
        bullets:
          "Continue the story from here in a fresh, surprising but fitting direction. Invent the next beat — a vivid 2-4 sentence passage and a short choice label for it.",
      });
      const node = await createNode(story.id, {
        parent_node_id: parentNodeId,
        edge_prompt: draft.edge_prompt || null,
        content: draft.content,
      });
      enterBranch(node);
    } catch (e) {
      setContinueNote(e.message);
    } finally {
      setContinuing(false);
    }
  }

  function jumpTo(index) {
    // index === -1 → story root; otherwise the node at that path index
    if (index < 0) navigate(`/stories/${id}`);
    else navigate(`/stories/${id}/nodes/${path[index].id}`);
  }

  if (error) return <p className="error">Error: {error}</p>;
  if (!story) return <p className="muted">Loading…</p>;

  const parentId = current ? current.id : undefined;

  return (
    <div className="story-layout">
      <aside className="sidebar">
        <HistoryNav story={story} path={path} onJump={jumpTo} />
        <SummaryPanel summary={current?.summary_so_far} />
      </aside>

      <section className="story-main">
        <div className="story-topbar">
          <Link to="/" className="back">
            ← all stories
          </Link>
          <button
            type="button"
            className="map-icon-btn"
            onClick={() => setMapOpen(true)}
            title="Story map"
            aria-label="Open story map"
          >
            🗺
          </button>
        </div>
        {story.mode === "campaign" && (
          <div className="campaign-bar">
            <span className="campaign-hint">
              🛠 <strong>Build &amp; explore</strong> — jump anywhere via the 🗺 map,
              see each choice's mechanics, and add branches. Or play it for real:
            </span>
            <Link to={`/stories/${id}/play`} className="play-cta">
              ⚔ Play a run
            </Link>
          </div>
        )}
        <div className="story-date">{story.publish_date}</div>
        <div className="story-head">
          <h1>{story.title}</h1>
          {current && nodeVote && (
            <div className="head-meta">
              {user ? (
                <VoteButtons
                  nodeId={current.id}
                  score={nodeVote.score}
                  myVote={nodeVote.myVote}
                  onChange={(v) => setNodeVote((p) => ({ ...p, ...v }))}
                />
              ) : (
                <span className="vote-bar vote-bar--locked" title="Log in to vote">
                  <span className="vote-locked">▲ {nodeVote.score}</span>
                  <Link to="/login" state={{ from: location.pathname }} className="login-hint">
                    Log in to vote
                  </Link>
                </span>
              )}
              <span className="views" title="People who've viewed this node">
                👁 {nodeVote.views}
              </span>
              {current.author && (
                <span className="byline">by @{current.author}</span>
              )}
            </div>
          )}
        </div>

        {current ? (
          <>
            {current.edge_prompt && (
              <p className="edge-prompt lead">“{current.edge_prompt}”</p>
            )}
            <p className="blurb lead">{current.content}</p>
          </>
        ) : (
          <p className="blurb lead">{story.blurb}</p>
        )}

        <h3 className="branches-title">
          {current ? "Where to next" : "Opening branches"}
        </h3>
        {adding ? (
          <AddOptionForm
            storyId={story.id}
            parentNodeId={current ? current.id : null}
            onCancel={() => setAdding(false)}
            onCreated={() => {
              setAdding(false);
              loadBranches(parentId);
            }}
          />
        ) : (
          <>
            {loadingBranches ? (
              <p className="muted">Loading…</p>
            ) : branches.items.length === 0 ? (
              <p className="muted">
                No continuations yet — be the first to continue the story.
              </p>
            ) : (
              <ul className="node-list">
                {groupByEdge(branches.items).map((g) =>
                  story.mode === "campaign" && g.edge?.kind === "roll" ? (
                    <RollChoiceCard
                      key={`e${g.key}`}
                      group={g}
                      onEnter={enterBranch}
                    />
                  ) : (
                    g.items.map((n) => (
                      <BranchCard
                        key={n.id}
                        n={n}
                        campaign={story.mode === "campaign"}
                        onEnter={enterBranch}
                      />
                    ))
                  )
                )}
              </ul>
            )}
            {!loadingBranches && branches.items.length < branches.total && (
              <div className="load-more-row">
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={() => loadMoreBranches(parentId)}
                  disabled={loadingMore}
                >
                  {loadingMore ? "Loading…" : "Load more"}
                </button>
              </div>
            )}
            {user ? (
              <>
                <div
                  style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}
                >
                  <button
                    type="button"
                    className="add-option-btn"
                    onClick={() => setAdding(true)}
                  >
                    + Add an option
                  </button>
                  <button
                    type="button"
                    className="add-option-btn ai-btn"
                    onClick={handleAiContinue}
                    disabled={continuing}
                  >
                    {continuing ? "✨ Continuing…" : "✨ Let AI continue"}
                  </button>
                </div>
                {continueNote && (
                  <p className="muted ai-note">{continueNote}</p>
                )}
              </>
            ) : (
              <Link
                to="/login"
                state={{ from: location.pathname }}
                className="add-option-btn add-option-btn--locked"
              >
                Log in to add an option
              </Link>
            )}
          </>
        )}
      </section>

      {mapOpen && (
        <StoryMapModal
          storyId={id}
          currentNodeId={currentId}
          pathIds={path.map((n) => n.id)}
          onClose={() => setMapOpen(false)}
          onNavigate={(nodeId) => {
            setMapOpen(false);
            navigate(nodeId == null ? `/stories/${id}` : `/stories/${id}/nodes/${nodeId}`);
          }}
        />
      )}
    </div>
  );
}
