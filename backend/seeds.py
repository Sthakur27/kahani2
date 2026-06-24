"""Create tables and seed the first daily story if the DB is empty. Idempotent —
safe to run on every startup."""
import datetime as dt

from sqlalchemy import select

from db import Base, SessionLocal, engine
from models import Story, StoryNode, User


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
