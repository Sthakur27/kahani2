"""Branch economy: keep only a capped set of `active` (in-play) edges per choice
point; extra submissions are `candidate` proposals that can be voted up and
promoted. See docs/rpg-statefulness.md §13.

Rules:
- canonize-on-depth: an active edge whose destination has been built upon
  (has outgoing edges) is protected and cannot be unseated.
- never-delete: a relegated edge becomes a `candidate` again, never removed.
- promotion: fill any free active slots with the top candidates, then unseat the
  weakest *unprotected* active whenever a candidate strictly outscores it.
"""
from sqlalchemy import func, select

from models import Edge, EdgeOutcome, EdgeVote


def _edge_score(db, edge) -> int:
    """An edge's score = net votes across its outcome destination node(s)."""
    dests = select(EdgeOutcome.to_node_id).where(EdgeOutcome.edge_id == edge.id)
    return db.scalar(
        select(func.coalesce(func.sum(EdgeVote.value), 0)).where(
            EdgeVote.story_node_id.in_(dests)
        )
    ) or 0


def _is_protected(db, edge) -> bool:
    """Protected once its destination has descendants (the branch was developed)."""
    dests = select(EdgeOutcome.to_node_id).where(EdgeOutcome.edge_id == edge.id)
    built = db.scalar(
        select(func.count(Edge.id)).where(Edge.from_node_id.in_(dests))
    )
    return (built or 0) > 0


def _point_edges(db, story_id, from_node_id):
    stmt = select(Edge).where(
        Edge.story_id == story_id,
        Edge.status.in_(["active", "candidate"]),
    )
    stmt = stmt.where(
        Edge.from_node_id.is_(None) if from_node_id is None
        else Edge.from_node_id == from_node_id
    )
    return db.scalars(stmt).all()


def promote_choice_point(db, story, from_node_id) -> int:
    """Settle one choice point. Returns the number of status changes made."""
    cap = story.active_edge_cap or 3
    edges = _point_edges(db, story.id, from_node_id)
    cands = [e for e in edges if e.status == "candidate"]
    if not cands:
        return 0
    actives = [e for e in edges if e.status == "active"]
    score = {e.id: _edge_score(db, e) for e in edges}
    cands.sort(key=lambda e: score[e.id], reverse=True)
    changes = 0

    # 1) fill any free active slots with the strongest candidates
    while len(actives) < cap and cands:
        c = cands.pop(0)
        c.status = "active"
        actives.append(c)
        changes += 1

    # 2) unseat the weakest unprotected active when a candidate strictly beats it
    while cands:
        c = cands[0]
        unprotected = [e for e in actives if not _is_protected(db, e)]
        if not unprotected:
            break
        weakest = min(unprotected, key=lambda e: score[e.id])
        if score[c.id] > score[weakest.id]:
            weakest.status = "candidate"
            actives.remove(weakest)
            c.status = "active"
            actives.append(c)
            cands.pop(0)
            changes += 1
        else:
            break

    if changes:
        db.commit()
    return changes


def promote_story(db, story) -> int:
    """Settle every choice point in a story."""
    points = db.scalars(
        select(Edge.from_node_id).where(Edge.story_id == story.id).distinct()
    ).all()
    return sum(promote_choice_point(db, story, p) for p in points)
