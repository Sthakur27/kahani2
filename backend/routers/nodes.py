"""Node-centric routes: a node + its children, the root→node path, and voting."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import current_user, optional_user
from db import get_db
from models import EdgeVote, StoryNode, User
from schemas import VoteRequest
from serializers import ancestor_chain, node_to_dict, record_view

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("/{node_id}")
def get_node(
    node_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    """A node plus its immediate children (for traversing the tree)."""
    node = db.get(StoryNode, node_id)
    if node is None:
        raise HTTPException(404, "node not found")
    user_id = user.id if user else None
    if user_id is not None:
        record_view(db, node_id, user_id)  # opening a node page = a visit
    children = db.scalars(
        select(StoryNode).where(StoryNode.parent_node_id == node_id)
    ).all()
    data = node_to_dict(db, node, user_id)
    data["children"] = [node_to_dict(db, c) for c in children]
    data["children"].sort(key=lambda n: (-n["score"], n["created_at"] or ""))
    return data


@router.get("/{node_id}/path")
def node_path(node_id: int, db: Session = Depends(get_db)):
    """The chain of nodes from the story root down to (and including) this node.

    Lets the frontend rebuild the traversal from a URL so a refresh stays put.
    """
    node = db.get(StoryNode, node_id)
    if node is None:
        raise HTTPException(404, "node not found")
    chain = [*ancestor_chain(db, node), node]  # root → current
    return [node_to_dict(db, n) for n in chain]


@router.post("/{node_id}/vote")
def vote_node(
    node_id: int,
    body: VoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Set this user's vote on a node. value 1 = up, -1 = down, 0 = clear.

    One vote per user per node (upsert). Returns the node with refreshed
    `score` and the user's `my_vote`.
    """
    value = body.value
    if value not in (-1, 0, 1):
        raise HTTPException(400, "value must be -1, 0, or 1")
    if db.get(StoryNode, node_id) is None:
        raise HTTPException(404, "node not found")
    user_id = user.id
    vote = db.scalar(
        select(EdgeVote).where(
            EdgeVote.story_node_id == node_id, EdgeVote.user_id == user_id
        )
    )
    if value == 0:
        if vote is not None:
            db.delete(vote)
    elif vote is None:
        db.add(EdgeVote(user_id=user_id, story_node_id=node_id, value=value))
    else:
        vote.value = value
    db.commit()
    node = db.get(StoryNode, node_id)
    return node_to_dict(db, node, user_id)
