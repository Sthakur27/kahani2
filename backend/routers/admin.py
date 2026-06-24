"""Admin routes: generate today's daily prompts."""
import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import llm
from auth import admin_user
from db import get_db
from models import Story, User
from serializers import story_to_dict

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/generate-daily")
def generate_daily_route(
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    """Admin-only: generate today's prompts — one per genre × rating (pg/mature).
    Skips combos that already exist."""
    day = dt.date.today()
    created = []
    for genre in llm.GENRES:
        for rating in llm.RATINGS:
            if db.scalar(
                select(Story).where(
                    Story.publish_date == day,
                    Story.genre == genre,
                    Story.rating == rating,
                )
            ):
                continue
            p = llm.generate_daily(genre, rating)
            story = Story(
                title=p["title"][:200],
                blurb=p["blurb"],
                user_id=user.id,
                genre=genre,
                rating=rating,
                publish_date=day,
            )
            db.add(story)
            db.commit()
            db.refresh(story)
            created.append(story_to_dict(story))
    return {"date": day.isoformat(), "count": len(created), "created": created}
