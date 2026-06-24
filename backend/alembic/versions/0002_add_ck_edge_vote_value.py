"""add_ck_edge_vote_value

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-21 14:49:39.189366

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CHECK constraint to edge_votes.value — only -1 or 1 allowed."""
    op.create_check_constraint(
        "ck_edge_vote_value",
        "edge_votes",
        "value IN (-1, 1)",
    )


def downgrade() -> None:
    """Remove the CHECK constraint from edge_votes.value."""
    op.drop_constraint("ck_edge_vote_value", "edge_votes", type_="check")
