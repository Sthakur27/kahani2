# StorySim

**StorySim drops a fresh story prompt every day, then hands everyone the pen.** Each reader can branch the tale — writing their own "what happens next" and the choice that leads there — then walk any path through the growing tree, vote the best continuations to the top, and add their own turn with a few bullet points or just their voice. It's a writing-prompts subreddit crossed with an old-school choose-your-own-adventure: one seed, infinite endings, written by the crowd.

## Features

- **Accounts** — username/password signup & login. Login issues a **signed, expiring session token** (HMAC) the client sends as `Authorization: Bearer`; the server derives the user from the verified token, so clients can't impersonate by asserting a user id. Writes (add a node, vote) and the admin endpoint require a valid token; reads stay public.
- **Daily prompts by genre & rating** — each day has one prompt per **genre** (sci-fi, fantasy, mystery, horror) in both a **PG** and a **mature** version. An admin generates the day's set with one click (or the `generate_daily.py` CLI); the home page filters by rating.
- **Branching tree** — every passage is a node; anyone can add a child continuation. Top-level nodes branch directly off the day's prompt.
- **Moderation** — every submitted passage is screened (stubbed AI) against the story's rating; PG stories reject edgier language with a friendly reason.
- **Traversal UI** — a "your path" timeline (root → current) you can click to jump anywhere; the URL tracks your position so a refresh keeps you put.
- **Upvote / downvote** — thumbs on each node; options are ranked by score (popularity) in SQL.
- **View counts** — opening a node records a visit; the distinct-viewer count is shown on the node page and in the options list.
- **Shadow tree map** — a per-story map (`/stories/:id/map`) of the whole node graph: nodes you've visited are lit and labeled (and clickable to jump straight there); the rest are dim "shadow" silhouettes of paths you haven't explored yet.
- **AI assist** — turn rough bullet points into a polished passage ("Draft with AI"), and an auto-generated "story so far" recap on each node. Currently stubbed locally; uses Claude when an API key is set.
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

Writes with no `user_id` still fall back to a seeded `demo` user (the backend's quick-and-dirty default).

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
| `GET /api/nodes/<id>[?user_id=N]`           | A node plus its children. Includes `my_vote` (`1`/`-1`/`null`) and `view_count`. Records a view for the acting user (first view per node)                                 |
| `GET /api/nodes/<id>/path`                  | The chain of nodes root → this node (lets the UI rebuild traversal from a URL)                                                                                            |
| `GET /api/stories/<id>/tree[?user_id=N]`    | Whole node graph for the shadow-tree map: every node with `score`, `view_count`, and `visited` (whether the acting user has opened it)                                    |
| `POST /api/stories/<id>/nodes`              | **Bearer token required.** Create a node: `{content, edge_prompt?, parent_node_id?}` (author = token's user). Screened by moderation (422 if blocked); generates `summary_so_far` synchronously |
| `POST /api/nodes/<id>/vote`                 | **Bearer token required.** `{value}` — `1` up / `-1` down / `0` clear. Upsert for the token's user; returns refreshed `score` + `my_vote`                                  |
| `POST /api/ai/draft`                        | `{bullets, story_id, parent_node_id?}` → `{edge_prompt, content}`; polishes rough notes                                                                                   |

## AI features

The "Draft with AI" and "story so far" summary live in `backend/llm.py`. They are currently **stubbed** — local logic derives the output, so no API key is needed. Set `ANTHROPIC_API_KEY` in `backend/.env` and the real Claude calls (model `claude-opus-4-8`) are used automatically instead.

## Frontend routes

- `/` — list of all stories (rating filter, "load more", and an admin "generate today's prompts" button).
- `/login` — log in or sign up.
- `/stories/:id` — story root (blurb + opening branches).
- `/stories/:id/nodes/:nodeId` — a node page. The URL is the source of truth for your position; loading it directly rebuilds the full path from the node's ancestor chain, so a refresh stays put.
- `/stories/:id/map` — the shadow-tree map of the whole story (visited nodes lit + clickable, the rest as shadows).

## Project layout

```
storysim/
├── backend/
│   ├── main.py         FastAPI app: CORS, error envelope, startup seeding, router wiring
│   ├── routers/        route modules (auth, stories, nodes, ai, admin, leaderboard)
│   ├── auth.py         token signing + current_user / optional_user / admin deps
│   ├── schemas.py      Pydantic request bodies
│   ├── serializers.py  ORM → JSON dicts + ancestor_chain / record_view helpers
│   ├── seeds.py        init_db + first-run daily-story seed
│   ├── models.py       SQLAlchemy models (User, Story, StoryNode, EdgeVote, NodeView)
│   ├── db.py           engine / session / Base / get_db dependency
│   ├── llm.py          AI draft + summary (stubbed; Claude when keyed)
│   ├── seed_demo.py    idempotent demo-data seeder (--reset to wipe + reseed)
│   ├── alembic/        migrations
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/      StoriesList, StoryView, StoryMap
│       ├── components/ HistoryNav, SummaryPanel, AddOptionForm, VoteButtons, MicButton
│       └── api.js      fetch wrappers
└── README.md
```

## Notes & limitations (MVP)

- **Auth** — passwords are hashed and sessions use signed, expiring Bearer tokens (`itsdangerous`, 7-day expiry), so a client can't impersonate another user. Set a strong `SECRET_KEY` in the environment for production (the default is a dev placeholder) and serve over HTTPS. Still missing for full hardening: token refresh/rotation + server-side revocation (logout is client-side only), and per-account rate limiting.
- **Moderation + daily generation are stubbed AI** — local logic stands in for Claude; set `ANTHROPIC_API_KEY` to use the real model. The daily generator is triggered manually (admin button / `generate_daily.py`) — wire it to a real scheduler (cron) for production.
- **Speech-to-text** needs the Web Speech API (Chrome/Edge/Safari) + mic permission; the mic button hides itself where unsupported.
- **Deploy:** the production host must serve `index.html` for unmatched routes (SPA fallback) so a hard refresh on a node URL resolves; lock down `CORS(app)` and move secrets out of `.env`.
