# StorySim

**StorySim drops a fresh story prompt every day, then hands everyone the pen.** Each reader can branch the tale — writing their own "what happens next" and the choice that leads there — then walk any path through the growing tree, vote the best continuations to the top, and add their own turn with a few bullet points or just their voice. It's a writing-prompts subreddit crossed with an old-school choose-your-own-adventure: one seed, infinite endings, written by the crowd.

## Features

- **Accounts** — username/password signup & login. Login issues a **signed, expiring session token** (HMAC) the client sends as `Authorization: Bearer`; the server derives the user from the verified token, so clients can't impersonate by asserting a user id. Writes (add a node, vote) and the admin endpoint require a valid token; reads stay public.
- **Daily prompts by genre & rating** — each day has one prompt per **genre** (sci-fi, fantasy, mystery, horror) in both a **PG** and a **mature** version. An admin generates the day's set with one click (or the `generate_daily.py` CLI); the home page filters by rating.
- **Branching tree** — every passage is a node; anyone can add a child continuation. Top-level nodes branch directly off the day's prompt.
- **Moderation** — every submitted passage is screened by **Claude** against the story's rating; PG stories reject edgier language with a friendly reason. (Falls back to a local stub when no API key is set.)
- **Traversal UI** — a "your path" timeline (root → current) you can click to jump anywhere; the URL tracks your position so a refresh keeps you put.
- **Upvote / downvote** — thumbs on each node; options are ranked by score (popularity) in SQL.
- **View counts** — opening a node records a visit; the distinct-viewer count is shown on the node page and in the options list.
- **Shadow-tree map** — an in-page **modal** (🗺 on the story view) of the whole node graph: visited nodes are lit, labeled, and clickable; the rest are dim "shadow" silhouettes. It auto-fits with zoom/pan, hover tooltips (score / views / author), and a highlighted "you are here" trail.
- **AI assist** — turn rough notes into a polished passage ("✨ Draft with AI"), one-click **"✨ Let AI continue"** to have Claude write the next branch, and an auto-generated "story so far" recap that fills in as you read. Uses Claude (`claude-opus-4-8`) when `ANTHROPIC_API_KEY` is set; falls back to local stubs otherwise.
- **Trending** — a leaderboard of the top-scoring branches across all stories (`/trending`).
- **Profile / history** — click your username to see what you've **read**, **voted** on, and **written** (`/me`).
- **Author attribution** — "by @author" credits on branch cards, the node header, and map tooltips.
- **Campaign mode** — a story can be `mode='campaign'`: a D&D-style text RPG layered on the same branching tree. Pick from a **curated, story-themed cast** (AI-generated over shared archetypes), then play a stateful **run** — HP + stats, **dice-rolled skill checks** (d20 vs DC, crit bands), **items & inventory** (use a potion; item-gated choices), **authored endings** vs undeveloped dead-ends, a **run summary**, and **save-anywhere rewind**. Authoring is its own "build" lens: see each choice's mechanics, add branches, and AI-draft skill checks. A **branch economy** keeps the canonical tree to 3 in-play choices per node with the rest as votable proposals that get promoted. Full design: [`docs/rpg-statefulness.md`](docs/rpg-statefulness.md). Daily `story`-mode content is unaffected.
- **Voice input** — dictate into any writing field via the Web Speech API.

## Architecture

```
frontend (React/Vite :5173)  ──HTTP /api──▶  backend (FastAPI :5051)  ──SQLAlchemy──▶  Postgres (storysim_db)
```

The Vite dev server proxies `/api/*` to the API, so the browser sees a single origin.

**Stack:** React 18 + Vite + React Router · FastAPI + SQLAlchemy 2 · PostgreSQL · Alembic (migrations) · Anthropic Claude (optional).

## Getting started

### Prerequisites

- Python 3, Node.js, and a running Postgres (`brew services start postgresql@17`).
- A dedicated `storysim_db` database owned by the `storysim_app` role:

  ```bash
  psql -d postgres <<'SQL'
  CREATE ROLE storysim_app WITH LOGIN PASSWORD 'storysim_dev_pw';
  CREATE DATABASE storysim_db OWNER storysim_app;
  SQL
  psql -d storysim_db -c "ALTER SCHEMA public OWNER TO storysim_app;"
  ```

### Backend

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python main.py       # serves http://localhost:5051 (uvicorn, auto-reload)
```

Config lives in `backend/.env` (`DATABASE_URL`, `PORT` (or legacy `FLASK_PORT`), `ANTHROPIC_API_KEY`, and `SECRET_KEY` — used to sign auth tokens; set a strong random value in production). On startup the app runs `create_all` and seeds today's story if none exists. Interactive API docs are available at `http://localhost:5051/docs`.

#### Seed demo data

Populate the database with the four demo stories (branching node trees, community users, and votes):

