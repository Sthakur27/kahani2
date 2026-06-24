"""Story routes: the daily prompt, listing/paging, a single story, the node
list at a level, the shadow-tree, and node creation."""
import datetime as dt
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import llm
from auth import current_user, optional_user
from db import get_db
from models import EdgeVote, NodeView, Story, StoryNode, User
from schemas import NodeCreate
from serializers import (
    ancestor_chain,
    node_to_dict,
    serialize_node,
    story_to_dict,
)

router = APIRouter(prefix="/api", tags=["stories"])
log = logging.getLogger("storysim")


@router.get("/stories/today")
def story_today(db: Session = Depends(get_db)):
    """The most recent story on or before today (the current daily prompt)."""
    story = db.scalar(
        select(Story)
        .where(Story.publish_date <= dt.date.today())
        .order_by(Story.publish_date.desc())
        .limit(1)
    )
    if story is None:
        raise HTTPException(404, "no story available")
    return story_to_dict(story)


@router.get("/stories")
def list_stories(
    response: Response,
    rating: str | None = None,
    genre: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """All stories, newest first. Optional rating/genre filters, plus limit/offset
    paging (total in the X-Total-Count header)."""
    limit = max(1, min(limit, 100))
    base = select(Story)
    count_stmt = select(func.count(Story.id))
    if rating:
        base = base.where(Story.rating == rating)
        count_stmt = count_stmt.where(Story.rating == rating)
    if genre:
        base = base.where(Story.genre == genre)
        count_stmt = count_stmt.where(Story.genre == genre)
    total = db.scalar(count_stmt) or 0
    stories = db.scalars(
        base.order_by(Story.publish_date.desc()).limit(limit).offset(offset)
    ).all()
    response.headers["X-Total-Count"] = str(total)
    return [story_to_dict(s) for s in stories]


@router.get("/stories/{story_id}")
def get_story(story_id: int, db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "story not found")
    return story_to_dict(story)


@router.get("/stories/{story_id}/nodes")
def list_nodes(
    story_id: int,
    response: Response,
    parent_id: int | None = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Children of a node within a story. Omit parent_id to get top-level nodes.

    Vote aggregates come from a single LEFT JOIN against a grouped SUM over
    edge_votes (no per-node query); popularity ranking — highest score first,
    then oldest — is done in SQL.
    """
    limit = max(1, min(limit, 100))
    if db.get(Story, story_id) is None:
        raise HTTPException(404, "story not found")

    # total at this level (for "load more")
    total_stmt = select(func.count(StoryNode.id)).where(
        StoryNode.story_id == story_id
    )
    total_stmt = total_stmt.where(
        StoryNode.parent_node_id.is_(None)
        if parent_id is None
        else StoryNode.parent_node_id == parent_id
    )
    total = db.scalar(total_stmt) or 0

    score_sq = (
        select(
            EdgeVote.story_node_id.label("nid"),
            func.coalesce(func.sum(EdgeVote.value), 0).label("score"),
        )
        .group_by(EdgeVote.story_node_id)
        .subquery()
    )
    child_sq = (
        select(
            StoryNode.parent_node_id.label("pid"),
            func.count(StoryNode.id).label("cnt"),
        )
        .group_by(StoryNode.parent_node_id)
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
    cnt = func.coalesce(child_sq.c.cnt, 0)
    views = func.coalesce(views_sq.c.views, 0)

    stmt = (
        select(StoryNode, score, cnt, views)
        .outerjoin(score_sq, score_sq.c.nid == StoryNode.id)
        .outerjoin(child_sq, child_sq.c.pid == StoryNode.id)
        .outerjoin(views_sq, views_sq.c.nid == StoryNode.id)
        .where(StoryNode.story_id == story_id)
    )
    if parent_id is None:
        stmt = stmt.where(StoryNode.parent_node_id.is_(None))
    else:
        stmt = stmt.where(StoryNode.parent_node_id == parent_id)
    stmt = stmt.order_by(score.desc(), StoryNode.created_at.asc())
    stmt = stmt.limit(limit).offset(offset)

    rows = db.execute(stmt).all()
    response.headers["X-Total-Count"] = str(total)
    return [serialize_node(n, s, c, view_count=v) for (n, s, c, v) in rows]


@router.get("/stories/{story_id}/tree")
def story_tree(
    story_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    """The whole node graph for a story (for the "shadow tree" map).

    Each node carries `score`, `view_count`, and `visited` (whether the acting
    user has opened it). `content` is included only for visited nodes so the map
    tooltips can preview them without leaking unexplored ("shadow") paths.
    """
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "story not found")
    user_id = user.id if user else None  # anonymous → nothing visited

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
    visited_sq = (
        select(NodeView.story_node_id.label("nid"))
        .where(NodeView.user_id == user_id)
        .subquery()
    )
    score = func.coalesce(score_sq.c.score, 0)
    views = func.coalesce(views_sq.c.views, 0)
    visited = visited_sq.c.nid.isnot(None)

    stmt = (
        select(StoryNode, score, views, visited)
        .outerjoin(score_sq, score_sq.c.nid == StoryNode.id)
        .outerjoin(views_sq, views_sq.c.nid == StoryNode.id)
        .outerjoin(visited_sq, visited_sq.c.nid == StoryNode.id)
        .where(StoryNode.story_id == story_id)
        .order_by(StoryNode.created_at.asc())
    )
    rows = db.execute(stmt).all()
    nodes = [
        {
            "id": n.id,
            "parent_node_id": n.parent_node_id,
            "edge_prompt": n.edge_prompt,
            "content": n.content if vis else None,
            "author": n.author.username if n.author else None,
            "score": int(s or 0),
            "view_count": int(v or 0),
            "visited": bool(vis),
        }
        for (n, s, v, vis) in rows
    ]
    return {"story": story_to_dict(story), "nodes": nodes}


@router.post("/stories/{story_id}/nodes", status_code=201)
def create_node(
    story_id: int,
    body: NodeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Create a node under a story. parent_node_id is optional (NULL = top-level)."""
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(400, "content is required")
    parent_node_id = body.parent_node_id
    edge_prompt = (body.edge_prompt or "").strip() or None

    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "story not found")
    if parent_node_id is not None:
        parent = db.get(StoryNode, parent_node_id)
        if parent is None or parent.story_id != story_id:
            raise HTTPException(400, "invalid parent_node_id")

    # AI moderation: screen the submission against the story's rating.
    verdict = llm.moderate_text(f"{edge_prompt or ''}\n{content}", story.rating)
    if not verdict.get("allowed"):
        raise HTTPException(
            422,
            detail={
                "error": verdict.get("reason") or "Content not allowed",
                "moderation": True,
            },
        )

    node = StoryNode(
        story_id=story_id,
        parent_node_id=parent_node_id,
        user_id=user.id,
        edge_prompt=edge_prompt,
        content=content,
    )
    db.add(node)
    db.commit()
    db.refresh(node)

    # Synchronously generate the "story so far" recap (MVP). Never fail the
    # create if the LLM is unavailable or errors — just leave it NULL.
    if llm.ai_available():
        try:
            ancestors = ancestor_chain(db, node)
            node.summary_so_far = llm.summarize_path(story, ancestors, node)
            db.commit()
            db.refresh(node)
        except Exception as exc:  # noqa: BLE001
            log.warning("summary generation failed: %s", exc)

    return node_to_dict(db, node)
