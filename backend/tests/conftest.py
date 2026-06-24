"""Pytest fixtures. Runs against a dedicated Postgres test DB (same dialect as
prod) and forces the local AI stubs (no real Claude in tests)."""
import os

# Must be set BEFORE importing db/main. load_dotenv (override=False) won't clobber
# already-set vars, so this wins over backend/.env.
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg2://storysim_app:storysim_dev_pw@localhost:5432/storysim_test"
)
os.environ["ANTHROPIC_API_KEY"] = ""  # force llm stubs (deterministic, free)
os.environ.setdefault("SECRET_KEY", "test-secret")

import itertools  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import models  # noqa: E402,F401  (register ORM models)
from db import Base, SessionLocal, engine  # noqa: E402
import main  # noqa: E402

_ids = itertools.count(1)


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(main.app) as c:  # lifespan runs init_db (seeds items + a story)
        yield c
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def auth(client):
    """Factory: create a fresh user and return Authorization headers."""
    def _make(username=None, password="pass1234", admin=False):
        username = username or f"u{next(_ids)}"
        r = client.post("/api/auth/signup", json={"username": username, "password": password})
        assert r.status_code == 201, r.text
        token = r.json()["token"]
        if admin:
            with SessionLocal() as s:
                from models import User
                from sqlalchemy import select
                u = s.scalar(select(User).where(User.username == username))
                u.is_admin = True
                s.commit()
        return {"Authorization": f"Bearer {token}"}, username
    return _make


@pytest.fixture
def campaign(client):
    """A fresh campaign story: root choice 'Step forward' (-5 HP) -> node A,
    then A -> ending node B. Returns ids."""
    import datetime as dt
    from storybuilder import add_branch, get_or_create_user
    from models import Story
    with SessionLocal() as s:
        author = get_or_create_user(s, "test_author")
        n = next(_ids)
        story = Story(
            title=f"Test Quest {n}",
            blurb="A test premise. You stand at a threshold.",
            user_id=author.id, genre=f"test{n}", rating="pg",
            mode="campaign", publish_date=dt.date(2020, 1, 1),
        )
        s.add(story)
        s.flush()
        a = add_branch(s, story_id=story.id, from_node_id=None, author_id=author.id,
                       label="Step forward", content="You step into the dark.",
                       effects=[{"type": "hp_delta", "amount": -5}])
        b = add_branch(s, story_id=story.id, from_node_id=a, author_id=author.id,
                       label="Press on", content="The end of the path.", is_ending=True)
        s.commit()
        return {"story_id": story.id, "author_id": author.id, "node_a": a, "node_b": b}

