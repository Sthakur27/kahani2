import { useState } from "react";
import { draftRoll, createRollEdge } from "../api.js";

const STATS = ["str", "dex", "con", "int", "wis", "cha"];
const BANDS = [
  { key: "success", label: "Success", req: true },
  { key: "fail", label: "Fail", req: true },
  { key: "crit_success", label: "Critical success", req: false },
  { key: "crit_fail", label: "Critical fail", req: false },
];

const EMPTY = {
  success: { content: "", hp: 0 },
  fail: { content: "", hp: 0 },
  crit_success: { content: "", hp: 0 },
  crit_fail: { content: "", hp: 0 },
};

// Author a roll (skill-check) edge: describe the action, let AI draft the check
// + outcome passages, edit, then create. (Build mode, campaign stories.)
export default function RollForm({ storyId, parentNodeId, onCancel, onCreated }) {
  const [idea, setIdea] = useState("");
  const [label, setLabel] = useState("");
  const [stat, setStat] = useState("dex");
  const [dc, setDc] = useState(12);
  const [outcomes, setOutcomes] = useState(EMPTY);
  const [drafting, setDrafting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [aiNote, setAiNote] = useState(null);

  const setBand = (key, patch) =>
    setOutcomes((o) => ({ ...o, [key]: { ...o[key], ...patch } }));

  async function handleDraft() {
    setError(null);
    setAiNote(null);
    if (!idea.trim()) {
      setAiNote("Describe the action to check.");
      return;
    }
    setDrafting(true);
    try {
      const p = await draftRoll({
        story_id: storyId,
        parent_node_id: parentNodeId,
        idea,
      });
      setLabel(p.label || "");
      setStat(p.check_stat || "dex");
      setDc(p.check_dc || 12);
      setOutcomes(() => {
        const next = { ...EMPTY };
        for (const b of BANDS) {
          const od = p.outcomes?.[b.key];
          next[b.key] = od ? { content: od.content || "", hp: od.hp || 0 } : { content: "", hp: 0 };
        }
        return next;
      });
    } catch (e) {
      setAiNote(e.message);
    } finally {
      setDrafting(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (!label.trim()) {
      setError("Give the action a label.");
      return;
    }
    if (!outcomes.success.content.trim() || !outcomes.fail.content.trim()) {
      setError("Both a success and a fail passage are required.");
      return;
    }
    const outs = {};
    for (const b of BANDS) {
      const c = outcomes[b.key].content.trim();
      if (c) outs[b.key] = { content: c, hp: Number(outcomes[b.key].hp) || 0 };
    }
    setSubmitting(true);
    try {
      await createRollEdge(storyId, {
        parent_node_id: parentNodeId,
        label: label.trim(),
        check_stat: stat,
        check_dc: Number(dc),
        outcomes: outs,
      });
      onCreated();
    } catch (e) {
      setError(e.message);
      setSubmitting(false);
    }
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <div className="ai-box">
        <label className="field-label">
          Describe the risky action <span className="muted">— AI drafts the check</span>
        </label>
        <textarea
          className="field"
          rows={2}
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="e.g. leap across the collapsing bridge before it falls"
        />
        <button type="button" className="ai-btn" onClick={handleDraft} disabled={drafting}>
          {drafting ? "Drafting…" : "✨ Draft skill check"}
        </button>
        {aiNote && <p className="muted ai-note">{aiNote}</p>}
      </div>

      <label className="field-label">Action label</label>
      <input
        className="field"
        type="text"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Leap the chasm"
      />

      <div className="roll-check-row">
        <label className="field-label">
          Check
          <select className="field" value={stat} onChange={(e) => setStat(e.target.value)}>
            {STATS.map((s) => (
              <option key={s} value={s}>{s.toUpperCase()}</option>
            ))}
          </select>
        </label>
        <label className="field-label">
          DC
          <input
            className="field"
            type="number"
            min={1}
            max={30}
            value={dc}
            onChange={(e) => setDc(e.target.value)}
          />
        </label>
      </div>

      {BANDS.map((b) => (
        <div key={b.key} className="roll-band">
          <label className="field-label">
            {b.label}
            {b.req ? <span className="muted"> — required</span> : <span className="muted"> — optional</span>}
          </label>
          <textarea
            className="field"
            rows={2}
            value={outcomes[b.key].content}
            onChange={(e) => setBand(b.key, { content: e.target.value })}
            placeholder={b.req ? "What happens…" : "(leave blank to skip)"}
          />
          <label className="field-label hp-field">
            HP change
            <input
              className="field hp-input"
              type="number"
              value={outcomes[b.key].hp}
              onChange={(e) => setBand(b.key, { hp: e.target.value })}
            />
          </label>
        </div>
      ))}

      {error && <p className="error">{error}</p>}

      <div className="form-actions">
        <button type="submit" className="primary-btn" disabled={submitting}>
          {submitting ? "Adding…" : "Add skill check"}
        </button>
        <button type="button" className="ghost-btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
