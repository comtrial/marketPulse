"""Initial schema — orders, extractions, gold_examples, traces, emerging_attributes

Revision ID: 001
Revises: None
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── orders_cafe24 ──
    op.create_table(
        "orders_cafe24",
        sa.Column("order_id", sa.String(20), primary_key=True),
        sa.Column("order_date", sa.Date, nullable=False),
        sa.Column("destination_country", sa.String(5), nullable=False),
        sa.Column("brand", sa.String(50), nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price_usd", sa.Numeric(8, 2)),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "destination_country IN ('KR','JP','SG')", name="chk_cafe24_country"
        ),
        sa.CheckConstraint(
            "product_type IN ('sunscreen','toner','serum','cream','lip')",
            name="chk_cafe24_type",
        ),
    )
    op.create_index("idx_cafe24_country_date", "orders_cafe24", ["destination_country", "order_date"])
    op.create_index("idx_cafe24_type", "orders_cafe24", ["product_type"])

    # ── orders_qoo10 ──
    op.create_table(
        "orders_qoo10",
        sa.Column("order_id", sa.String(20), primary_key=True),
        sa.Column("order_date", sa.Date, nullable=False),
        sa.Column("destination_country", sa.String(5), nullable=False),
        sa.Column("brand", sa.String(50), nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price_usd", sa.Numeric(8, 2)),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "destination_country IN ('JP','SG')", name="chk_qoo10_country"
        ),
        sa.CheckConstraint(
            "product_type IN ('sunscreen','toner','serum','cream','lip')",
            name="chk_qoo10_type",
        ),
    )
    op.create_index("idx_qoo10_country_date", "orders_qoo10", ["destination_country", "order_date"])
    op.create_index("idx_qoo10_type", "orders_qoo10", ["product_type"])

    # ── orders_shopee ──
    op.create_table(
        "orders_shopee",
        sa.Column("order_id", sa.String(20), primary_key=True),
        sa.Column("order_date", sa.Date, nullable=False),
        sa.Column("destination_country", sa.String(5), nullable=False),
        sa.Column("brand", sa.String(50), nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price_usd", sa.Numeric(8, 2)),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "destination_country IN ('SG')", name="chk_shopee_country"
        ),
        sa.CheckConstraint(
            "product_type IN ('sunscreen','toner','serum','cream','lip')",
            name="chk_shopee_type",
        ),
    )
    op.create_index("idx_shopee_date", "orders_shopee", ["order_date"])
    op.create_index("idx_shopee_type", "orders_shopee", ["product_type"])

    # ── orders_unified view ──
    op.execute("""
        CREATE VIEW orders_unified AS
        SELECT order_id, order_date, 'cafe24' AS platform, destination_country,
               brand, product_name, product_type, quantity, unit_price_usd, collected_at
        FROM orders_cafe24
        UNION ALL
        SELECT order_id, order_date, 'qoo10' AS platform, destination_country,
               brand, product_name, product_type, quantity, unit_price_usd, collected_at
        FROM orders_qoo10
        UNION ALL
        SELECT order_id, order_date, 'shopee' AS platform, destination_country,
               brand, product_name, product_type, quantity, unit_price_usd, collected_at
        FROM orders_shopee
    """)

    # ── extractions ──
    op.create_table(
        "extractions",
        sa.Column("extraction_id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(20), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("attributes", postgresql.JSONB, nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.Column("confidence_tier", sa.String(10)),
        sa.Column("avg_similarity", sa.Numeric(4, 3)),
        sa.Column("examples_used", postgresql.ARRAY(sa.Text)),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(8, 6)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("validation_passed", sa.Boolean, server_default="true"),
        sa.Column("validation_warnings", postgresql.ARRAY(sa.Text)),
        sa.Column("is_gold", sa.Boolean, server_default="false"),
        sa.Column("verified_by", sa.String(50)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("graph_synced", sa.Boolean, server_default="false"),
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_ext_order", "extractions", ["order_id"])
    op.create_index("idx_ext_attrs", "extractions", ["attributes"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX idx_ext_not_synced ON extractions(graph_synced) WHERE graph_synced = FALSE"
    )

    # ── gold_examples ──
    op.create_table(
        "gold_examples",
        sa.Column("gold_id", sa.String(20), primary_key=True),
        sa.Column("raw_input", sa.Text, nullable=False),
        sa.Column("extracted_output", postgresql.JSONB, nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("brand", sa.String(50)),
        sa.Column("quality_score", sa.Numeric(3, 2), server_default="1.00"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", sa.String(50), server_default="'initial_seed'"),
    )

    # ── tool_call_traces ──
    op.create_table(
        "tool_call_traces",
        sa.Column("trace_id", sa.String(36), primary_key=True),
        sa.Column("step", sa.Integer, primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("user_query", sa.Text, nullable=False),
        sa.Column("selected_tool", sa.String(100), nullable=False),
        sa.Column("tool_input", postgresql.JSONB, nullable=False),
        sa.Column("selection_reason", sa.Text),
        sa.Column("tool_output", postgresql.JSONB),
        sa.Column("tool_latency_ms", sa.Integer),
        sa.Column("tool_success", sa.Boolean, server_default="true"),
        sa.Column("error_message", sa.Text),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(8, 6)),
        sa.Column("mcp_server", sa.String(50)),
    )
    op.create_index("idx_trace_ts", "tool_call_traces", ["timestamp"])
    op.create_index("idx_trace_tool", "tool_call_traces", ["selected_tool"])

    # ── emerging_attributes ──
    op.create_table(
        "emerging_attributes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("attribute_key", sa.String(100), unique=True, nullable=False),
        sa.Column("occurrence", sa.Integer, nullable=False),
        sa.Column("first_seen", sa.Date, nullable=False),
        sa.Column("last_seen", sa.Date, nullable=False),
        sa.Column("example_values", postgresql.ARRAY(sa.Text)),
        sa.Column("found_in_types", postgresql.ARRAY(sa.Text)),
        sa.Column("status", sa.String(20), server_default="'detected'"),
        sa.Column("promoted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS orders_unified")
    op.drop_table("emerging_attributes")
    op.drop_table("tool_call_traces")
    op.drop_table("gold_examples")
    op.drop_table("extractions")
    op.drop_table("orders_shopee")
    op.drop_table("orders_qoo10")
    op.drop_table("orders_cafe24")
