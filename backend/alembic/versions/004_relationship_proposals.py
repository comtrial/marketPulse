"""Add relationship_proposals and market_insights tables.

PatternScout가 통계적 패턴을 제안하고, 사람이 승인/거부하는 구조.
승인된 관계는 Neo4j DISCOVERED_LINK로 편입.

Revision ID: 004
Revises: 003
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "relationship_proposals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_concept", sa.String(100), nullable=False),
        sa.Column("target_concept", sa.String(100), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("evidence", postgresql.JSONB, nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), server_default="'proposed'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text),
    )

    op.create_table(
        "market_insights",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("country", sa.String(5), nullable=False),
        sa.Column("product_type", sa.String(30), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("evidence", postgresql.JSONB, nullable=False),
        sa.Column("related_insights", postgresql.ARRAY(sa.Integer)),
        sa.Column("trace_id", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("market_insights")
    op.drop_table("relationship_proposals")