```bash
cd backend && ./venv/bin/python seed_demo.py        # idempotent: safe to re-run
```

The script is standalone (it creates the schema itself, so it works on a fresh DB) and is a no-op if the demo data is already present. Pass `--reset` to wipe just the four demo stories and reseed:

```bash
./venv/bin/python seed_demo.py --reset
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # serves http://localhost:5173
```

Then open **http://localhost:5173**.

## Database migrations

Schema changes are tracked with **Alembic** (`backend/alembic/`):

```bash
./venv/bin/alembic upgrade head                          # apply pending migrations
./venv/bin/alembic revision --autogenerate -m "message"  # after editing models.py
./venv/bin/alembic current && ./venv/bin/alembic history
```

## Data model

```
users ──< stories                       (author of the daily prompt)
users ──< story_nodes                   (author of a node)
stories ──< story_nodes                 (all nodes in a story)
story_nodes ──< story_nodes             (self-ref tree via parent_node_id; NULL = top-level)
users ──< edge_votes >── story_nodes    (one vote per user per node)
users ──< node_views >── story_nodes    (one row per user per node they've opened)
```

- **users** — `username`, `password_hash` (nullable; seeded community users predate auth), `is_admin`.
- **stories** — a daily prompt: `title`, `blurb`, `genre`, `rating` (`pg`/`mature`). `UNIQUE(publish_date, genre, rating)` — one of each genre×rating per day.
- **story_nodes** — a passage in the tree. `content` is the text; `edge_prompt` is the "choice" label leading into it (NULL for top-level); `parent_node_id` NULL = a direct continuation of the prompt; `summary_so_far` is an AI-generated recap of the path down to this node.
- **edge_votes** — votes on a node/choice. `value` is `+1` or `-1` (enforced by a `CHECK`), with `UNIQUE(user_id, story_node_id)`.
- **node_views** — one row per `(user, node)` the first time a user opens a node. Powers the node's view count (distinct viewers) and the per-user "visited" set for the shadow tree map.

### Edge model & RPG tables

