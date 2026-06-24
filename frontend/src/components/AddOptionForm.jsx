import { useState } from "react";
import { createNode, draftNode } from "../api.js";
import MicButton from "./MicButton.jsx";

// Append dictated speech to existing text, inserting a space at the seam so
// words don't run together. Used as the onTranscript handler for each mic.
function appendTranscript(prev, fresh) {
  const piece = fresh.trim();
  if (!piece) return prev;
  if (!prev) return piece;
  return /\s$/.test(prev) ? prev + piece : `${prev} ${piece}`;
}

// In-page form that replaces the options list. Two sections — "story path"
// (the edge prompt) and "blurb" (the node content) — plus a describe-to-AI
// box that polishes a few bullets into both fields.
export default function AddOptionForm({ storyId, parentNodeId, onCancel, onCreated }) {
  const [edgePrompt, setEdgePrompt] = useState("");
  const [content, setContent] = useState("");
  const [bullets, setBullets] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [aiNote, setAiNote] = useState(null);

  async function handleDraft() {
    setError(null);
    setAiNote(null);
    if (!bullets.trim()) {
      setAiNote("Add a few notes for the AI to work from.");
      return;
    }
    setDrafting(true);
    try {
      const draft = await draftNode({
        story_id: storyId,
        parent_node_id: parentNodeId,
        bullets,
      });
      setEdgePrompt(draft.edge_prompt || "");
      setContent(draft.content || "");
    } catch (e) {
      setAiNote(e.message);
    } finally {
      setDrafting(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (!content.trim()) {
      setError("Write the passage before adding.");
      return;
    }
    setSubmitting(true);
    try {
      const node = await createNode(storyId, {
        parent_node_id: parentNodeId,
        edge_prompt: edgePrompt.trim() || null,
        content: content.trim(),
      });
      onCreated(node);
    } catch (e) {
      setError(e.message);
      setSubmitting(false);
    }
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <div className="ai-box">
        <label className="field-label">
          Describe it to AI <span className="muted">— optional</span>
        </label>
        <div className="field-with-mic">
          <textarea
            className="field"
            rows={3}
            value={bullets}
            onChange={(e) => setBullets(e.target.value)}
            placeholder={"A few quick notes…\n- they pry open the hatch\n- something below is breathing"}
          />
          <MicButton
            label="notes"
            onTranscript={(fresh) =>
              setBullets((prev) => appendTranscript(prev, fresh))
            }
          />
        </div>
        <button
          type="button"
          className="ai-btn"
          onClick={handleDraft}
          disabled={drafting}
        >
          {drafting ? "Drafting…" : "✨ Draft with AI"}
        </button>
        {aiNote && <p className="muted ai-note">{aiNote}</p>}
      </div>

      <label className="field-label">
        Story path <span className="muted">— the choice that leads here</span>
      </label>
      <div className="field-with-mic">
        <input
          className="field"
          type="text"
          value={edgePrompt}
          onChange={(e) => setEdgePrompt(e.target.value)}
          placeholder="e.g. Pry open the humming hatch"
        />
        <MicButton
          label="story path"
          onTranscript={(fresh) =>
            setEdgePrompt((prev) => appendTranscript(prev, fresh))
          }
        />
      </div>

      <label className="field-label">
        Blurb <span className="muted">— the passage</span>
      </label>
      <div className="field-with-mic">
        <textarea
          className="field"
          rows={6}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Write what happens next…"
        />
        <MicButton
          label="blurb"
          onTranscript={(fresh) =>
            setContent((prev) => appendTranscript(prev, fresh))
          }
        />
      </div>

      {error && <p className="error">{error}</p>}

      <div className="form-actions">
        <button type="submit" className="primary-btn" disabled={submitting}>
          {submitting ? "Adding…" : "Add option"}
        </button>
        <button type="button" className="ghost-btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
