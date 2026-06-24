"""CLI: generate today's daily prompts — one Story per genre × rating (pg/mature).

The admin UI button hits POST /api/admin/generate-daily, which runs the same loop;
this is the cron/script entry point. Idempotent: skips combos already present.

    ./venv/bin/python generate_daily.py
"""
import datetime as dt

from sqlalchemy import select

from db import SessionLocal
from models import Story, User
import llm


def main():
    day = dt.date.today()
    with SessionLocal() as session:
        admin = session.scalar(select(User).where(User.is_admin.is_(True)))
        created = 0
        for genre in llm.GENRES:
            for rating in llm.RATINGS:
                exists = session.scalar(
                    select(Story).where(
                        Story.publish_date == day,
                        Story.genre == genre,
                        Story.rating == rating,
                    )
                )
                if exists:
                    continue
                p = llm.generate_daily(genre, rating)
                session.add(
                    Story(
                        title=p["title"][:200],
                        blurb=p["blurb"],
                        user_id=admin.id if admin else None,
                        genre=genre,
                        rating=rating,
                        publish_date=day,
                    )
                )
                session.commit()
                created += 1
        print(f"Generated {created} new prompt(s) for {day} (genres × ratings).")


if __name__ == "__main__":
    main()
