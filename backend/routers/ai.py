"""AI routes: polish rough notes into a story-path label + blurb."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import llm
from db import get_db
from models import Story, StoryNode
from schemas import DraftRequest, DraftRollRequest

router = APIRouter(prefix="/api/ai", tags=["ai"])
log = logging.getLogger("storysim")


@router.post("/draft")
def ai_draft(body: DraftRequest, db: Session = Depends(get_db)):
    """Polish a few rough bullet points into a story-path label + blurb."""
    if not llm.ai_available():
        raise HTTPException(503, "AI is not configured (set ANTHROPIC_API_KEY)")
    bullets = (body.bullets or "").strip()
    if not bullets:
        raise HTTPException(400, "bullets are required")

    story = db.get(Story, body.story_id) if body.story_id else None
    if story is None:
        raise HTTPException(404, "story not found")
    parent = db.get(StoryNode, body.parent_node_id) if body.parent_node_id else None
    try:
        return llm.draft_node(story, parent, bullets)
    except Exception as exc:  # noqa: BLE001
        log.warning("AI draft failed: %s", exc)
        raise HTTPException(502, "AI draft failed")


@router.post("/draft-roll")
def ai_draft_roll(body: DraftRollRequest, db: Session = Depends(get_db)):
    """Propose a skill-check (roll) edge — a check + outcome passages — from a
    rough idea. The author reviews/edits before creating it."""
    if not llm.ai_available():
        raise HTTPException(503, "AI is not configured (set ANTHROPIC_API_KEY)")
    idea = (body.idea or "").strip()
    if not idea:
        raise HTTPException(400, "describe the action to check")
    story = db.get(Story, body.story_id) if body.story_id else None
    if story is None:
        raise HTTPException(404, "story not found")
    parent = db.get(StoryNode, body.parent_node_id) if body.parent_node_id else None
    try:
        return llm.draft_roll(story, parent, idea)
    except Exception as exc:  # noqa: BLE001
        log.warning("AI roll draft failed: %s", exc)
        raise HTTPException(502, "AI roll draft failed")
