from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    # Quick-and-dirty auth: nullable so the seeded demo/community users (which
    # predate auth) still work. Real users get a hash.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(server_default=text("false"), default=False)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    blurb: Mapped[str] = mapped_column(Text)
    # Author of the daily prompt; nullable so a story can be system-generated.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    genre: Mapped[str] = mapped_column(String(40), server_default="general")
    rating: Mapped[str] = mapped_column(String(10), server_default="pg")  # pg | mature
    # story = daily light branching (today); campaign = RPG (stats/HP/dice/items).
    mode: Mapped[str] = mapped_column(String(20), server_default="story")
    # save_anywhere | checkpoint | permadeath — how a run handles save/restore/death.
    death_policy: Mapped[str] = mapped_column(String(20), server_default="save_anywhere")
    # curated (per-story cast) | classes (generic W/R/M) | fixed (single pregen).
    character_mode: Mapped[str] = mapped_column(String(20), server_default="classes")
    # Branch economy: max in-play (active) edges per choice point.
    active_edge_cap: Mapped[int] = mapped_column(server_default="3", default=3)
    publish_date: Mapped[dt.date] = mapped_column()
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    nodes: Mapped[list["StoryNode"]] = relationship(back_populates="story")

    # One story per (day, genre, rating): a PG and a mature version of each genre per day.
    __table_args__ = (
        UniqueConstraint(
            "publish_date", "genre", "rating", name="uq_story_day_genre_rating"
        ),
    )


class StoryNode(Base):
    __tablename__ = "story_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"))
    # NULL parent => a top-level continuation of the story's blurb.
    parent_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # The "choice" label that leads into this node (the edge). NULL for top-level.
    edge_prompt: Mapped[str | None] = mapped_column(String(280), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    # LLM-generated recap of the story from the root down to and including this
    # node. NULL until generated (populated on node creation — see next task).
    summary_so_far: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Arrival behavior (Slay-the-Spire-style): story|combat|rest|treasure|boss.
    kind: Mapped[str] = mapped_column(String(20), server_default="story")
    # A deliberate narrative ending (vs an undeveloped leaf no one has continued).
    is_ending: Mapped[bool] = mapped_column(server_default=text("false"), default=False)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    story: Mapped["Story"] = relationship(back_populates="nodes")
    author: Mapped["User"] = relationship()
    children: Mapped[list["StoryNode"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped["StoryNode | None"] = relationship(
        back_populates="children", remote_side="StoryNode.id"
    )

    __table_args__ = (
        Index("ix_story_nodes_story_parent", "story_id", "parent_node_id"),
    )


class EdgeVote(Base):
    __tablename__ = "edge_votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    story_node_id: Mapped[int] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="CASCADE")
    )
    # +1 upvote for MVP; leaves room for -1 downvotes later.
    value: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "story_node_id", name="uq_user_node_vote"),
        CheckConstraint("value IN (-1, 1)", name="ck_edge_vote_value"),
    )


class NodeView(Base):
    """One row the first time a user opens a node page. Powers the node's view
    count (distinct viewers) and the per-user 'visited' set for the shadow tree."""

    __tablename__ = "node_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    story_node_id: Mapped[int] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="CASCADE")
    )
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "story_node_id", name="uq_user_node_view"),
        Index("ix_node_views_node", "story_node_id"),
        Index("ix_node_views_user", "user_id"),
    )


# --------------------------------------------------------------------------- #
# RPG: rules layer (shared, authored) — see docs/rpg-statefulness.md
# --------------------------------------------------------------------------- #
class Edge(Base):
    """A choice/action offered at a node (or off the story blurb when from_node_id
    is NULL). kind='plain' has a single linear outcome; kind='roll' is a skill
    check resolving to 2-4 outcome bands. Supersedes the legacy
    parent_node_id/edge_prompt linkage (kept as a derived cache for now)."""

    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"))
    from_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="CASCADE"), nullable=True
    )
    label: Mapped[str | None] = mapped_column(String(280), nullable=True)
    kind: Mapped[str] = mapped_column(String(10), server_default="plain")  # plain | roll
    # active = in-play (capped per choice point) | candidate = votable proposal
    # | retired = relegated. Only active edges are traversable.
    status: Mapped[str] = mapped_column(String(12), server_default="active")
    check_stat: Mapped[str | None] = mapped_column(String(12), nullable=True)
    check_dc: Mapped[int | None] = mapped_column(nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    outcomes: Mapped[list["EdgeOutcome"]] = relationship(
        back_populates="edge", cascade="all, delete-orphan"
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_edges_from_node", "from_node_id"),
        Index("ix_edges_story", "story_id"),
    )


class EdgeOutcome(Base):
    """Where an edge leads, per result band. plain edge -> one 'plain' outcome;
    roll edge -> 'fail'+'success' required, 'crit_fail'/'crit_success' optional."""

    __tablename__ = "edge_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    edge_id: Mapped[int] = mapped_column(ForeignKey("edges.id", ondelete="CASCADE"))
    band: Mapped[str] = mapped_column(String(16), server_default="plain")
    to_node_id: Mapped[int] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="CASCADE")
    )

    edge: Mapped["Edge"] = relationship(back_populates="outcomes")
    effects: Mapped[list["Effect"]] = relationship(
        back_populates="outcome", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("edge_id", "band", name="uq_outcome_edge_band"),
    )


