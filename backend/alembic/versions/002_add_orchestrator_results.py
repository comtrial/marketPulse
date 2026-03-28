"""Add orchestrator_results table for full result replay

Revision ID: 002
Revises: 001
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orchestrator_results",
        sa.Column("trace_id", sa.String(36), primary_key=True),
        sa.Column("user_query", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("steps", postgresql.JSONB, nullable=False),
        sa.Column("total_steps", sa.Integer, nullable=False),
        sa.Column(
            "total_input_tokens", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "total_output_tokens", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "total_cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_orch_result_created",
        "orchestrator_results",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_orch_result_created", table_name="orchestrator_results")
    op.drop_table("orchestrator_results")
