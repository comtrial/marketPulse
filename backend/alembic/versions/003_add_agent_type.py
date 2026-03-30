"""Add agent_type column to tool_call_traces.

PatternScout 도입 전에 구조를 잡아놓아서,
analyst(기존 오케스트레이터)와 scout(PatternScout)를 구분할 수 있게 한다.
기존 데이터는 NULL → 새 데이터부터 "analyst"로 기록.

Revision ID: 003
Revises: 002
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tool_call_traces",
        sa.Column("agent_type", sa.String(30), nullable=True),
    )
    op.create_index("idx_trace_agent", "tool_call_traces", ["agent_type"])


def downgrade() -> None:
    op.drop_index("idx_trace_agent", table_name="tool_call_traces")
    op.drop_column("tool_call_traces", "agent_type")
