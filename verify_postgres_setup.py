from __future__ import annotations

from inventory_db import _database_url, backend_label, connect, init_db


def main() -> int:
    if not _database_url():
        raise RuntimeError("DATABASE_URL is not set. Create a .env file first.")

    conn = connect("inventory.sqlite3")
    try:
        init_db(conn)
        print(f"Backend: {backend_label()}")
        for table in ("categories", "products", "users", "transactions", "orders"):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
