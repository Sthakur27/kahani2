"""Leaderboard: top story branches across ALL stories."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import EdgeVote, NodeView, Story, StoryNode

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard")
def leaderboard(limit: int = 20, db: Session = Depends(get_db)):
    """Top branches ranked by net vote score, then distinct viewers, then newest.
    Aggregate score via a grouped SUM subquery, views via a grouped COUNT
    subquery, joined to Story for the title. All nodes included (score 0 too)."""
    limit = max(1, min(limit, 50))
    score_sq = (
        select(
            EdgeVote.story_node_id.label("nid"),
            func.coalesce(func.sum(EdgeVote.value), 0).label("score"),
        )
        .group_by(EdgeVote.story_node_id)
        .subquery()
    )
    views_sq = (
        select(
            NodeView.story_node_id.label("nid"),
            func.count(NodeView.id).label("views"),
        )
        .group_by(NodeView.story_node_id)
        .subquery()
    )
    score = func.coalesce(score_sq.c.score, 0)
    views = func.coalesce(views_sq.c.views, 0)

    stmt = (
        select(StoryNode, Story.title, score, views)
        .join(Story, Story.id == StoryNode.story_id)
        .outerjoin(score_sq, score_sq.c.nid == StoryNode.id)
        .outerjoin(views_sq, views_sq.c.nid == StoryNode.id)
        .order_by(score.desc(), views.desc(), StoryNode.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "node_id": n.id,
            "story_id": n.story_id,
            "story_title": title,
            "edge_prompt": n.edge_prompt,
            "content": n.content,
            "author": n.author.username if n.author else None,
            "score": int(s or 0),
            "view_count": int(v or 0),
        }
        for (n, title, s, v) in rows
    ]
