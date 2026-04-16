from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
SOURCE_SQLITE = APP_DIR / "inventory.sqlite3"
OUTPUT_DIR = APP_DIR / "csv_export"
TABLES = ("products", "users", "transactions", "orders")


def export_table(conn: sqlite3.Connection, table_name: str, output_dir: Path) -> Path:
    cursor = conn.execute(f"SELECT * FROM {table_name}")
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()

    output_path = output_dir / f"{table_name}.csv"
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)
    return output_path


def main() -> int:
    if not SOURCE_SQLITE.exists():
        raise FileNotFoundError(f"Source SQLite database not found: {SOURCE_SQLITE}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(str(SOURCE_SQLITE))
    try:
        for table_name in TABLES:
            output_path = export_table(conn, table_name, OUTPUT_DIR)
            print(f"Exported {table_name} -> {output_path}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
