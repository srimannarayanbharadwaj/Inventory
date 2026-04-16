from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Iterable

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


APP_DIR = Path(__file__).resolve().parent

def _load_local_env() -> None:
    env_path = APP_DIR / ".env"
    if not env_path.exists():
        return

    if load_dotenv is not None:
        load_dotenv(env_path)
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()


@dataclass(frozen=True)
class Product:
    category: str
    name: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _database_url() -> str:
    return (
        os.getenv("DATABASE_URL", "").strip()
        or os.getenv("SUPABASE_DB_URL", "").strip()
        or os.getenv("POSTGRES_URL", "").strip()
    )


def using_postgres() -> bool:
    return bool(_database_url())


def backend_label() -> str:
    return "PostgreSQL" if using_postgres() else "SQLite"


def _is_postgres(conn) -> bool:
    return conn.__class__.__module__.startswith("psycopg")


def _adapt_sql(conn, query: str) -> str:
    if _is_postgres(conn):
        return query.replace("?", "%s")
    return query


def _execute(conn, query: str, params: Iterable[object] | None = None):
    return conn.execute(_adapt_sql(conn, query), tuple(params or ()))


def _executemany(conn, query: str, rows: Iterable[Iterable[object]]):
    prepared_rows = [tuple(row) for row in rows]
    if not prepared_rows:
        return None
    return conn.executemany(_adapt_sql(conn, query), prepared_rows)


