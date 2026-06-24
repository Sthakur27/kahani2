import { useState } from "react";
import { voteNode } from "../api.js";

// Thumbs up / down for the node you're currently viewing. `myVote` is 1, -1, or
// null (from the server). Clicking the already-active thumb again clears it.
export default function VoteButtons({ nodeId, score, myVote, onChange }) {
  const [busy, setBusy] = useState(false);

  async function cast(value) {
    if (busy) return;
    setBusy(true);
    const next = myVote === value ? 0 : value; // toggle off if re-clicking
    try {
      const node = await voteNode(nodeId, next);
      onChange({ score: node.score, myVote: node.my_vote });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="vote-bar">
      <button
        type="button"
        className={"vote-btn up" + (myVote === 1 ? " active" : "")}
        onClick={() => cast(1)}
        disabled={busy}
        aria-pressed={myVote === 1}
        aria-label="Thumbs up"
        title="Thumbs up"
      >
        👍
      </button>
      <span className="vote-score">{score}</span>
      <button
        type="button"
        className={"vote-btn down" + (myVote === -1 ? " active" : "")}
        onClick={() => cast(-1)}
        disabled={busy}
        aria-pressed={myVote === -1}
        aria-label="Thumbs down"
        title="Thumbs down"
      >
        👎
      </button>
    </div>
  );
}
