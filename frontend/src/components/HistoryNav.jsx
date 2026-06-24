// Vertical "path so far" timeline: connected dots, one per node, labeled with
// the edge prompt that led there. The story itself is the root dot. Clicking a
// dot jumps back to that point in the path.
export default function HistoryNav({ story, path, onJump }) {
  const items = [
    { key: "root", label: story.title, isRoot: true },
    ...path.map((n) => ({ key: n.id, label: n.edge_prompt || "(untitled branch)" })),
  ];
  const activeIndex = items.length - 1;

  return (
    <nav className="history-nav">
      <h4 className="sidebar-title">Your path</h4>
      <ul className="timeline">
        {items.map((item, i) => (
          <li
            key={item.key}
            className={
              "timeline-item" +
              (i === activeIndex ? " active" : "") +
              (item.isRoot ? " root" : "")
            }
            onClick={() => onJump(i - 1)}
          >
            <span className="timeline-dot" />
            <span className="timeline-label">{item.label}</span>
          </li>
        ))}
      </ul>
    </nav>
  );
}
