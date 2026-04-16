from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from inventory_db import Product, connect, init_db, upsert_products


APP_DIR = Path(__file__).resolve().parent
SOURCE_SQLITE = APP_DIR / "inventory.sqlite3"


def require_database_url() -> None:
    if not os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError("Set DATABASE_URL before running this migration script.")


def copy_table_rows(sqlite_conn: sqlite3.Connection, target_conn, table: str, columns: list[str]) -> int:
    select_sql = f"SELECT {', '.join(columns)} FROM {table}"
    rows = sqlite_conn.execute(select_sql).fetchall()
    if not rows:
        return 0

    placeholders = ", ".join(["?"] * len(columns))
    target_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    target_conn.executemany(target_sql.replace("?", "%s"), rows)
    return len(rows)


def reset_sequence(target_conn, table: str) -> None:
    if table not in {"products", "users", "transactions", "orders"}:
        raise ValueError(f"Unsupported table for sequence reset: {table}")

    target_conn.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence(%s, 'id'),
            COALESCE((SELECT MAX(id) FROM {table}), 1),
            COALESCE((SELECT MAX(id) FROM {table}), 0) > 0
        )
        """,
        (table,),
    )


def main() -> int:
    require_database_url()
    if not SOURCE_SQLITE.exists():
        raise FileNotFoundError(f"Source SQLite database not found: {SOURCE_SQLITE}")

    sqlite_conn = sqlite3.connect(str(SOURCE_SQLITE))
    target_conn = connect(SOURCE_SQLITE)

    try:
        init_db(target_conn)
        target_conn.execute("TRUNCATE TABLE transactions, orders, users, products RESTART IDENTITY")

        products = [
            Product(category=row[0], name=row[1])
            for row in sqlite_conn.execute("SELECT category, name FROM products").fetchall()
        ]
        inserted_products = upsert_products(target_conn, products)

        copied_users = copy_table_rows(
            sqlite_conn,
            target_conn,
            "users",
            [
                "id",
                "username",
                "password_hash",
                "role",
                "is_active",
                "recovery_question",
                "recovery_answer_hash",
                "created_at",
            ],
        )
        copied_transactions = copy_table_rows(
            sqlite_conn,
            target_conn,
            "transactions",
            ["id", "created_at", "tx_type", "category", "name", "qty", "created_by", "note"],
        )
        copied_orders = copy_table_rows(
            sqlite_conn,
            target_conn,
            "orders",
            ["id", "created_at", "category", "name", "qty", "note", "status", "inventory_applied", "created_by"],
        )

        for table_name in ("products", "users", "transactions", "orders"):
            reset_sequence(target_conn, table_name)

        target_conn.commit()
        print("Migration complete.")
        print(f"Products inserted: {inserted_products}")
        print(f"Users copied: {copied_users}")
        print(f"Transactions copied: {copied_transactions}")
        print(f"Orders copied: {copied_orders}")
        return 0
    finally:
        sqlite_conn.close()
        target_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
