# StorySim → Stateful Text RPG — Design Doc

**Status:** Draft for review · **Author:** (design session) · **Scope:** turns the
collaborative branching story into an optional D&D-style text RPG with stats,
dice-rolled skill checks, items, HP, and per-player playthroughs.

---

## 1. Goals & non-goals

**Goals**
- Authors can make a choice into a **roll node** with 2–4 authored outcomes
  (crit-fail*, fail, success, crit-success*) — `*` optional.
- A choice can also just apply **direct effects** with no roll
  (e.g. "wade through the bug-infested jungle → −3 HP").
- Players have **persistent character state**: HP, six stats, an inventory, and
  story flags, evolving as they traverse the tree.
- Server-authoritative dice (no client cheating), with a full **roll/step log**.
- **Backwards compatible**: existing stories keep working untouched; the RPG
  layer is opt-in per story, and "linear" is just the degenerate case of the
  general model.

**Non-goals (for now)**
- Multiplayer/shared runs (state is per user per run).
- Combat sub-systems / turn order. A "fight" is modeled as roll nodes.
- Real-time anything.

**Guiding principle — separate three concerns that change at different rates:**

| Layer | What | Who owns it | Mutability |
|---|---|---|---|
| **Content** | passages of prose (`StoryNode`) | authors, shared | append-only |
| **Rules** | what a choice does: checks, branches, effects (`Edge`, `EdgeOutcome`, `Effect`) | authors, shared | append-only |
| **Player state** | HP/stats/inventory/flags for one playthrough (`Run`, `RunStep`, …) | one user, private | mutates constantly |

Keeping these strictly separate is what stops us getting "shot in the foot": new
mechanics become new **rows** (effect types, items) or new **config**, not schema
rewrites.

---

## 2. The big model shift: explicit Edges

Today a choice is implicit: a child node carries `parent_node_id` + `edge_prompt`,
and "the children are the choices." That can't express "one action, several
possible destinations depending on a die roll." So we promote the **choice** to a
first-class entity and split it from its **destinations**.

```mermaid
erDiagram
    STORY ||--o{ STORY_NODE : has
    STORY ||--o{ EDGE : has
    STORY_NODE ||--o{ EDGE : "offers (from_node)"
    EDGE ||--o{ EDGE_OUTCOME : "resolves to"
    EDGE_OUTCOME }o--|| STORY_NODE : "leads to (to_node)"
    EDGE_OUTCOME ||--o{ EFFECT : applies
    EDGE ||--o{ REQUIREMENT : gated_by
    STORY ||--o{ ITEM : defines

    USER ||--o{ RUN : plays
    STORY ||--o{ RUN : "is played in"
    RUN ||--o{ RUN_STEP : logs
    RUN ||--o{ RUN_INVENTORY : holds
    RUN ||--o{ RUN_FLAG : remembers
    RUN_STEP }o--|| EDGE : "taken"
    RUN_STEP }o--|| STORY_NODE : "arrived_at"
```

- **A plain choice** = an `Edge(kind='plain')` with exactly **one** outcome
  (`band='plain'`). The old linear story is exactly this. ✅ migration is mechanical.
- **A roll choice** = an `Edge(kind='roll')` with a check (`stat`,`dc`) and **2–4**
  outcomes keyed by result band.

### 2.5 Two modes: Story vs Campaign

The RPG layer changes the *vibe*, so it's framed as a content mode, not just a
mechanics flag. **Mechanics (`mode`) and cadence (publish schedule) are
orthogonal**, but paired by convention:

| | `mode = 'story'` *(today)* | `mode = 'campaign'` *(new)* |
|---|---|---|
| Vibe | a daily branching tale | a D&D-style adventure |
| Cadence (convention) | **daily** | **weekly / monthly** |
| Mechanics | plain edges only; no stats/HP | stats, HP, dice rolls, items |
| Player state | none (just "which node") | a saveable `Run` (HP/stats/inventory) |
| UI | reading view as-is | + character sheet, HP bar, dice, inventory |

Cadence is purely a *scheduling* concern (`Story.publish_date` already exists; a
campaign just publishes less often) — it adds **no schema**. The daily-generation
job gains a campaign variant later. Existing daily content stays `mode='story'`
and is completely unaffected.

---

## 3. Data model

### 3.1 Content & structure (shared, authored)

