import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getStory,
  getStoryCharacters,
  getMyRuns,
  getRun,
  getRunSummary,
  startRun,
  takeEdge,
  useItem,
  restoreStep,
} from "../api.js";
import { useAuth } from "../auth.jsx";
import "./CampaignPlay.css";

const STAT_ORDER = ["str", "dex", "con", "int", "wis", "cha"];

// Render the effects a step applied as short chips ("−5 HP", "Healed", "+1 DEX").
function effectLabel(e) {
  if (e.type === "hp_delta") return `${e.amount > 0 ? "+" : ""}${e.amount} HP`;
  if (e.type === "max_hp_delta") return `${e.amount > 0 ? "+" : ""}${e.amount} max HP`;
  if (e.type === "heal_full") return "Fully healed";
  if (e.type === "stat_delta") return `${e.amount > 0 ? "+" : ""}${e.amount} ${e.stat?.toUpperCase()}`;
  if (e.type === "grant_item") return "Found an item";
  if (e.type === "set_flag") return null; // silent
  if (e.type === "end_run") return "The story ends";
  return e.type;
}

export default function CampaignPlay() {
  const { id } = useParams();
  const { user } = useAuth();
  const [story, setStory] = useState(null);
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [lastEffects, setLastEffects] = useState([]);
  const [lastRoll, setLastRoll] = useState(null);
  const [summary, setSummary] = useState(null);
  const [cast, setCast] = useState(null);

  useEffect(() => {
    getStory(id).then(setStory).catch((e) => setError(e.message));
    getStoryCharacters(id).then(setCast).catch(() => setCast([]));
  }, [id]);

  // Resume an active run for this story if one exists; else land on the class picker.
  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    getMyRuns()
      .then((runs) => {
        const active = runs.find(
          (r) => r.story_id === Number(id) && r.status === "active"
        );
        if (cancelled) return;
        if (active) return getRun(active.id).then((s) => !cancelled && setRun(s));
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [id, user]);

  const begin = useCallback(
    (option) => {
      setBusy(true);
      setError(null);
      const body = option.id
        ? { option_id: option.id }
        : { char_class: option.archetype };
      startRun(id, body)
        .then((s) => {
          setRun(s);
          setLastEffects([]);
          setLastRoll(null);
        })
        .catch((e) => setError(e.message))
        .finally(() => setBusy(false));
    },
    [id]
  );

  const choose = useCallback(
    (edgeId) => {
      if (!run || busy) return;
      setBusy(true);
      setError(null);
      takeEdge(run.id, edgeId)
        .then((s) => {
          setRun(s);
          setLastEffects(s.applied_effects || []);
          setLastRoll(s.roll || null);
        })
        .catch((e) => setError(e.message))
        .finally(() => setBusy(false));
    },
    [run, busy]
  );

  const consume = useCallback(
    (itemId) => {
      if (!run || busy) return;
      setBusy(true);
      setError(null);
      useItem(run.id, itemId)
        .then((s) => {
          setRun(s);
          setLastEffects(s.applied_effects || []);
          setLastRoll(null);
        })
        .catch((e) => setError(e.message))
        .finally(() => setBusy(false));
    },
    [run, busy]
  );

  const rewind = useCallback(
    (stepId) => {
      if (!run || busy) return;
      setBusy(true);
      setError(null);
      restoreStep(run.id, stepId)
        .then((s) => {
          setRun(s);
          setLastEffects([]);
          setLastRoll(null);
        })
        .catch((e) => setError(e.message))
        .finally(() => setBusy(false));
    },
    [run, busy]
  );

  // When the run reaches a terminal state (death / authored ending / dead-end),
  // pull the journey recap for the end screen.
  useEffect(() => {
    if (!run) {
      setSummary(null);
      return;
    }
    const terminal =
      run.status !== "active" || run.node?.is_ending || run.choices.length === 0;
    if (!terminal) {
      setSummary(null);
      return;
    }
    let cancelled = false;
    getRunSummary(run.id)
      .then((s) => !cancelled && setSummary(s))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [run]);

  if (!user) {
    return (
      <div className="play">
        <Link to={`/stories/${id}`} className="back">← back to story</Link>
        <p className="muted">
          You need to <Link to="/login" className="link-like">log in</Link> to play a campaign.
        </p>
      </div>
    );
  }
  if (error) return <p className="error">Error: {error}</p>;
  if (loading) return <p className="muted">Loading…</p>;

  return (
    <div className="play">
      <div className="play-topbar">
        <Link to={`/stories/${id}`} className="back">← back to story</Link>
        {story && <span className="play-title">⚔ {story.title}</span>}
      </div>

      {!run ? (
        <ClassPicker story={story} cast={cast} busy={busy} onPick={begin} />
      ) : (
        <RunView
          run={run}
          story={story}
          busy={busy}
          lastEffects={lastEffects}
          lastRoll={lastRoll}
          summary={summary}
          canRewind={story?.death_policy !== "permadeath"}
          onChoose={choose}
          onUseItem={consume}
          onRewind={rewind}
          onRestart={() => {
            setRun(null);
            setLastEffects([]);
            setLastRoll(null);
          }}
        />
      )}
    </div>
  );
}

function ClassPicker({ story, cast, busy, onPick }) {
  return (
    <div className="class-picker">
      <h1>{story ? story.title : "Begin your run"}</h1>
      {story && <p className="blurb lead">{story.blurb}</p>}
      <h3 className="branches-title">Choose your character</h3>
      {cast === null ? (
        <p className="muted">Loading the cast…</p>
      ) : (
        <div className="class-grid">
          {cast.map((c, i) => (
            <button
              key={c.id ?? c.archetype ?? i}
              type="button"
              className="class-card"
              disabled={busy}
              onClick={() => onPick(c)}
            >
              <span className="class-icon">{c.icon}</span>
              <span className="class-name">{c.name}</span>
              <span className="class-blurb">{c.blurb}</span>
              <span className="class-stats">
                ❤ {c.hp} HP · {c.archetype}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const VERDICT = {
  crit_success: "Critical success!",
  success: "Success",
  fail: "Failed",
  crit_fail: "Critical fail!",
};

function RollBanner({ roll }) {
  const band = roll.effective_band || roll.band;
  const mod =
    roll.modifier >= 0 ? `+ ${roll.modifier}` : `− ${Math.abs(roll.modifier)}`;
  return (
    <div className={"roll-banner roll-" + band}>
      🎲 {roll.stat?.toUpperCase()} check — rolled <b>{roll.d20}</b> {mod} ={" "}
      <b>{roll.total}</b> vs DC {roll.dc} → <b>{VERDICT[band] || band}</b>
    </div>
  );
}

function RunView({ run, story, busy, lastEffects, lastRoll, summary, canRewind, onChoose, onUseItem, onRewind, onRestart }) {
  const char = run.snapshot?.characters?.[0];
  const dead = run.status === "dead";
  const isEnding = run.status === "won" || run.node?.is_ending;
  // An undeveloped leaf (no one has written past here) — NOT a real ending.
  const deadEnd = !dead && !isEnding && run.choices.length === 0;
  const atStart = run.current_node_id == null;
  const passage = atStart ? story?.blurb : run.node?.content;

  return (
    <div className="run">
      <div className="run-side">
        {char && <CharacterSheet char={char} />}
        <Inventory
          items={run.inventory || []}
          busy={busy}
          active={run.status === "active"}
          onUse={onUseItem}
        />
      </div>

      <section className="run-main">
        {lastRoll && <RollBanner roll={lastRoll} />}
        {lastEffects.filter((e) => effectLabel(e)).length > 0 && (
          <div className="effects-flash">
            {lastEffects.map((e, i) => {
              const label = effectLabel(e);
              if (!label) return null;
              const bad = e.type === "hp_delta" && e.amount < 0;
              const good =
                e.type === "heal_full" ||
                (e.type === "hp_delta" && e.amount > 0) ||
                e.type === "max_hp_delta" ||
                e.type === "stat_delta";
              return (
                <span
                  key={i}
                  className={"fx" + (bad ? " fx-bad" : good ? " fx-good" : "")}
                >
                  {label}
                </span>
              );
            })}
          </div>
        )}

        {run.node?.kind && run.node.kind !== "story" && (
          <span className={"node-kind kind-" + run.node.kind}>{run.node.kind}</span>
        )}
        <p className="blurb lead">{passage}</p>

        {dead && (
          <div className="run-end run-dead">
            <h2>💀 You have fallen</h2>
            <RunSummary
              summary={summary}
              canRewind={canRewind}
              busy={busy}
              onRewind={onRewind}
            />
            <button type="button" className="primary-btn" onClick={onRestart}>
              Start a new run
            </button>
          </div>
        )}
        {!dead && isEnding && (
          <div className="run-end run-won">
            <h2>📖 An ending</h2>
            <p className="muted">You've reached one of this story's endings.</p>
            <RunSummary
              summary={summary}
              canRewind={canRewind}
              busy={busy}
              onRewind={onRewind}
            />
            <button type="button" className="primary-btn" onClick={onRestart}>
              Play again
            </button>
          </div>
        )}
        {deadEnd && (
          <div className="run-end run-deadend">
            <h2>✍ The trail goes cold</h2>
            <p className="muted">
              No one has written past here yet — this isn't an ending, just an
              unwritten path. Add the next branch in{" "}
              <Link to={`/stories/${story?.id}/nodes/${run.current_node_id}`}>
                build mode
              </Link>
              , or:
            </p>
            <RunSummary
              summary={summary}
              canRewind={canRewind}
              busy={busy}
              onRewind={onRewind}
            />
            <button type="button" className="ghost-btn" onClick={onRestart}>
              Start over
            </button>
          </div>
        )}

        {!dead && !isEnding && run.choices.length > 0 && (
          <>
            <h3 className="branches-title">What do you do?</h3>
            <ul className="choice-list">
              {run.choices.map((c) => (
                <li key={c.edge_id}>
                  <button
                    type="button"
                    className={"choice-btn" + (c.locked ? " locked" : "")}
                    disabled={busy || c.locked}
                    onClick={() => !c.locked && onChoose(c.edge_id)}
                  >
                    {c.locked && <span className="lock-icon">🔒</span>}
                    {c.kind === "roll" && c.check_stat && (
                      <span className="check-tag">
                        {c.check_stat.toUpperCase()} {c.check_dc}
                      </span>
                    )}
                    {c.label}
                    {c.requires?.length > 0 && (
                      <span className="req-tags">
                        {c.requires.map((r, i) => (
                          <span key={i} className={"req-tag" + (r.met ? " met" : "")}>
                            {r.met ? "✓ " : "needs "}
                            {r.text}
                          </span>
                        ))}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}

function Inventory({ items, busy, active, onUse }) {
  return (
    <aside className="inventory">
      <div className="inv-head">Inventory</div>
      {items.length === 0 ? (
        <p className="inv-empty">Empty-handed.</p>
      ) : (
        <ul className="inv-list">
          {items.map((it) => (
            <li key={it.item_id} className="inv-item">
              <span className="inv-icon">{it.icon}</span>
              <span className="inv-name">
                {it.name}
                {it.count > 1 ? ` ×${it.count}` : ""}
              </span>
              {it.usable && active && (
                <button
                  type="button"
                  className="inv-use"
                  disabled={busy}
                  onClick={() => onUse(it.item_id)}
                >
                  Use
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

function RunSummary({ summary, canRewind, busy, onRewind }) {
  if (!summary) return null;
  const s = summary.stats;
  return (
    <div className="run-summary">
      <div className="summary-stats">
        <span>🗺 {s.turns} steps</span>
        <span>💔 {s.damage_taken} damage taken</span>
        {s.rolls > 0 && (
          <span>🎲 {s.successes}/{s.rolls} checks passed</span>
        )}
      </div>
      {summary.journey.length > 0 && (
        <>
          {canRewind && onRewind && (
            <p className="rewind-hint muted">↩ Rewind to any earlier step and play on:</p>
          )}
          <ol className="summary-journey">
            {summary.journey.map((j) => (
              <li key={j.id ?? j.seq}>
                <span className="j-label">{j.label}</span>
                {j.roll && (
                  <span className={"j-roll band-" + j.roll.band}>🎲 {j.roll.band}</span>
                )}
                {j.hp_after != null && <span className="j-hp">{j.hp_after} HP</span>}
                {canRewind && onRewind && (
                  <button
                    type="button"
                    className="j-rewind"
                    disabled={busy}
                    title="Rewind to here"
                    onClick={() => onRewind(j.id)}
                  >
                    ↩
                  </button>
                )}
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

function CharacterSheet({ char }) {
  const pct = Math.max(0, Math.round((char.hp / char.max_hp) * 100));
  const low = pct <= 33;
  return (
    <aside className="char-sheet">
      <div className="char-head">
        <span className="char-name">{char.name}</span>
        <span className="char-class">{char.class}</span>
      </div>
      <div className="hp-row">
        <span className="hp-label">HP</span>
        <div className="hp-bar">
          <div
            className={"hp-fill" + (low ? " hp-low" : "")}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="hp-num">
          {char.hp}/{char.max_hp}
        </span>
      </div>
      <div className="stat-grid">
        {STAT_ORDER.map((k) => (
          <div key={k} className="stat">
            <span className="stat-key">{k.toUpperCase()}</span>
            <span className="stat-val">{char.stats[k]}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
