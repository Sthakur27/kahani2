"""Turn ORM objects (+ aggregate columns) into the JSON dicts the API returns.
Kept as plain dicts (not Pydantic response models) so the exact shapes the
frontend depends on are preserved verbatim. Also holds small DB helpers shared
across routers."""
from sqlalchemy import func, select

from models import Edge, EdgeOutcome, EdgeVote, NodeView, Story, StoryNode, User


# --------------------------------------------------------------------------- #
# Edge-based structure helpers (the edge model is the source of truth; the
# legacy parent_node_id/edge_prompt columns are kept in sync as a cache).
# --------------------------------------------------------------------------- #
def inbound_edge(session, node_id: int) -> Edge | None:
    """The edge whose outcome leads into this node (each node has ≤1)."""
    return session.scalar(
        select(Edge)
        .join(EdgeOutcome, EdgeOutcome.edge_id == Edge.id)
        .where(EdgeOutcome.to_node_id == node_id)
        .limit(1)
    )


def child_nodes_select(story_id: int, from_node_id: int | None):
    """SELECT over StoryNode for the children reachable from a node via edges
    (or off the story blurb when from_node_id is None)."""
    stmt = (
        select(StoryNode)
        .join(EdgeOutcome, EdgeOutcome.to_node_id == StoryNode.id)
        .join(Edge, Edge.id == EdgeOutcome.edge_id)
        .where(Edge.story_id == story_id)
    )
    return stmt.where(
        Edge.from_node_id.is_(None)
        if from_node_id is None
        else Edge.from_node_id == from_node_id
    )


def ancestor_chain(session, node: StoryNode) -> list[StoryNode]:
    """Walk inbound edges upward; return ancestors ordered root → parent."""
    chain = []
    cur = node
    seen = set()
    while True:
        edge = inbound_edge(session, cur.id)
        if edge is None or edge.from_node_id is None or edge.from_node_id in seen:
            break
        parent = session.get(StoryNode, edge.from_node_id)
        if parent is None:
            break
        seen.add(parent.id)
        chain.append(parent)
        cur = parent
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
