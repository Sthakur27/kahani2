"""Authoring helpers for building story content directly in the DB: a passage
(StoryNode) reachable by a new plain Edge + EdgeOutcome, with optional Effects.
Keeps the legacy parent_node_id/edge_prompt cache in sync. Used by seed scripts
and content-building agents.

Example:
    from dotenv import load_dotenv; load_dotenv()
    from db import SessionLocal
    from storybuilder import add_branch
    with SessionLocal() as s:
        n1 = add_branch(s, story_id=42, from_node_id=100, author_id=3,
                        label="Wade into the flooded vault",
                        content="The water is black and waist-deep ...",
                        kind="story", effects=[{"type": "hp_delta", "amount": -4}])
        n2 = add_branch(s, story_id=42, from_node_id=n1, author_id=3,
                        label="Rest on the dry altar step",
                        content="You catch your breath ...",
                        kind="rest", effects=[{"type": "heal_full"}])
        s.commit()
"""
from sqlalchemy import select

from models import Edge, EdgeOutcome, Effect, StoryNode, User


def get_or_create_user(session, username: str) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username)
        session.add(user)
        session.flush()
    return user


def add_branch(
    session,
    *,
    story_id: int,
    from_node_id: int | None,
    author_id: int,
    label: str,
    content: str,
    kind: str = "story",
    summary: str | None = None,
    effects: list[dict] | None = None,
    is_ending: bool = False,
) -> int:
    """Create a passage reachable by a new plain edge from `from_node_id`
    (None = a top-level choice off the story blurb). `effects` is a list of dicts
    like {"type": "hp_delta", "amount": -3} applied when the edge is taken
    (types: hp_delta, max_hp_delta, stat_delta(+stat), heal_full, set_flag
    (+flag_key/flag_value), end_run). Returns the new node id."""
    node = StoryNode(
        story_id=story_id,
        parent_node_id=from_node_id,  # legacy cache, kept in sync
        user_id=author_id,
        edge_prompt=label,            # legacy cache (= edge.label)
        content=content,
        kind=kind,
        is_ending=is_ending,
        summary_so_far=summary,
    )
    session.add(node)
    session.flush()

    edge = Edge(
        story_id=story_id,
        from_node_id=from_node_id,
        label=label,
        kind="plain",
        created_by=author_id,
    )
    session.add(edge)
    session.flush()

    outcome = EdgeOutcome(edge_id=edge.id, band="plain", to_node_id=node.id)
    session.add(outcome)
    session.flush()

    for ef in effects or []:
        _add_effect(session, outcome.id, ef)

    return node.id


def _add_effect(session, outcome_id: int, ef: dict) -> None:
    session.add(Effect(
        outcome_id=outcome_id,
        type=ef["type"],
        amount=ef.get("amount"),
        stat=ef.get("stat"),
        flag_key=ef.get("flag_key"),
        flag_value=ef.get("flag_value"),
    ))


def add_roll(
    session,
    *,
    story_id: int,
    from_node_id: int | None,
    author_id: int,
    label: str,
    check_stat: str,
    check_dc: int,
    outcomes: dict,
    status: str = "active",
) -> tuple[int, dict]:
    """Create a roll edge (a skill check) from `from_node_id` with up to 4 outcome
    bands. `outcomes` maps band -> {content, kind?, label?, effects?}; `fail` and
    `success` are required, `crit_fail`/`crit_success` optional. Each band becomes
    its own destination passage. Returns (edge_id, {band: node_id})."""
    for required in ("fail", "success"):
        if required not in outcomes:
            raise ValueError(f"roll edge needs a '{required}' outcome")

    edge = Edge(
        story_id=story_id,
        from_node_id=from_node_id,
        label=label,
        kind="roll",
        check_stat=check_stat,
        check_dc=check_dc,
        status=status,
        created_by=author_id,
    )
    session.add(edge)
    session.flush()

    ids = {}
    for band, spec in outcomes.items():
        node = StoryNode(
            story_id=story_id,
            parent_node_id=from_node_id,
            user_id=author_id,
            edge_prompt=spec.get("label", label),
            content=spec["content"],
            kind=spec.get("kind", "story"),
            is_ending=spec.get("is_ending", False),
        )
        session.add(node)
        session.flush()
        oc = EdgeOutcome(edge_id=edge.id, band=band, to_node_id=node.id)
        session.add(oc)
        session.flush()
        for ef in spec.get("effects", []):
            _add_effect(session, oc.id, ef)
        ids[band] = node.id

    return edge.id, ids
