"""Create tables and seed the first daily story if the DB is empty. Idempotent —
safe to run on every startup."""
import datetime as dt

from sqlalchemy import select

from db import Base, SessionLocal, engine
from models import Item, Story, StoryNode, User

# Global item catalog (story_id NULL). Idempotent-seeded on startup.
GLOBAL_ITEMS = [
    {"slug": "health_potion", "name": "Health Potion", "kind": "consumable",
     "description": "A swallow of warmth that knits flesh back together.",
     "on_use": {"type": "hp_delta", "amount": 12}},
    {"slug": "lockpick", "name": "Lockpick", "kind": "equipment",
     "description": "A slim hooked pick for stubborn locks.", "on_use": None},
]


def ensure_global_items(session) -> None:
    for spec in GLOBAL_ITEMS:
        exists = session.scalar(
            select(Item).where(Item.slug == spec["slug"], Item.story_id.is_(None))
        )
        if exists is None:
            session.add(Item(story_id=None, **spec))
    session.commit()


def get_or_create_demo_user(session) -> User:
    """Seeded fallback author (used by init_db seeding only)."""
    user = session.scalar(select(User).where(User.username == "demo"))
    if user is None:
        user = User(username="demo")
        session.add(user)
        session.commit()
    return user


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        ensure_global_items(session)
        demo = get_or_create_demo_user(session)
        today = dt.date.today()
        existing = session.scalar(select(Story).where(Story.publish_date == today))
        if existing is not None:
            return

        story = Story(
            title="The Last Lighthouse",
            blurb=(
                "The radio went silent three days ago. Tonight the lamp "
                "still turns, but no one has climbed the stairs in years. "
                "You push open the salt-warped door at the base of the tower..."
            ),
            user_id=demo.id,
            publish_date=today,
        )
        session.add(story)
        session.commit()
        session.refresh(story)

        # Two opening branches off the blurb.
        a = StoryNode(
            story_id=story.id,
            user_id=demo.id,
            edge_prompt="Climb the spiral stairs toward the light",
            content=(
                "Each step groans. Halfway up, a logbook lies open, its last "
                "entry smeared: 'It answers when the lamp turns three times.'"
            ),
        )
        b = StoryNode(
            story_id=story.id,
            user_id=demo.id,
            edge_prompt="Follow the wet footprints down to the cellar",
            content=(
                "The prints are too long to be human. They end at a hatch in "
                "the floor that hums, faintly, like a held breath."
            ),
        )
        session.add_all([a, b])
        session.commit()
