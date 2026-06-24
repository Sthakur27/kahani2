"""add node_views

Revision ID: 984c13a2e858
Revises: ec4c5e5c11bf
Create Date: 2026-06-22 19:57:51.426633

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '984c13a2e858'
down_revision: Union[str, Sequence[str], None] = 'ec4c5e5c11bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create node_views (skip if create_all already made it on a fresh DB)."""
    bind = op.get_bind()
    if sa.inspect(bind).has_table("node_views"):
        return
    op.create_table(
        "node_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("story_node_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["story_node_id"], ["story_nodes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "story_node_id", name="uq_user_node_view"),
    )
    op.create_index("ix_node_views_node", "node_views", ["story_node_id"])
    op.create_index("ix_node_views_user", "node_views", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_node_views_user", table_name="node_views")
    op.drop_index("ix_node_views_node", table_name="node_views")
    op.drop_table("node_views")
