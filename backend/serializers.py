"""Turn ORM objects (+ aggregate columns) into the JSON dicts the API returns.
Kept as plain dicts (not Pydantic response models) so the exact shapes the
frontend depends on are preserved verbatim. Also holds small DB helpers shared
across routers."""
from sqlalchemy import func, select

from models import EdgeVote, NodeView, Story, StoryNode, User


# --------------------------------------------------------------------------- #
# DB helpers
# --------------------------------------------------------------------------- #
def ancestor_chain(session, node: StoryNode) -> list[StoryNode]:
    """Walk parent links upward; return ancestors ordered root → parent."""
    chain = []
    cur = node.parent_node_id
    while cur is not None:
        parent = session.get(StoryNode, cur)
        if parent is None:
            break
        chain.append(parent)
        cur = parent.parent_node_id
    chain.reverse()
    return chain


def record_view(session, node_id: int, user_id: int) -> None:
    """Mark a node as viewed by a user (first view only; one row per user/node)."""
    seen = session.scalar(
        select(NodeView.id).where(
            NodeView.story_node_id == node_id, NodeView.user_id == user_id
        )
    )
    if seen is None:
        session.add(NodeView(story_node_id=node_id, user_id=user_id))
        session.commit()


# --------------------------------------------------------------------------- #
# Serializers
# --------------------------------------------------------------------------- #
def serialize_node(node: StoryNode, score, child_count, my_vote=None, view_count=0) -> dict:
    return {
        "id": node.id,
        "story_id": node.story_id,
        "parent_node_id": node.parent_node_id,
        "user_id": node.user_id,
        "edge_prompt": node.edge_prompt,
        "content": node.content,
        "summary_so_far": node.summary_so_far,
        "author": node.author.username if node.author else None,
        "score": int(score or 0),
        "child_count": int(child_count or 0),
        "view_count": int(view_count or 0),  # distinct viewers
        "my_vote": my_vote,  # this user's vote on the node: 1, -1, or null
        "created_at": node.created_at.isoformat() if node.created_at else None,
    }


def node_to_dict(session, node: StoryNode, user_id=None) -> dict:
    score = session.scalar(
        select(func.coalesce(func.sum(EdgeVote.value), 0)).where(
            EdgeVote.story_node_id == node.id
        )
    )
    child_count = session.scalar(
        select(func.count(StoryNode.id)).where(StoryNode.parent_node_id == node.id)
    )
    view_count = session.scalar(
        select(func.count(NodeView.id)).where(NodeView.story_node_id == node.id)
    )
    my_vote = None
    if user_id is not None:
        my_vote = session.scalar(
            select(EdgeVote.value).where(
                EdgeVote.story_node_id == node.id, EdgeVote.user_id == user_id
            )
        )
    return serialize_node(node, score, child_count, my_vote, view_count)


def story_to_dict(story: Story) -> dict:
    return {
        "id": story.id,
        "title": story.title,
        "blurb": story.blurb,
        "user_id": story.user_id,
        "genre": story.genre,
        "rating": story.rating,
        "publish_date": story.publish_date.isoformat(),
        "created_at": story.created_at.isoformat() if story.created_at else None,
    }


def user_to_dict(user: User) -> dict:
    return {"id": user.id, "username": user.username, "is_admin": bool(user.is_admin)}