class Effect(Base):
    """A state mutation applied when an outcome fires. Interpreted by `type`, so
    new mechanics are new type values — not schema changes."""

    __tablename__ = "effects"

    id: Mapped[int] = mapped_column(primary_key=True)
    outcome_id: Mapped[int] = mapped_column(
        ForeignKey("edge_outcomes.id", ondelete="CASCADE")
    )
    # hp_delta|max_hp_delta|stat_delta|grant_item|consume_item|set_flag|heal_full|end_run
    type: Mapped[str] = mapped_column(String(24))
    amount: Mapped[int | None] = mapped_column(nullable=True)
    stat: Mapped[str | None] = mapped_column(String(12), nullable=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    count: Mapped[int | None] = mapped_column(nullable=True)
    flag_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    flag_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    outcome: Mapped["EdgeOutcome"] = relationship(back_populates="effects")


class Item(Base):
    """Item catalog (shared). story_id NULL = global catalog."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int | None] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(16), server_default="consumable")
    on_use: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Requirement(Base):
    """A gate to even attempt an edge: need an item / minimum stat / flag."""

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    edge_id: Mapped[int] = mapped_column(ForeignKey("edges.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(12))  # item | stat_min | flag
    key: Mapped[str] = mapped_column(String(64))  # item slug / stat key / flag key
    amount: Mapped[int | None] = mapped_column(nullable=True)
    # For item requirements: whether taking the edge consumes the item.
    consume: Mapped[bool] = mapped_column(server_default=text("false"), default=False)


# --------------------------------------------------------------------------- #
# RPG: player state (private, per playthrough)
# --------------------------------------------------------------------------- #
class Run(Base):
    """One playthrough of a story by a user. Party-level container; per-character
    state lives in RunCharacter (party-of-1 in the MVP)."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"))
    current_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(12), server_default="active")
    party_gold: Mapped[int] = mapped_column(server_default="0", default=0)
    started_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    characters: Mapped[list["RunCharacter"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_runs_user_story", "user_id", "story_id"),)


class RunCharacter(Base):
    """A character in a run. A solo run is a party of one of these."""

    __tablename__ = "run_characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(60), server_default="Adventurer")
    char_class: Mapped[str | None] = mapped_column(String(24), nullable=True)
    strength: Mapped[int] = mapped_column(server_default="10", default=10)
    dexterity: Mapped[int] = mapped_column(server_default="10", default=10)
    constitution: Mapped[int] = mapped_column(server_default="10", default=10)
    intelligence: Mapped[int] = mapped_column(server_default="10", default=10)
    wisdom: Mapped[int] = mapped_column(server_default="10", default=10)
    charisma: Mapped[int] = mapped_column(server_default="10", default=10)
    hp: Mapped[int] = mapped_column(server_default="20", default=20)
    max_hp: Mapped[int] = mapped_column(server_default="20", default=20)
    status: Mapped[str] = mapped_column(String(8), server_default="alive")  # alive|down|dead
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    run: Mapped["Run"] = relationship(back_populates="characters")


class RunStep(Base):
    """Append-only log of a run, with a full state snapshot per step — the basis
    for save-anywhere / checkpoint / permadeath as a *policy*, not a schema fork."""

    __tablename__ = "run_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column()
    edge_id: Mapped[int | None] = mapped_column(
        ForeignKey("edges.id", ondelete="SET NULL"), nullable=True
    )
    arrived_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="SET NULL"), nullable=True
    )
    roll_d20: Mapped[int | None] = mapped_column(nullable=True)
    modifier: Mapped[int | None] = mapped_column(nullable=True)
    dc: Mapped[int | None] = mapped_column(nullable=True)
    band_result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    effects_applied: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    undone: Mapped[bool] = mapped_column(server_default=text("false"), default=False)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_run_steps_run_seq", "run_id", "seq"),)


class RunInventory(Base):
    """Live inventory for a run. character_id NULL = shared party stash."""

    __tablename__ = "run_inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    character_id: Mapped[int | None] = mapped_column(
        ForeignKey("run_characters.id", ondelete="CASCADE"), nullable=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    count: Mapped[int] = mapped_column(server_default="1", default=1)


class RunFlag(Base):
    """Arbitrary story flags set during a run ("has_key", "spared_the_ghost")."""

    __tablename__ = "run_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("run_id", "key", name="uq_run_flag_key"),)


class CharacterOption(Base):
    """A selectable character for a story's run (curated/AI-generated, authorable
    later). Themed flavor (name/blurb/icon) over a shared mechanical `archetype`
    (a key into game.CLASS_PRESETS)."""

    __tablename__ = "character_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    blurb: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(8), nullable=True)
    archetype: Mapped[str] = mapped_column(String(24), server_default="warrior")
    sort_order: Mapped[int] = mapped_column(server_default="0", default=0)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