def _combine_start(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return datetime.combine(value, time.min, tzinfo=timezone.utc).isoformat()


def _combine_end(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return datetime.combine(value, time.max, tzinfo=timezone.utc).isoformat()


def connect(db_path: str | Path):
    database_url = _database_url()
    if database_url:
        if psycopg is None:
            raise RuntimeError(
                "PostgreSQL support requires the 'psycopg[binary]' package. "
                "Install requirements.txt before using DATABASE_URL."
            )
        return psycopg.connect(database_url, autocommit=False)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def _sync_categories_from_products(conn) -> None:
    rows = _execute(
        conn,
        """
        SELECT DISTINCT category
        FROM products
        WHERE TRIM(category) <> ''
        ORDER BY category
        """,
    ).fetchall()
    now = _utc_now_iso()
    for row in rows:
        category = str(row[0]).strip()
        if not category:
            continue
        if _is_postgres(conn):
            _execute(
                conn,
                """
                INSERT INTO categories(name, created_at)
                VALUES (?, ?)
                ON CONFLICT (name) DO NOTHING
                """,
                (category, now),
            )
        else:
            _execute(
                conn,
                """
                INSERT OR IGNORE INTO categories(name, created_at)
                VALUES (?, ?)
                """,
                (category, now),
            )


def init_db(conn) -> None:
    if _is_postgres(conn):
        statements = [
            """
            CREATE TABLE IF NOT EXISTS categories (
              id BIGSERIAL PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              created_at TIMESTAMPTZ NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS products (
              id BIGSERIAL PRIMARY KEY,
              category TEXT NOT NULL,
              name TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL,
              UNIQUE(category, name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transactions (
              id BIGSERIAL PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL,
              tx_type TEXT NOT NULL CHECK (tx_type IN ('purchase', 'reduction')),
              category TEXT NOT NULL,
              name TEXT NOT NULL,
              qty DOUBLE PRECISION NOT NULL CHECK (qty > 0),
              created_by TEXT NOT NULL DEFAULT '',
              note TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
              id BIGSERIAL PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
              is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
              recovery_question TEXT NOT NULL DEFAULT '',
              recovery_answer_hash TEXT NOT NULL DEFAULT '',
              created_at TIMESTAMPTZ NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
              id BIGSERIAL PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL,
              category TEXT NOT NULL,
              name TEXT NOT NULL,
              qty DOUBLE PRECISION NOT NULL CHECK (qty > 0),
              note TEXT,
              status TEXT NOT NULL DEFAULT 'pending',
              inventory_applied INTEGER NOT NULL DEFAULT 0 CHECK (inventory_applied IN (0, 1)),
              created_by TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_tx_product ON transactions(category, name)",
            "CREATE INDEX IF NOT EXISTS idx_tx_created_at ON transactions(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_by ON orders(created_by)",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)",
            "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_question TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_answer_hash TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS inventory_applied INTEGER NOT NULL DEFAULT 0",
        ]
        for statement in statements:
            _execute(conn, statement)
    else:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
              id INTEGER PRIMARY KEY,
              category TEXT NOT NULL,
              name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(category, name)
            );

            CREATE TABLE IF NOT EXISTS transactions (
              id INTEGER PRIMARY KEY,
              created_at TEXT NOT NULL,
              tx_type TEXT NOT NULL CHECK (tx_type IN ('purchase', 'reduction')),
              category TEXT NOT NULL,
              name TEXT NOT NULL,
              qty REAL NOT NULL CHECK (qty > 0),
              created_by TEXT NOT NULL DEFAULT '',
              note TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
              is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
              recovery_question TEXT NOT NULL DEFAULT '',
              recovery_answer_hash TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
              id INTEGER PRIMARY KEY,
              created_at TEXT NOT NULL,
              category TEXT NOT NULL,
              name TEXT NOT NULL,
              qty REAL NOT NULL CHECK (qty > 0),
              note TEXT,
              status TEXT NOT NULL DEFAULT 'pending',
              inventory_applied INTEGER NOT NULL DEFAULT 0 CHECK (inventory_applied IN (0, 1)),
              created_by TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tx_product ON transactions(category, name);
            CREATE INDEX IF NOT EXISTS idx_tx_created_at ON transactions(created_at);
            CREATE INDEX IF NOT EXISTS idx_orders_created_by ON orders(created_by);
            CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
            """
        )
        cols = [row[1] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()]
        if "created_by" not in cols:
            conn.execute("ALTER TABLE transactions ADD COLUMN created_by TEXT NOT NULL DEFAULT ''")

        user_cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "recovery_question" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN recovery_question TEXT NOT NULL DEFAULT ''")
        if "recovery_answer_hash" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN recovery_answer_hash TEXT NOT NULL DEFAULT ''")

        order_cols = [row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()]
        if "inventory_applied" not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN inventory_applied INTEGER NOT NULL DEFAULT 0")

    _sync_categories_from_products(conn)

    user_count = _execute(conn, "SELECT COUNT(*) FROM users").fetchone()[0]
    if int(user_count) == 0:
        create_user(conn, username="admin", password="admin123", role="admin", is_active=True)
    conn.commit()


def fetch_categories(conn) -> list[str]:
    order_clause = "ORDER BY LOWER(name)" if _is_postgres(conn) else "ORDER BY name COLLATE NOCASE"
    rows = _execute(conn, f"SELECT name FROM categories {order_clause}").fetchall()
    return [str(row[0]) for row in rows]


def add_category(conn, name: str) -> bool:
    clean_name = name.strip()
    if not clean_name:
        return False

    if _is_postgres(conn):
        cur = _execute(
            conn,
            """
            INSERT INTO categories(name, created_at)
            VALUES (?, ?)
            ON CONFLICT (name) DO NOTHING
            """,
            (clean_name, _utc_now_iso()),
        )
    else:
        cur = _execute(
            conn,
            """
            INSERT OR IGNORE INTO categories(name, created_at)
            VALUES (?, ?)
            """,
            (clean_name, _utc_now_iso()),
        )
    conn.commit()
    return cur.rowcount > 0


def rename_category(conn, *, old_name: str, new_name: str) -> tuple[bool, str]:
    source = old_name.strip()
    target = new_name.strip()
    if not source or not target:
        return False, "Category names cannot be empty."
    if source == target:
        return True, "Category name is unchanged."

    if _execute(conn, "SELECT 1 FROM categories WHERE name = ?", (target,)).fetchone():
        return False, "A category with that name already exists."

    cur = _execute(conn, "UPDATE categories SET name = ? WHERE name = ?", (target, source))
    if cur.rowcount <= 0:
        conn.commit()
        return False, "Category not found."

    _execute(conn, "UPDATE products SET category = ? WHERE category = ?", (target, source))
    _execute(conn, "UPDATE transactions SET category = ? WHERE category = ?", (target, source))
    _execute(conn, "UPDATE orders SET category = ? WHERE category = ?", (target, source))
    conn.commit()
    return True, "Category renamed successfully."


def delete_category(conn, *, name: str) -> tuple[bool, str]:
    clean_name = name.strip()
    if not clean_name:
        return False, "Category is required."

    product_count = int(_execute(conn, "SELECT COUNT(*) FROM products WHERE category = ?", (clean_name,)).fetchone()[0])
    tx_count = int(_execute(conn, "SELECT COUNT(*) FROM transactions WHERE category = ?", (clean_name,)).fetchone()[0])
    order_count = int(_execute(conn, "SELECT COUNT(*) FROM orders WHERE category = ?", (clean_name,)).fetchone()[0])
    if product_count or tx_count or order_count:
        return False, "Category cannot be deleted while it is referenced by products, orders, or transactions."

    cur = _execute(conn, "DELETE FROM categories WHERE name = ?", (clean_name,))
    conn.commit()
    if cur.rowcount <= 0:
        return False, "Category not found."
    return True, "Category deleted successfully."


def upsert_products(conn, products: Iterable[Product]) -> int:
    inserted = 0
    now = _utc_now_iso()
    rows = [(p.category.strip(), p.name.strip(), now) for p in products if p.category and p.name]
    if not rows:
        return 0

    for category, name, created_at in rows:
        add_category(conn, category)
        if _is_postgres(conn):
            cur = _execute(
                conn,
                """
                INSERT INTO products(category, name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT (category, name) DO NOTHING
                """,
                (category, name, created_at),
            )
        else:
            cur = _execute(
                conn,
                """
                INSERT OR IGNORE INTO products(category, name, created_at)
                VALUES (?, ?, ?)
                """,
                (category, name, created_at),
            )
        inserted += max(cur.rowcount, 0)

    conn.commit()
    return inserted


def add_product(conn, product: Product) -> bool:
    category = product.category.strip()
    name = product.name.strip()
    if not category or not name:
        return False

    add_category(conn, category)
    if _is_postgres(conn):
        cur = _execute(
            conn,
            """
            INSERT INTO products(category, name, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT (category, name) DO NOTHING
            """,
            (category, name, _utc_now_iso()),
        )
    else:
        cur = _execute(
            conn,
            """
            INSERT OR IGNORE INTO products(category, name, created_at)
            VALUES (?, ?, ?)
            """,
            (category, name, _utc_now_iso()),
        )
    conn.commit()
    return cur.rowcount > 0


def update_product(
    conn,
    *,
    old_category: str,
    old_name: str,
    new_category: str,
    new_name: str,
) -> tuple[bool, str]:
    source_category = old_category.strip()
    source_name = old_name.strip()
    target_category = new_category.strip()
    target_name = new_name.strip()
    if not source_category or not source_name or not target_category or not target_name:
        return False, "Product category and name are required."

    existing = _execute(
        conn,
        """
        SELECT 1
        FROM products
        WHERE category = ? AND name = ? AND NOT (category = ? AND name = ?)
        """,
        (target_category, target_name, source_category, source_name),
    ).fetchone()
    if existing:
        return False, "A product with that category and name already exists."

    add_category(conn, target_category)
    cur = _execute(
        conn,
        """
        UPDATE products
        SET category = ?, name = ?
        WHERE category = ? AND name = ?
        """,
        (target_category, target_name, source_category, source_name),
    )
    if cur.rowcount <= 0:
        conn.commit()
        return False, "Product not found."

    _execute(
        conn,
        "UPDATE transactions SET category = ?, name = ? WHERE category = ? AND name = ?",
        (target_category, target_name, source_category, source_name),
    )
    _execute(
        conn,
        "UPDATE orders SET category = ?, name = ? WHERE category = ? AND name = ?",
        (target_category, target_name, source_category, source_name),
    )
    conn.commit()
    return True, "Product updated successfully."


def delete_product(conn, *, category: str, name: str) -> tuple[bool, str]:
    clean_category = category.strip()
    clean_name = name.strip()
    if not clean_category or not clean_name:
        return False, "Product category and name are required."

    tx_count = int(
        _execute(
            conn,
            "SELECT COUNT(*) FROM transactions WHERE category = ? AND name = ?",
            (clean_category, clean_name),
        ).fetchone()[0]
    )
    order_count = int(
        _execute(
            conn,
            "SELECT COUNT(*) FROM orders WHERE category = ? AND name = ?",
            (clean_category, clean_name),
        ).fetchone()[0]
    )
    if tx_count or order_count:
        return False, "Product cannot be deleted while it is referenced by orders or transactions."

    cur = _execute(
        conn,
        "DELETE FROM products WHERE category = ? AND name = ?",
        (clean_category, clean_name),
    )
    conn.commit()
    if cur.rowcount <= 0:
        return False, "Product not found."
    return True, "Product deleted successfully."


def add_transaction(
    conn,
    *,
    tx_type: str,
    product: Product,
    qty: float,
    created_by: str,
    note: str | None = None,
) -> None:
    _execute(
        conn,
        """
        INSERT INTO transactions(created_at, tx_type, category, name, qty, created_by, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _utc_now_iso(),
            tx_type,
            product.category.strip(),
            product.name.strip(),
            float(qty),
            created_by.strip(),
            note or None,
        ),
    )
    conn.commit()


def fetch_products(conn) -> list[Product]:
    cur = _execute(
        conn,
        """
        SELECT category, name
        FROM products
        ORDER BY category, name
        """,
    )
    return [Product(category=row[0], name=row[1]) for row in cur.fetchall()]


def fetch_inventory(
    conn,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
) -> list[tuple[str, str, float, float, float]]:
    params: list[object] = []
    where_clause = ""

    if start_date is not None:
        where_clause = "WHERE created_at >= ?"
        params.append(_combine_start(start_date))

    if end_date is not None:
        where_clause += " AND " if where_clause else "WHERE "
        where_clause += "created_at <= ?"
        params.append(_combine_end(end_date))

    order_clause = (
        "ORDER BY LOWER(p.category), LOWER(p.name)"
        if _is_postgres(conn)
        else "ORDER BY p.category COLLATE NOCASE, p.name COLLATE NOCASE"
    )

    cur = _execute(
        conn,
        f"""
        WITH tx AS (
          SELECT
            category,
            name,
            SUM(CASE WHEN tx_type='purchase' THEN qty ELSE 0 END) AS purchased_qty,
            SUM(CASE WHEN tx_type='reduction' THEN qty ELSE 0 END) AS reduced_qty
          FROM transactions
          {where_clause}
          GROUP BY category, name
        )
        SELECT
          p.category,
          p.name,
          COALESCE(tx.purchased_qty, 0) AS purchased_qty,
          COALESCE(tx.reduced_qty, 0) AS reduced_qty,
          COALESCE(tx.purchased_qty, 0) - COALESCE(tx.reduced_qty, 0) AS on_hand
        FROM products p
        LEFT JOIN tx
          ON tx.category = p.category AND tx.name = p.name
        {order_clause}
        """,
        params,
    )
    return [(r[0], r[1], float(r[2]), float(r[3]), float(r[4])) for r in cur.fetchall()]


def fetch_transactions(conn, limit: int = 500) -> list[tuple]:
    cur = _execute(
        conn,
        """
        SELECT id, created_at, tx_type, category, name, qty, COALESCE(created_by, ''), COALESCE(note, '')
        FROM transactions
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    return cur.fetchall()


def fetch_purchase_transactions(
    conn,
    *,
    limit: int = 500,
    created_by: str | None = None,
) -> list[tuple]:
    if created_by:
        cur = _execute(
            conn,
            """
            SELECT id, created_at, tx_type, category, name, qty, COALESCE(created_by, ''), COALESCE(note, '')
            FROM transactions
            WHERE tx_type = 'purchase' AND created_by = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (created_by.strip(), int(limit)),
        )
    else:
        cur = _execute(
            conn,
            """
            SELECT id, created_at, tx_type, category, name, qty, COALESCE(created_by, ''), COALESCE(note, '')
            FROM transactions
            WHERE tx_type = 'purchase'
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
    return cur.fetchall()


def fetch_reduction_transactions(
    conn,
    *,
    limit: int = 500,
    created_by: str | None = None,
) -> list[tuple]:
    if created_by:
        cur = _execute(
            conn,
            """
            SELECT id, created_at, tx_type, category, name, qty, COALESCE(created_by, ''), COALESCE(note, '')
            FROM transactions
            WHERE tx_type = 'reduction' AND created_by = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (created_by.strip(), int(limit)),
        )
    else:
        cur = _execute(
            conn,
            """
            SELECT id, created_at, tx_type, category, name, qty, COALESCE(created_by, ''), COALESCE(note, '')
            FROM transactions
            WHERE tx_type = 'reduction'
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
    return cur.fetchall()


def _hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt_bytes = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 100_000)
    return f"{salt_bytes.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)
    except Exception:
        return False
    expected = _hash_password(password, salt=salt).split("$", 1)[1]
    return hmac.compare_digest(expected, digest_hex)


def _normalize_recovery_answer(answer: str) -> str:
    return " ".join(answer.strip().lower().split())


def create_user(
    conn,
    *,
    username: str,
    password: str,
    role: str = "user",
    is_active: bool = True,
    recovery_question: str = "",
    recovery_answer: str = "",
) -> bool:
    clean_username = username.strip().lower()
    if not clean_username or not password:
        return False

    recovery_q = recovery_question.strip()
    recovery_hash = ""
    if recovery_q and recovery_answer.strip():
        recovery_hash = _hash_password(_normalize_recovery_answer(recovery_answer))

    if _is_postgres(conn):
        cur = _execute(
            conn,
            """
            INSERT INTO users(
              username, password_hash, role, is_active, recovery_question, recovery_answer_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (username) DO NOTHING
            """,
            (
                clean_username,
                _hash_password(password),
                "admin" if role == "admin" else "user",
                1 if is_active else 0,
                recovery_q,
                recovery_hash,
                _utc_now_iso(),
            ),
        )
    else:
        cur = _execute(
            conn,
            """
            INSERT OR IGNORE INTO users(
              username, password_hash, role, is_active, recovery_question, recovery_answer_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_username,
                _hash_password(password),
                "admin" if role == "admin" else "user",
                1 if is_active else 0,
                recovery_q,
                recovery_hash,
                _utc_now_iso(),
            ),
        )

    conn.commit()
    return cur.rowcount > 0


def authenticate_user(conn, *, username: str, password: str) -> dict | None:
    clean_username = username.strip().lower()
    row = _execute(
        conn,
        """
        SELECT id, username, password_hash, role, is_active
        FROM users
        WHERE username = ?
        """,
        (clean_username,),
    ).fetchone()
    if not row or int(row[4]) != 1 or not _verify_password(password, row[2]):
        return None
    return {"id": int(row[0]), "username": str(row[1]), "role": str(row[3])}


def fetch_users(conn) -> list[tuple]:
    order_clause = "ORDER BY LOWER(username)" if _is_postgres(conn) else "ORDER BY username COLLATE NOCASE"
    cur = _execute(
        conn,
        f"""
        SELECT id, username, role, is_active, created_at, recovery_question
        FROM users
        {order_clause}
        """,
    )
    return cur.fetchall()


def update_user_role_and_status(conn, *, user_id: int, role: str, is_active: bool) -> None:
    _execute(
        conn,
        """
        UPDATE users
        SET role = ?, is_active = ?
        WHERE id = ?
        """,
        ("admin" if role == "admin" else "user", 1 if is_active else 0, int(user_id)),
    )
    conn.commit()


def update_purchase_transaction(
    conn,
    *,
    tx_id: int,
    category: str,
    name: str,
    qty: float,
    note: str | None,
) -> bool:
    cur = _execute(
        conn,
        """
        UPDATE transactions
        SET category = ?, name = ?, qty = ?, note = ?
        WHERE id = ? AND tx_type = 'purchase'
        """,
        (category.strip(), name.strip(), float(qty), note or None, int(tx_id)),
    )
    conn.commit()
    return cur.rowcount > 0


def update_reduction_transaction(
    conn,
    *,
    tx_id: int,
    category: str,
    name: str,
    qty: float,
    note: str | None,
) -> bool:
    cur = _execute(
        conn,
        """
        UPDATE transactions
        SET category = ?, name = ?, qty = ?, note = ?
        WHERE id = ? AND tx_type = 'reduction'
        """,
        (category.strip(), name.strip(), float(qty), note or None, int(tx_id)),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_user(conn, *, user_id: int) -> bool:
    cur = _execute(conn, "DELETE FROM users WHERE id = ?", (int(user_id),))
    conn.commit()
    return cur.rowcount > 0


def create_order(
    conn,
    *,
    category: str,
    name: str,
    qty: float,
    created_by: str,
    note: str | None = None,
) -> bool:
    cur = _execute(
        conn,
        """
        INSERT INTO orders(created_at, category, name, qty, note, status, created_by)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """,
        (_utc_now_iso(), category.strip(), name.strip(), float(qty), note or None, created_by.strip()),
    )
    conn.commit()
    return cur.rowcount > 0


def fetch_orders(conn, *, limit: int = 500, created_by: str | None = None) -> list[tuple]:
    if created_by:
        cur = _execute(
            conn,
            """
            SELECT id, created_at, category, name, qty, COALESCE(note, ''), status, created_by
            FROM orders
            WHERE created_by = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (created_by.strip(), int(limit)),
        )
    else:
        cur = _execute(
            conn,
            """
            SELECT id, created_at, category, name, qty, COALESCE(note, ''), status, created_by
            FROM orders
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
    return cur.fetchall()


def update_order(
    conn,
    *,
    order_id: int,
    category: str,
    name: str,
    qty: float,
    note: str | None,
    status: str,
    updated_by: str,
    is_admin: bool,
) -> bool:
    order_row = _execute(
        conn,
        """
        SELECT id, status, inventory_applied, created_by
        FROM orders
        WHERE id = ?
        """,
        (int(order_id),),
    ).fetchone()
    if not order_row:
        return False

    cur = _execute(
        conn,
        """
        UPDATE orders
        SET category = ?, name = ?, qty = ?, note = ?, status = ?
        WHERE id = ?
        """,
        (
            category.strip(),
            name.strip(),
            float(qty),
            note or None,
            status.strip() or "pending",
            int(order_id),
        ),
    )
    if cur.rowcount <= 0:
        conn.commit()
        return False

    normalized_status = (status or "").strip().lower()
    already_applied = int(order_row[2]) == 1
    if is_admin and normalized_status == "received" and not already_applied:
        _execute(
            conn,
            """
            INSERT INTO transactions(created_at, tx_type, category, name, qty, created_by, note)
            VALUES (?, 'purchase', ?, ?, ?, ?, ?)
            """,
            (
                _utc_now_iso(),
                category.strip(),
                name.strip(),
                float(qty),
                updated_by.strip(),
                f"Auto inventory update from order #{int(order_id)}",
            ),
        )
        _execute(conn, "UPDATE orders SET inventory_applied = 1 WHERE id = ?", (int(order_id),))

    conn.commit()
    return True


def change_password(conn, *, username: str, current_password: str, new_password: str) -> bool:
    clean_username = username.strip().lower()
    row = _execute(
        conn,
        "SELECT password_hash FROM users WHERE username = ? AND is_active = 1",
        (clean_username,),
    ).fetchone()
    if not row or not _verify_password(current_password, row[0]):
        return False
    _execute(
        conn,
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (_hash_password(new_password), clean_username),
    )
    conn.commit()
    return True


def set_recovery_details(
    conn,
    *,
    username: str,
    current_password: str,
    recovery_question: str,
    recovery_answer: str,
) -> bool:
    clean_username = username.strip().lower()
    row = _execute(
        conn,
        "SELECT password_hash FROM users WHERE username = ? AND is_active = 1",
        (clean_username,),
    ).fetchone()
    if not row or not _verify_password(current_password, row[0]):
        return False

    q = recovery_question.strip()
    a = recovery_answer.strip()
    if not q or not a:
        return False

    _execute(
        conn,
        "UPDATE users SET recovery_question = ?, recovery_answer_hash = ? WHERE username = ?",
        (q, _hash_password(_normalize_recovery_answer(a)), clean_username),
    )
    conn.commit()
    return True


def get_recovery_question(conn, *, username: str) -> str:
    clean_username = username.strip().lower()
    row = _execute(
        conn,
        "SELECT COALESCE(recovery_question, '') FROM users WHERE username = ? AND is_active = 1",
        (clean_username,),
    ).fetchone()
    return "" if not row else str(row[0] or "")


def recover_password(conn, *, username: str, recovery_answer: str, new_password: str) -> bool:
    clean_username = username.strip().lower()
    row = _execute(
        conn,
        """
        SELECT recovery_answer_hash
        FROM users
        WHERE username = ? AND is_active = 1
        """,
        (clean_username,),
    ).fetchone()
    if not row:
        return False

    stored = str(row[0] or "")
    if not stored or not _verify_password(_normalize_recovery_answer(recovery_answer), stored):
        return False

    _execute(
        conn,
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (_hash_password(new_password), clean_username),
    )
    conn.commit()
    return True
