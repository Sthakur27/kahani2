from __future__ import annotations

import datetime as dt

from sqlalchemy import (
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
