"""Seed PostgreSQL with gold examples + order CSVs.

Usage:
    cd backend && python -m data.seed_db
    cd backend && python -m data.seed_db --verify
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import create_engine, text

from core.config import settings

logger = structlog.get_logger()

DATA_DIR = Path(__file__).parent
ENGINE = create_engine(settings.database_url_sync)


def load_gold_examples() -> int:
    gold_path = DATA_DIR / "seed_gold_examples.json"
    with open(gold_path) as f:
        examples = json.load(f)

    with ENGINE.connect() as conn:
        for ex in examples:
            conn.execute(
                text("""
                    INSERT INTO gold_examples (gold_id, raw_input, extracted_output, product_type, brand)
                    VALUES (:gold_id, :raw_input, :extracted_output, :product_type, :brand)
                    ON CONFLICT (gold_id) DO NOTHING
                """),
                {
                    "gold_id": ex["gold_id"],
                    "raw_input": ex["raw_input"],
                    "extracted_output": json.dumps(ex["extracted_output"]),
                    "product_type": ex["product_type"],
                    "brand": ex.get("brand"),
                },
            )
        conn.commit()

    logger.info("gold_examples_loaded", count=len(examples))
    return len(examples)


def load_orders_csv(filename: str, table: str) -> int:
    csv_path = DATA_DIR / filename
    if not csv_path.exists():
        logger.warning("csv_not_found", file=filename)
        return 0

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with ENGINE.connect() as conn:
        for row in rows:
            conn.execute(
                text(f"""
                    INSERT INTO {table}
                        (order_id, order_date, destination_country, brand,
                         product_name, product_type, quantity, unit_price_usd)
                    VALUES
                        (:order_id, :order_date, :destination_country, :brand,
                         :product_name, :product_type, :quantity, :unit_price_usd)
                    ON CONFLICT (order_id) DO NOTHING
                """),
                {
                    "order_id": row["order_id"],
                    "order_date": row["order_date"],
                    "destination_country": row["destination_country"],
                    "brand": row["brand"],
                    "product_name": row["product_name"],
                    "product_type": row["product_type"],
                    "quantity": int(row["quantity"]),
                    "unit_price_usd": float(row["unit_price_usd"]),
                },
            )
        conn.commit()

    logger.info("orders_loaded", table=table, count=len(rows))
    return len(rows)


def seed() -> None:
    gold_count = load_gold_examples()
    cafe24_count = load_orders_csv("orders_cafe24.csv", "orders_cafe24")
    qoo10_count = load_orders_csv("orders_qoo10.csv", "orders_qoo10")
    shopee_count = load_orders_csv("orders_shopee.csv", "orders_shopee")

    total = cafe24_count + qoo10_count + shopee_count
    logger.info(
        "seed_complete",
        gold_examples=gold_count,
        total_orders=total,
        cafe24=cafe24_count,
        qoo10=qoo10_count,
        shopee=shopee_count,
    )


def verify() -> None:
    with ENGINE.connect() as conn:
        print("\n=== Table Row Counts ===")
        for table in [
            "orders_cafe24",
            "orders_qoo10",
            "orders_shopee",
            "gold_examples",
            "extractions",
            "tool_call_traces",
            "emerging_attributes",
        ]:
            result = conn.execute(text(f"SELECT count(*) FROM {table}"))
            count = result.scalar()
            print(f"  {table}: {count}")

        print("\n=== Unified View: Orders by Platform ===")
        result = conn.execute(
            text(
                "SELECT platform, count(*) as cnt, sum(quantity) as total_qty "
                "FROM orders_unified GROUP BY platform ORDER BY platform"
            )
        )
        for row in result:
            print(f"  {row.platform}: {row.cnt} orders, {row.total_qty} units")

        print("\n=== Unified View: Orders by Country ===")
        result = conn.execute(
            text(
                "SELECT destination_country, count(*) as cnt "
                "FROM orders_unified GROUP BY destination_country ORDER BY cnt DESC"
            )
        )
        for row in result:
            print(f"  {row.destination_country}: {row.cnt} orders")

        print("\n=== Gold Examples by Type ===")
        result = conn.execute(
            text(
                "SELECT product_type, count(*) as cnt "
                "FROM gold_examples GROUP BY product_type ORDER BY cnt DESC"
            )
        )
        for row in result:
            print(f"  {row.product_type}: {row.cnt}")

    print("\nVerification complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="Run verification queries only")
    args = parser.parse_args()

    if args.verify:
        verify()
    else:
        seed()
        verify()
