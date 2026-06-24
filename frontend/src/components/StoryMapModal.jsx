import { useEffect, useMemo, useRef, useState } from "react";
import { getStoryTree } from "../api.js";
import "./StoryMapModal.css";

const X_GAP = 116; // horizontal spacing between sibling columns
const Y_GAP = 96; // vertical spacing between depth levels
const MARGIN = 60;
const R = 9; // node radius

const MIN_K = 0.2;
const MAX_K = 4;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// Zoom by `factor` while keeping the point (mx,my) — in stage pixel coords —
// anchored under the cursor.
function zoomAt(v, mx, my, factor) {
  if (!v) return v;
  const k = clamp(v.k * factor, MIN_K, MAX_K);
  const ratio = k / v.k;
  return { k, tx: mx - (mx - v.tx) * ratio, ty: my - (my - v.ty) * ratio };
}

// Scale the tree to fit the stage with a little breathing room, then center it.
function computeFit(sw, sh, tw, th) {
  if (!sw || !sh) return { k: 1, tx: 0, ty: 0 };
  const k = clamp(Math.min(sw / tw, sh / th) * 0.95, MIN_K, 1.3);
  return { k, tx: (sw - tw * k) / 2, ty: (sh - th * k) / 2 };
}

// Build a tidy tree: the story is the (always-visited) root; nodes hang off it
// by parent_node_id. Returns the laid-out root plus the canvas size.
function buildLayout(story, nodes) {
  const byId = new Map();
  nodes.forEach((n) => byId.set(n.id, { ...n, children: [], x: 0, depth: 0 }));
  const root = {
    id: null,
    label: story.title,
    content: story.blurb,
    visited: true,
    isRoot: true,
    children: [],
    x: 0,
    depth: 0,
  };
  // attach children
  nodes.forEach((n) => {
    const node = byId.get(n.id);
    const parent = n.parent_node_id == null ? root : byId.get(n.parent_node_id);
    if (parent) parent.children.push(node);
  });
  // popular branches first, stable by id
  const sortKids = (node) => {
    node.children.sort((a, b) => b.score - a.score || a.id - b.id);
    node.children.forEach(sortKids);
  };
  sortKids(root);

  // assign x (leaves get sequential columns, parents center over children)
  let nextX = 0;
  let maxDepth = 0;
  const place = (node, depth) => {
    node.depth = depth;
    maxDepth = Math.max(maxDepth, depth);
    if (node.children.length === 0) {
      node.x = nextX++;
    } else {
      node.children.forEach((c) => place(c, depth + 1));
      node.x =
        (node.children[0].x + node.children[node.children.length - 1].x) / 2;
    }
  };
  place(root, 0);

  const width = Math.max(nextX, 1) * X_GAP + MARGIN * 2;
  const height = (maxDepth + 1) * Y_GAP + MARGIN * 2;
  return { root, width, height };
}

function flatten(root) {
  const nodes = [];
  const edges = [];
  const walk = (n) => {
    nodes.push(n);
    n.children.forEach((c) => {
      edges.push([n, c]);
      walk(c);
    });
  };
  walk(root);
  return { nodes, edges };
}

const px = (n) => n.x * X_GAP + MARGIN;
const py = (n) => n.depth * Y_GAP + MARGIN;