**`Story`** *(existing — add columns)*
- `mode: 'story' | 'campaign'` (default `'story'`) — see §2.5. `campaign` unlocks
  the RPG layer (stats/HP/dice/items, saveable runs).
- `death_policy: 'save_anywhere' | 'checkpoint' | 'permadeath'` (default
  `'save_anywhere'`).
- *(optional later)* `starting_hp`, `starting_kit_id`, `class_options`, cadence.

**`StoryNode`** *(existing — simplify)*
- Keep: `id, story_id, content, summary_so_far, user_id (author), created_at`.
- **Drop** `parent_node_id` and `edge_prompt` as the source of truth — structure
  now lives in `Edge`/`EdgeOutcome`. (We may keep a *derived* `parent_node_id`
  purely as a denormalized cache for the map; see §7.)
- Optional: `is_checkpoint: bool` (see §6 persistence).

**`Edge`** — a choice/action available from a node.
- `id`
- `story_id` *(denormalized for cheap per-story queries)*
- `from_node_id: FK StoryNode | NULL` — `NULL` = a choice off the story's opening
  blurb (today's "top-level" nodes).
- `label: str` — the choice text shown to the reader (was `edge_prompt`).
- `kind: 'plain' | 'roll'`
- `check_stat: 'str'|'dex'|'con'|'int'|'wis'|'cha' | NULL` *(roll only)*
- `check_dc: int | NULL` *(roll only)*
- `created_by, created_at`

**`EdgeOutcome`** — where an edge leads, per result band.
- `id, edge_id`
- `band: 'plain' | 'crit_fail' | 'fail' | 'success' | 'crit_success'`
- `to_node_id: FK StoryNode` — destination passage.
- Uniqueness: one row per `(edge_id, band)`.
- Rules: `plain` edge → exactly one `plain` outcome. `roll` edge → `fail` +
  `success` **required**, `crit_fail`/`crit_success` **optional** (fall back to
  fail/success when absent).

**`Effect`** — a state mutation applied when an outcome is taken. *(The main
extensibility point — new mechanics = new `type` values, no schema change.)*
- `id, outcome_id`
- `type: 'hp_delta' | 'max_hp_delta' | 'stat_delta' | 'grant_item' | 'consume_item' | 'set_flag' | 'heal_full' | 'end_run' | …`
- `amount: int | NULL` (hp/stat deltas)
- `stat: str | NULL` (for `stat_delta`)
- `item_id: FK Item | NULL`, `count: int | NULL` (item effects)
- `flag_key: str | NULL`, `flag_value: str | NULL` (for `set_flag`)
- `meta: JSON` (escape hatch for future params)
- This unifies **stat-check rewards** and **direct modifiers**: "jungle −3 HP" is a
  `plain` edge whose single outcome has one `hp_delta:-3` effect.

**`Requirement`** — a gate to even *attempt* an edge *(optional in MVP)*.
- `id, edge_id, type: 'item'|'stat_min'|'flag', key, amount`
- e.g. "needs `rope`", "needs STR ≥ 14", "flag `met_ferryman` = true".

**`Item`** — catalog of item definitions (shared).
- `id, story_id (NULL = global catalog), slug, name, description`
- `kind: 'consumable' | 'equipment' | 'key'`
- `on_use_effects: JSON | via Effect rows` — e.g. health potion → `hp_delta:+10`.
- Equipment may carry passive `stat`/`max_hp` modifiers (later).

### 3.2 Player state (private, per playthrough)

**`Run`** — one playthrough of one story by one user.
- `id, user_id, story_id`
- `current_node_id: FK StoryNode | NULL` (NULL = at the opening blurb)
- `hp: int, max_hp: int`
- `str, dex, con, int, wis, cha: int` *(the six core stats as columns — typed &
  queryable; exotic attributes can live in `RunFlag`)*
- `status: 'active' | 'dead' | 'won' | 'abandoned'`
- `last_checkpoint_step_id: FK RunStep | NULL`
- `started_at, updated_at`
- A user may have multiple runs of a story (history / restart) — `(user, story)`
  is **not** unique. Convention: one `active` run per `(user, story)` at a time.

**`RunStep`** — the append-only log of everything that happened, **with a state
snapshot**. This single table is the key to the persistence question (§6).
- `id, run_id, seq` (0,1,2,…)
- `edge_id: FK Edge | NULL` (the choice taken to produce this step; NULL for the
  initial "spawn" step)
- `arrived_node_id: FK StoryNode | NULL`
- `roll_d20: int | NULL`, `modifier: int | NULL`, `dc: int | NULL`,
  `band_result: str | NULL` (which outcome fired)
- `effects_applied: JSON` (audit of what changed)
- **`snapshot: JSON`** — full state *after* this step: `{hp,max_hp,stats,inventory,flags}`.
  Cheap (a few hundred bytes); makes rewind/restore to any step trivial.
- `created_at`

**`RunInventory`** — current live inventory (denormalized from the log for fast reads).
- `id, run_id, item_id, count` — unique `(run_id, item_id)`.

**`RunFlag`** — arbitrary boolean/string story state for this run.
- `id, run_id, key, value` — unique `(run_id, key)`. ("has_key", "spared_the_ghost".)

*(Inventory + flags are also captured in each `RunStep.snapshot`, so they're
restorable; the live tables are just the convenient "current" view.)*

---

## 4. Mechanics

### 4.1 Resolving a roll
1. Player takes an `Edge`. Server checks `Requirement`s (else 409 "can't yet").
2. If `kind='plain'` → fire the single outcome.
3. If `kind='roll'`:
   - `modifier = floor((stat - 10) / 2)` (D&D-style; stats ~8–18).
   - `roll = d20` (server RNG, logged).
   - **Band:** natural 20 → `crit_success`; natural 1 → `crit_fail`; else
     `roll + modifier ≥ dc` → `success` else `fail`.
   - If the chosen band has no authored outcome, fall back: `crit_*` → its base
     band (`success`/`fail`); base bands always exist.
4. Apply the outcome's `Effect`s in order → mutate `Run` (hp/stats/inventory/flags).
5. Set `current_node_id = outcome.to_node_id`; append a `RunStep` with snapshot.
6. If `hp ≤ 0` (or an `end_run` effect) → `status='dead'` and apply the death
   policy (§6).

### 4.2 Effects are data, not code
A small interpreter applies `Effect` rows by `type`. Adding "gain XP", "set
reputation", "teleport to node" later = a new `type` + a branch in the
interpreter. **No migration.**

### 4.3 Character creation
**Recommended MVP:** class presets at run start (Warrior / Rogue / Mage), each a
stat spread + starting HP + starting kit (items). Point-buy can be added later as
just a different way to populate the same `Run` columns. Linear stories skip this
entirely.

---

## 5. Authoring flow

Creating a choice (in an RPG story) offers:
- **Plain** (the old way) — label + destination passage, optionally with direct
  effects (±HP, grant/consume item).
- **Roll** — pick `stat` + `DC`, then author the **fail** and **success**
  passages (required) and optionally **crit-fail** / **crit-success**. Each band
  gets its own prose + effects.
- **"Not creative enough" → linear:** the author just makes a Plain choice. The
  model needs no special "linear mode" — plain *is* linear.

**AI tie-in (recommended):** the existing `/ai/draft` can, for a roll edge,
propose a fitting `stat`+`DC` and draft the 2–4 outcome passages + effects from
the prose; the author edits before posting. Strong, on-brand use of Claude.

---

## 6. The persistence question — solved by the step log

The user raised three options. **Key realization:** if every `RunStep` carries a
full state `snapshot` (cheap), then *all three become a policy choice, not a
schema choice.* We log everything once and pick behavior with config.

| Policy | Behavior | Implementation on top of the step log |
|---|---|---|
| **Save anywhere** *(default)* | save/restore at any visited step | restore any chosen `RunStep.snapshot`; mark later steps `undone`; optional named save slots |
| **Checkpoints** | restore to last checkpoint on death | mark some outcomes/nodes `is_checkpoint`; `Run.last_checkpoint_step_id`; on death restore that step's snapshot, truncate later steps |
| **Permadeath** ("you die, you die") | death ends the run; start fresh | on death set `status='dead'`; reads block; new `Run` to replay |

**Decision:** ship the **step-log-with-snapshots** schema now and default
`death_policy` to **`save_anywhere`** (most flexible — players save/restore at
any visited step; the natural fit for a longer weekly campaign). `checkpoint` and
`permadeath` remain available per story without any schema change.

**Save UX for `save_anywhere`:** every step is implicitly snapshotted, so "Save"
is really "name/bookmark this step" and "Load" restores its snapshot (later steps
marked `undone`). We can also offer named save slots on top of the same log.

**Immersion note:** free restore lets a player re-roll a failed check by loading
and retrying. For campaigns where that matters, an author can set
`death_policy='checkpoint'` (restore only at checkpoints) or `'permadeath'`. The
default favors flexibility per the product direction; the knob is per story.

---

## 7. How existing features map

- **Shadow-tree map:** built from `Edge`/`EdgeOutcome` instead of `parent_node_id`.
  A node's children = `to_node` of its edges' outcomes. Roll edges fan out to up
  to 4 children; render them with a 🎲 marker and band labels. We can keep a
  derived `parent_node_id` cache on `StoryNode` so the map/path queries stay cheap.
- **Path / breadcrumb:** for a *run*, the path is the ordered `RunStep`s (what you
  actually rolled) — strictly better than structural parent-walk. For anonymous
  browsing (no run), fall back to the structural tree.
- **Votes / views:** unchanged — still per-`StoryNode` aggregates. (Could add
  edge-level voting later.)
- **Linear stories:** `mode='linear'`, all edges `plain`, no Run required to read
  (or a trivial run with no stats/HP shown). Zero UX change for them.

---

## 8. Migration plan (Alembic + data backfill)

1. Add new tables (`edges`, `edge_outcomes`, `effects`, `items`, `runs`,
   `run_steps`, `run_inventory`, `run_flags`, `requirements`) + `stories.mode`.
2. **Backfill** from current data: for every `StoryNode` with a parent, create
   `Edge(from_node_id=parent, label=edge_prompt, kind='plain')` + one
   `EdgeOutcome(band='plain', to_node_id=node)`. Root-level nodes → edges with
   `from_node_id=NULL`. No content is lost; every current path becomes a plain edge.
3. Leave `parent_node_id`/`edge_prompt` in place initially (as the derived cache),
   drop later once the edge model is proven.
4. All existing stories stay `mode='linear'` → no behavior change.

---

## 9. API surface (new / changed)

```
# authoring (RPG)
POST   /api/stories/{id}/edges            create a choice (plain or roll + outcomes + effects)
GET    /api/nodes/{id}/edges              choices available at a node
POST   /api/ai/draft-roll                 AI proposes check + outcome drafts

# playing
POST   /api/stories/{id}/runs             start a run (pick class/preset) -> Run
GET    /api/runs/{id}                     current state (hp, stats, inventory, flags, node)
POST   /api/runs/{id}/take/{edge_id}      attempt an edge -> {roll, band, effects, new node, state}
POST   /api/runs/{id}/use-item/{item_id}  consume an item -> effects applied
POST   /api/runs/{id}/restore/{step_id}   rewind/checkpoint restore (policy-gated)
GET    /api/me/runs                        my playthroughs (extends the profile/history feature)
```

Reading endpoints (`/nodes/{id}`, tree, path) gain an optional `?run_id=` so the
view can reflect run state (locked edges, requirements, current HP).

---

## 10. Phased rollout (per-feature commits)

1. **Schema + migration + backfill** — new tables, `Story.mode`, edge backfill;
   no UI yet. Verify existing app still works on the edge-backed model.
2. **Edge-backed reading** — switch the read/tree/path endpoints to edges
   (all plain). Frontend unchanged. (De-risks the big refactor before adding RPG.)
3. **Runs + HP + class presets** — start a run, HP bar + character sheet UI,
   `take-edge` for plain edges applying direct effects (the "−3 HP jungle").
4. **Roll edges** — authoring 2–4 outcomes, server dice, roll animation, bands.
5. **Items & inventory** — catalog, grant/consume, use-item, health potion.
6. **Death policy + checkpoints**, then optional permadeath / free-rewind flags.
7. **AI roll-drafting** — Claude proposes checks + outcome prose.

---

## 11. Decisions

**Settled**
- ✅ **Modes:** `story` (daily, light) vs `campaign` (RPG, weekly/monthly). §2.5
- ✅ **Persistence:** snapshot-per-step log; default `death_policy='save_anywhere'`,
  per-story override. §6
- ✅ **Edge refactor:** do the full content→edge migration (Phases 1–2) for a clean base.

**Still to confirm (low-stakes; recommended defaults in parens — I'll proceed on
these unless you say otherwise):**
1. **Stat scale & modifier** — *(D&D-style 8–18 stats, `floor((s-10)/2)` mod, d20 vs DC)*
2. **Character creation** — *(class presets: Warrior / Rogue / Mage)*
3. **Crit rule** — *(natural 1/20 → crit bands, else fall back to fail/success)*
