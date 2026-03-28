"""SQLAlchemy ORM models matching Doc 2 DDL spec."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


# ── Orders ──────────────────────────────────────────────────────────


class OrderCafe24(Base):
    __tablename__ = "orders_cafe24"

    order_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    destination_country: Mapped[str] = mapped_column(String(5), nullable=False)
    brand: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_usd: Mapped[float | None] = mapped_column(Numeric(8, 2))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_cafe24_country_date", "destination_country", "order_date"),
        Index("idx_cafe24_type", "product_type"),
    )


class OrderQoo10(Base):
    __tablename__ = "orders_qoo10"

    order_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    destination_country: Mapped[str] = mapped_column(String(5), nullable=False)
    brand: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_usd: Mapped[float | None] = mapped_column(Numeric(8, 2))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_qoo10_country_date", "destination_country", "order_date"),
        Index("idx_qoo10_type", "product_type"),
    )


class OrderShopee(Base):
    __tablename__ = "orders_shopee"

    order_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    destination_country: Mapped[str] = mapped_column(String(5), nullable=False)
    brand: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_usd: Mapped[float | None] = mapped_column(Numeric(8, 2))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_shopee_date", "order_date"),
        Index("idx_shopee_type", "product_type"),
    )


# ── Extractions ─────────────────────────────────────────────────────


class Extraction(Base):
    __tablename__ = "extractions"

    extraction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(20), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    confidence_tier: Mapped[str | None] = mapped_column(String(10))
    avg_similarity: Mapped[float | None] = mapped_column(Numeric(4, 3))
    examples_used: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(8, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    validation_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_warnings: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_gold: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graph_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_ext_order", "order_id"),
        Index("idx_ext_attrs", "attributes", postgresql_using="gin"),
        Index(
            "idx_ext_not_synced",
            "graph_synced",
            postgresql_where="graph_synced = FALSE",
        ),
    )


# ── Gold Examples ────────────────────────────────────────────────────


class GoldExample(Base):
    __tablename__ = "gold_examples"

    gold_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(50))
    quality_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.00)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[str] = mapped_column(String(50), default="initial_seed")


# ── Tool Call Traces ─────────────────────────────────────────────────


class ToolCallTrace(Base):
    __tablename__ = "tool_call_traces"

    trace_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    step: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    selected_tool: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    selection_reason: Mapped[str | None] = mapped_column(Text)
    tool_output: Mapped[dict | None] = mapped_column(JSONB)
    tool_latency_ms: Mapped[int | None] = mapped_column(Integer)
    tool_success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(8, 6))
    mcp_server: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        Index("idx_trace_ts", "timestamp"),
        Index("idx_trace_tool", "selected_tool"),
    )


# ── Emerging Attributes (Phase 2) ───────────────────────────────────


class EmergingAttribute(Base):
    __tablename__ = "emerging_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attribute_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    occurrence: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen: Mapped[date] = mapped_column(Date, nullable=False)
    last_seen: Mapped[date] = mapped_column(Date, nullable=False)
    example_values: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    found_in_types: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(String(20), default="detected")
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