function truncate(s, max = 22) {
  if (!s) return "";
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

export default function StoryMapModal({
  storyId,
  onClose,
  onNavigate,
  currentNodeId = null,
  pathIds = [],
}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [hover, setHover] = useState(null); // { node, left, top }
  const [view, setView] = useState(null); // { k, tx, ty } pan/zoom transform

  const stageRef = useRef(null);
  const svgRef = useRef(null);
  const viewRef = useRef(null); // latest view, for event handlers
  const pointers = useRef(new Map()); // active pointerId -> {x, y}
  const gesture = useRef(null); // current pan/pinch gesture
  const moved = useRef(false); // did this gesture drag? (suppresses tap)
  const sizeRef = useRef({ w: 0, h: 0 });

  useEffect(() => {
    viewRef.current = view;
  }, [view]);

  useEffect(() => {
    let cancelled = false;
    getStoryTree(storyId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [storyId]);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const layout = useMemo(
    () => (data ? buildLayout(data.story, data.nodes) : null),
    [data]
  );

  // Auto-fit on open, and refit when the stage actually changes size
  // (e.g. orientation change), but not when panning/zooming.
  useEffect(() => {
    if (!layout) return;
    const stage = stageRef.current;
    if (!stage) return;
    const fit = () => {
      const r = stage.getBoundingClientRect();
      if (!r.width || !r.height) return;
      sizeRef.current = { w: r.width, h: r.height };
      setView(computeFit(r.width, r.height, layout.width, layout.height));
    };
    fit();
    const ro = new ResizeObserver(() => {
      const r = stage.getBoundingClientRect();
      if (r.width !== sizeRef.current.w || r.height !== sizeRef.current.h) {
        sizeRef.current = { w: r.width, h: r.height };
        setView(computeFit(r.width, r.height, layout.width, layout.height));
      }
    });
    ro.observe(stage);
    return () => ro.disconnect();
  }, [layout]);

  // Wheel zoom — needs a non-passive listener so we can preventDefault.
  useEffect(() => {
    if (!layout) return;
    const stage = stageRef.current;
    if (!stage) return;
    const onWheel = (e) => {
      e.preventDefault();
      const r = stage.getBoundingClientRect();
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      setView((v) => zoomAt(v, e.clientX - r.left, e.clientY - r.top, factor));
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [layout]);

  function onPointerDown(e) {
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    setHover(null);
    if (pointers.current.size === 2) {
      const pts = [...pointers.current.values()];
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      gesture.current = {
        mode: "pinch",
        startDist: dist,
        startView: viewRef.current,
        rect: stageRef.current.getBoundingClientRect(),
      };
      moved.current = true; // a pinch is never a tap
      try {
        svgRef.current.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    } else {
      gesture.current = {
        mode: "pan",
        dragging: false,
        lastX: e.clientX,
        lastY: e.clientY,
        startX: e.clientX,
        startY: e.clientY,
      };
      moved.current = false;
    }
  }

  function onPointerMove(e) {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const g = gesture.current;
    if (!g) return;

    if (g.mode === "pinch" && pointers.current.size >= 2) {
      const pts = [...pointers.current.values()];
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      const midX = (pts[0].x + pts[1].x) / 2 - g.rect.left;
      const midY = (pts[0].y + pts[1].y) / 2 - g.rect.top;
      const sv = g.startView;
      if (!sv) return;
      const k = clamp(sv.k * (dist / g.startDist), MIN_K, MAX_K);
      const ratio = k / sv.k;
      setView({
        k,
        tx: midX - (midX - sv.tx) * ratio,
        ty: midY - (midY - sv.ty) * ratio,
      });
    } else if (g.mode === "pan") {
      if (!g.dragging) {
        if (Math.hypot(e.clientX - g.startX, e.clientY - g.startY) <= 4) return;
        g.dragging = true;
        moved.current = true;
        try {
          svgRef.current.setPointerCapture(e.pointerId);
        } catch {
          /* ignore */
        }
      }
      const dx = e.clientX - g.lastX;
      const dy = e.clientY - g.lastY;
      g.lastX = e.clientX;
      g.lastY = e.clientY;
      setView((v) => (v ? { ...v, tx: v.tx + dx, ty: v.ty + dy } : v));
    }
  }

  function endPointer(e) {
    pointers.current.delete(e.pointerId);
    try {
      svgRef.current.releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
    if (pointers.current.size === 1) {
      // pinch released to one finger → resume panning from it without a jump
      const p = [...pointers.current.values()][0];
      gesture.current = {
        mode: "pan",
        dragging: true,
        lastX: p.x,
        lastY: p.y,
        startX: p.x,
        startY: p.y,
      };
    } else if (pointers.current.size === 0) {
      gesture.current = null;
    }
  }

  function go(node) {
    if (moved.current) return; // the gesture was a drag, not a tap
    if (!node.visited) return; // shadows aren't clickable
    onNavigate(node.isRoot ? null : node.id);
  }

  function showTip(node, evt) {
    if (gesture.current && gesture.current.dragging) return; // not while panning
    const stage = stageRef.current;
    if (!stage) return;
    const rect = stage.getBoundingClientRect();
    setHover({ node, left: evt.clientX - rect.left, top: evt.clientY - rect.top });
  }

  function zoomButton(factor) {
    const r = stageRef.current.getBoundingClientRect();
    setView((v) => zoomAt(v, r.width / 2, r.height / 2, factor));
  }

  function fitButton() {
    const r = stageRef.current.getBoundingClientRect();
    setView(computeFit(r.width, r.height, layout.width, layout.height));
  }

  let body;
  if (error) {
    body = <p className="error">Error: {error}</p>;
  } else if (!layout) {
    body = <p className="muted">Loading map…</p>;
  } else {
    const { root, width, height } = layout;
    const { nodes, edges } = flatten(root);
    const visitedCount = nodes.filter((n) => n.visited && !n.isRoot).length;
    const total = nodes.length - 1; // exclude root
    const v = view || { k: 1, tx: 0, ty: 0 };

    // The reader's trail (root → current). The root is always on-path.
    const trail = new Set(pathIds);
    const isOnPath = (n) => n.isRoot || trail.has(n.id);
    // "You are here": the current node, or the root when currentNodeId is null.
    const isCurrent = (n) =>
      currentNodeId == null ? n.isRoot : n.id === currentNodeId;

    body = (
      <>
        <p className="muted map-legend">
          The shadow tree — <span className="lg-visited">●</span> nodes you've
          visited are lit and clickable;{" "}
          <span className="lg-shadow">●</span> shadows are paths still unknown.
          The <span className="lg-current">◉</span> ring marks where you are now.
          You've explored <strong>{visitedCount}</strong> of {total}.{" "}
          <span className="map-hint">Drag to move · scroll / pinch to zoom.</span>
        </p>

        <div className="map-stage" ref={stageRef}>
          <svg
            ref={svgRef}
            className="map-svg"
            width="100%"
            height="100%"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endPointer}
            onPointerCancel={endPointer}
          >
            <g transform={`translate(${v.tx} ${v.ty}) scale(${v.k})`}>
              {/* edges */}
              {edges.map(([a, b]) => {
                // An edge is on the trail only when both endpoints are.
                const onTrail = isOnPath(a) && isOnPath(b);
                return (
                  <line
                    key={`${a.id ?? "root"}-${b.id}`}
                    x1={px(a)}
                    y1={py(a)}
                    x2={px(b)}
                    y2={py(b)}
                    className={
                      "map-edge" +
                      (a.visited && b.visited ? " lit" : "") +
                      (onTrail ? " trail" : "")
                    }
                  />
                );
              })}
              {/* nodes */}
              {nodes.map((n) => {
                const current = isCurrent(n);
                const cls =
                  "map-node" +
                  (n.isRoot ? " root" : "") +
                  (n.visited ? " visited" : " shadow") +
                  (isOnPath(n) ? " trail" : "") +
                  (current ? " current" : "");
                return (
                  <g
                    key={n.id ?? "root"}
                    transform={`translate(${px(n)}, ${py(n)})`}
                    className={cls}
                    onClick={() => go(n)}
                    onMouseEnter={(e) => showTip(n, e)}
                    onMouseMove={(e) => showTip(n, e)}
                    onMouseLeave={() => setHover(null)}
                  >
                    {current && <circle className="map-node-ring" r={R + 6} />}
                    <circle r={n.isRoot ? R + 3 : R} />
                    {n.visited && (
                      <text className="map-label" y={R + 16}>
                        {truncate(
                          n.isRoot ? n.label : n.edge_prompt || "(untitled)"
                        )}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>

          <div className="map-controls">
            <button
              type="button"
              onClick={() => zoomButton(1.2)}
              aria-label="Zoom in"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => zoomButton(1 / 1.2)}
              aria-label="Zoom out"
            >
              −
            </button>
            <button type="button" onClick={fitButton} aria-label="Fit to view">
              ⤢
            </button>
          </div>

          {hover && <NodeTooltip {...hover} />}
        </div>
      </>
    );
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal map-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Story map"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h2>{data ? `🗺 ${data.story.title}` : "🗺 Story map"}</h2>
          <button
            type="button"
            className="modal-close"
            aria-label="Close"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        {body}
      </div>
    </div>
  );
}

function NodeTooltip({ node, left, top }) {
  const title = node.isRoot
    ? node.label
    : node.edge_prompt || (node.visited ? "(untitled)" : "Unexplored path");

  return (
    <div className="map-tip" style={{ left, top }} aria-hidden="true">
      <div className="map-tip-title">
        {node.visited ? title : "Unexplored path"}
      </div>
      {node.visited && !node.isRoot && node.author && (
        <div className="map-tip-author">by @{node.author}</div>
      )}
      {node.visited && node.content && (
        <p className="map-tip-body">{truncate(node.content, 140)}</p>
      )}
      <div className="map-tip-meta">
        <span title="Net votes">▲ {node.score}</span>
        <span title="Distinct viewers">👁 {node.view_count}</span>
        <span title="Continuations">
          ⌥ {node.children.length} cont
          {node.children.length === 1 ? "" : "s"}
        </span>
      </div>
      {node.visited ? (
        <div className="map-tip-foot">Click to jump here</div>
      ) : (
        <div className="map-tip-foot muted">Visit its parent to reveal it</div>
      )}
    </div>
  );
}
