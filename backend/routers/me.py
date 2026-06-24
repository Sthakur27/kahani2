"""Per-user history: the nodes you've read, the branches you've voted on, and
the nodes you've written. All require auth and return newest-first."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import current_user
from db import get_db
from models import EdgeVote, NodeView, Story, StoryNode, User

router = APIRouter(prefix="/api/me", tags=["me"])

MAX = 100  # cap each history list (no paging for now)


def _score_subquery():
    return (
        select(
            EdgeVote.story_node_id.label("nid"),
            func.coalesce(func.sum(EdgeVote.value), 0).label("score"),
        )
        .group_by(EdgeVote.story_node_id)
        .subquery()
    )


def _views_subquery():
    return (
        select(
            NodeView.story_node_id.label("nid"),
            func.count(NodeView.id).label("views"),
        )
        .group_by(NodeView.story_node_id)
        .subquery()
    )


def _node_base(n: StoryNode, title: str, score, views) -> dict:
    return {
        "node_id": n.id,
        "story_id": n.story_id,
        "story_title": title,
        "edge_prompt": n.edge_prompt,
        "content": n.content,
        "author": n.author.username if n.author else None,
        "score": int(score or 0),
        "view_count": int(views or 0),
    }


@router.get("/views")
def my_views(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Nodes I've opened, most recently viewed first."""
    score_sq, views_sq = _score_subquery(), _views_subquery()
    score = func.coalesce(score_sq.c.score, 0)
    views = func.coalesce(views_sq.c.views, 0)
    stmt = (
        select(StoryNode, Story.title, NodeView.created_at, score, views)
        .join(NodeView, NodeView.story_node_id == StoryNode.id)
        .join(Story, Story.id == StoryNode.story_id)
        .outerjoin(score_sq, score_sq.c.nid == StoryNode.id)
        .outerjoin(views_sq, views_sq.c.nid == StoryNode.id)
        .where(NodeView.user_id == user.id)
        .order_by(NodeView.created_at.desc())
        .limit(MAX)
    )
    return [
        {**_node_base(n, title, s, v), "viewed_at": viewed.isoformat() if viewed else None}
        for (n, title, viewed, s, v) in db.execute(stmt).all()
    ]


@router.get("/votes")
def my_votes(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Branches I've voted on (up or down), most recent first."""
    score_sq, views_sq = _score_subquery(), _views_subquery()
    score = func.coalesce(score_sq.c.score, 0)
    views = func.coalesce(views_sq.c.views, 0)
    stmt = (
        select(StoryNode, Story.title, EdgeVote.value, EdgeVote.created_at, score, views)
        .join(EdgeVote, EdgeVote.story_node_id == StoryNode.id)
        .join(Story, Story.id == StoryNode.story_id)
        .outerjoin(score_sq, score_sq.c.nid == StoryNode.id)
        .outerjoin(views_sq, views_sq.c.nid == StoryNode.id)
        .where(EdgeVote.user_id == user.id)
        .order_by(EdgeVote.created_at.desc())
        .limit(MAX)
    )
    return [
        {
            **_node_base(n, title, s, v),
            "value": int(value),
            "voted_at": voted.isoformat() if voted else None,
        }
        for (n, title, value, voted, s, v) in db.execute(stmt).all()
    ]


@router.get("/nodes")
def my_nodes(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Nodes I've written, newest first."""
    score_sq, views_sq = _score_subquery(), _views_subquery()
    child_sq = (
        select(
            StoryNode.parent_node_id.label("pid"),
            func.count(StoryNode.id).label("cnt"),
        )
        .group_by(StoryNode.parent_node_id)
        .subquery()
    )
    score = func.coalesce(score_sq.c.score, 0)
    views = func.coalesce(views_sq.c.views, 0)
    cnt = func.coalesce(child_sq.c.cnt, 0)
    stmt = (
        select(StoryNode, Story.title, score, views, cnt)
        .join(Story, Story.id == StoryNode.story_id)
        .outerjoin(score_sq, score_sq.c.nid == StoryNode.id)
        .outerjoin(views_sq, views_sq.c.nid == StoryNode.id)
        .outerjoin(child_sq, child_sq.c.pid == StoryNode.id)
        .where(StoryNode.user_id == user.id)
        .order_by(StoryNode.created_at.desc())
        .limit(MAX)
    )
    return [
        {
            **_node_base(n, title, s, v),
            "child_count": int(c or 0),
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for (n, title, s, v, c) in db.execute(stmt).all()
    ]