Story structure is now an explicit **edge graph** (`edges` → `edge_outcomes`), not the `parent_node_id`/`edge_prompt` columns (which remain as a synced cache, to be dropped later). A plain edge has one outcome (today's linear story); a roll edge will have 2–4 outcome bands. The RPG layer adds: `effects` (state mutations on an outcome — the extensibility seam), `items` + `requirements`, and per-playthrough state in `runs` → `run_characters`, with a snapshotted `run_steps` log plus `run_inventory` / `run_flags`. `stories.mode` (`story`/`campaign`), `stories.death_policy`, and `story_nodes.kind` gate it. Full rationale and the phased plan: [`docs/rpg-statefulness.md`](docs/rpg-statefulness.md).

## API

| Method & path                               | Purpose                                                                                                                                                                   |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/health`                           | Liveness check                                                                                                                                                            |
| `POST /api/auth/signup`                     | `{username, password}` → `{user: {...}, token}` (201)                                                                                                                    |
| `POST /api/auth/login`                      | `{username, password}` → `{user: {...}, token}`                                                                                                                          |
| `GET /api/auth/me`                          | Resolve the `Authorization: Bearer` token to the current user (401 if missing/invalid/expired)                                                                          |
| `POST /api/admin/generate-daily`            | **Bearer token required**; user must be `is_admin` (401/403 otherwise). Generates today's prompts — one per genre × rating — skipping combos that already exist           |
| `GET /api/stories/today`                    | The current daily story                                                                                                                                                   |
| `GET /api/stories[?rating=&genre=&limit=&offset=]` | Stories, newest first; optional rating/genre filters + paging (`X-Total-Count` header)                                                                            |
| `GET /api/stories/<id>`                     | One story (includes `genre`, `rating`)                                                                                                                                    |
| `GET /api/stories/<id>/nodes[?parent_id=&limit=&offset=]` | Children of a node (omit `parent_id` for top-level). `score` from a LEFT JOIN on `SUM(edge_votes.value)`; ranked by score desc then recency; paged (`X-Total-Count`) |
| `GET /api/nodes/<id>`                       | A node plus its children (structure from the edge model). Includes `my_vote` (`1`/`-1`/`null`) and `view_count`. Records a view for the token's user (first view per node) |
| `GET /api/nodes/<id>/path`                  | The chain of nodes root → this node (lets the UI rebuild traversal from a URL). Lazily generates the current node's "story so far" recap if missing                       |
| `GET /api/stories/<id>/tree`                | Whole node graph for the shadow-tree map: every node with `score`, `view_count`, `author`, and `visited` (for the token's user). `content` only for visited nodes          |
| `POST /api/stories/<id>/nodes`              | **Bearer token required.** Create a node: `{content, edge_prompt?, parent_node_id?}` (author = token's user). Writes the node **+ a plain edge/outcome**. Screened by Claude moderation (422 if blocked); generates `summary_so_far` synchronously |
| `POST /api/nodes/<id>/vote`                 | **Bearer token required.** `{value}` — `1` up / `-1` down / `0` clear. Upsert for the token's user; returns refreshed `score` + `my_vote`                                  |
| `POST /api/ai/draft`                        | `{bullets, story_id, parent_node_id?}` → `{edge_prompt, content}`; polishes rough notes (503 if no API key)                                                               |
| `GET /api/leaderboard[?limit=]`             | Top branches across all stories, ranked by score then views then recency                                                                                                 |
| `GET /api/me/views \| /me/votes \| /me/nodes` | **Bearer token required.** This user's read / voted / authored history (newest first)                                                                                  |
| `GET /api/me/runs`                          | **Bearer token required.** This user's campaign playthroughs                                                                                                             |
| `POST /api/stories/<id>/runs`               | **Bearer token required.** Start a campaign run: `{char_class?, name?}` (warrior/rogue/mage) → run state (party-of-1, HP, stats, choices)                                  |
| `GET /api/runs/<id>`                         | **Bearer token required.** Current run state: node, party snapshot (HP/stats/inventory/flags), and available choices                                                      |
| `POST /api/runs/<id>/take/<edge_id>`        | **Bearer token required.** Take a (plain) choice in a run: applies the outcome's effects, advances, logs a snapshotted step. Returns new state + `applied_effects`        |

## AI features

All AI features live in `backend/llm.py`: drafting, the "story so far" summary, daily-prompt generation, and content moderation. Each transparently calls **Claude** (`claude-opus-4-8`) when `ANTHROPIC_API_KEY` is set in `backend/.env`, and falls back to local stubs otherwise — the same code path works with or without a key.

## Frontend routes

- `/` — list of all stories (rating filter, "load more", and an admin "generate today's prompts" button).
- `/login` — log in or sign up.
- `/stories/:id` — story root (blurb + opening branches). The shadow-tree map opens here as a modal (🗺), not a separate route.
- `/stories/:id/nodes/:nodeId` — a node page. The URL is the source of truth for your position; loading it directly rebuilds the full path from the node's ancestor chain, so a refresh stays put.
- `/trending` — leaderboard of the top-scoring branches across all stories.
- `/me` — your profile: read / voted / written history (and campaign runs).

## Project layout

```
storysim/
├── backend/
│   ├── main.py         FastAPI app: CORS, error envelope, startup seeding, router wiring
│   ├── routers/        route modules (auth, stories, nodes, ai, admin, leaderboard, me, runs)
│   ├── auth.py         token signing + current_user / optional_user / admin deps
│   ├── schemas.py      Pydantic request bodies
│   ├── serializers.py  ORM → JSON dicts + edge-based traversal helpers
│   ├── game.py         RPG run engine: class presets, Effect interpreter, snapshots
│   ├── storybuilder.py authoring helper (node + plain edge/outcome + effects)
│   ├── seeds.py        init_db + first-run daily-story seed
│   ├── models.py       SQLAlchemy models (content, edges/outcomes/effects, runs, …)
│   ├── db.py           engine / session / Base / get_db dependency
│   ├── llm.py          AI draft / summary / daily / moderation (Claude when keyed)
│   ├── seed_demo.py    idempotent demo-data seeder (--reset to wipe + reseed)
│   ├── alembic/        migrations
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/      StoriesList, StoryView, Trending, Profile, Login
│       ├── components/ StoryMapModal, HistoryNav, SummaryPanel, AddOptionForm, VoteButtons, MicButton
│       └── api.js      fetch wrappers
├── docs/
│   └── rpg-statefulness.md   campaign/RPG design (edges, runs, branch economy)
└── README.md
```

## Notes & limitations (MVP)

- **Auth** — passwords are hashed and sessions use signed, expiring Bearer tokens (`itsdangerous`, 7-day expiry), so a client can't impersonate another user. Set a strong `SECRET_KEY` in the environment for production (the default is a dev placeholder) and serve over HTTPS. Still missing for full hardening: token refresh/rotation + server-side revocation (logout is client-side only), and per-account rate limiting.
- **AI** — drafting, summaries, daily generation, and moderation use real Claude when `ANTHROPIC_API_KEY` is set (local stubs otherwise). The daily generator is triggered manually (admin button / `generate_daily.py`) — wire it to a real scheduler (cron) for production. AI calls run synchronously in request handlers, so under real load they'd want to move to background work.
- **Speech-to-text** needs the Web Speech API (Chrome/Edge/Safari) + mic permission; the mic button hides itself where unsupported.
- **Deploy:** the production host must serve `index.html` for unmatched routes (SPA fallback) so a hard refresh on a node URL resolves; lock down `CORS(app)` and move secrets out of `.env`.
