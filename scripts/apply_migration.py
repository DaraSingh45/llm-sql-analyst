"""
Apply a .sql migration file to the database, then remind you to update the
documentation the LLM reads.

Usage:
    python -m scripts.apply_migration data/migrations/001_add_performance_reviews.sql

The whole file runs in one transaction: if any statement fails, nothing is
committed, so a broken migration can't leave the schema half-changed.
"""
import argparse
import sys
from pathlib import Path

import psycopg2

import config


def main():
    parser = argparse.ArgumentParser(description="Apply a SQL migration file.")
    parser.add_argument("path")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"No such file: {path}")
        sys.exit(1)

    sql = path.read_text(encoding="utf-8")

    conn = psycopg2.connect(config.DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
        print(f"Applied {path.name}.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed, database unchanged: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print("\nNext, so the model knows about the change:")
    print("  1. Update or add the matching file in schema_docs/tables/")
    print("  2. python -m scripts.check_schema_sync")
    print("  3. python -m src.build_index")


if __name__ == "__main__":
    main()
