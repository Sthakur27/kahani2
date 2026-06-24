import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getStory, getMyRuns, getRun, startRun, takeEdge } from "../api.js";
import { useAuth } from "../auth.jsx";
import "./CampaignPlay.css";

const CLASSES = [
  { key: "warrior", icon: "🛡", blurb: "Strong & tough — STR/CON, 28 HP." },
  { key: "rogue", icon: "🗡", blurb: "Nimble & clever — DEX/INT, 22 HP." },
  { key: "mage", icon: "✨", blurb: "Keen & wise — INT/WIS, 18 HP." },
];

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

  useEffect(() => {
    getStory(id).then(setStory).catch((e) => setError(e.message));
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
    (charClass) => {
      setBusy(true);
      setError(null);
      startRun(id, { char_class: charClass })
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
        <ClassPicker story={story} busy={busy} onPick={begin} />
      ) : (
        <RunView
          run={run}
          story={story}
          busy={busy}
          lastEffects={lastEffects}
          lastRoll={lastRoll}
          onChoose={choose}
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

function ClassPicker({ story, busy, onPick }) {
  return (
    <div className="class-picker">
      <h1>{story ? story.title : "Begin your run"}</h1>
      {story && <p className="blurb lead">{story.blurb}</p>}
      <h3 className="branches-title">Choose your character</h3>
      <div className="class-grid">
        {CLASSES.map((c) => (
          <button
            key={c.key}
            type="button"
            className="class-card"
            disabled={busy}
            onClick={() => onPick(c.key)}
          >
            <span className="class-icon">{c.icon}</span>
            <span className="class-name">{c.key}</span>
            <span className="class-blurb">{c.blurb}</span>
          </button>
        ))}
      </div>
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

function RunView({ run, story, busy, lastEffects, lastRoll, onChoose, onRestart }) {
  const char = run.snapshot?.characters?.[0];
  const dead = run.status === "dead";
  const won = run.status === "won";
  const ended = !dead && !won && run.choices.length === 0;
  const atStart = run.current_node_id == null;
  const passage = atStart ? story?.blurb : run.node?.content;

  return (
    <div className="run">
      {char && <CharacterSheet char={char} />}

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
            <p className="muted">Your run ends here.</p>
            <button type="button" className="primary-btn" onClick={onRestart}>
              Start a new run
            </button>
          </div>
        )}
        {won && (
          <div className="run-end run-won">
            <h2>👑 Your story ends</h2>
            <button type="button" className="primary-btn" onClick={onRestart}>
              Play again
            </button>
          </div>
        )}
        {ended && (
          <div className="run-end">
            <h2>The path ends here</h2>
            <p className="muted">No further choices have been written down this way.</p>
            <button type="button" className="ghost-btn" onClick={onRestart}>
              Start over
            </button>
          </div>
        )}

        {!dead && !won && run.choices.length > 0 && (
          <>
            <h3 className="branches-title">What do you do?</h3>
            <ul className="choice-list">
              {run.choices.map((c) => (
                <li key={c.edge_id}>
                  <button
                    type="button"
                    className="choice-btn"
                    disabled={busy}
                    onClick={() => onChoose(c.edge_id)}
                  >
                    {c.kind === "roll" && c.check_stat && (
                      <span className="check-tag">
                        {c.check_stat.toUpperCase()} {c.check_dc}
                      </span>
                    )}
                    {c.label}
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
