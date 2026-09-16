"""
Load a CSV file into an existing database table.

Usage:
    python -m scripts.load_csv <csv_path> <table_name> [--truncate]

Example:
    python -m scripts.load_csv mydata/employees.csv employees
    python -m scripts.load_csv mydata/employees.csv employees --truncate

The CSV's header row must match the target table's column names. Columns you
leave out must be nullable or have a default in the table definition.
"""
import argparse
import sys

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

import config
from src import db


def main():
    parser = argparse.ArgumentParser(description="Load a CSV into a Postgres table.")
    parser.add_argument("csv_path")
    parser.add_argument("table")
    parser.add_argument("--truncate", action="store_true",
                        help="Delete existing rows in the table before loading.")
    args = parser.parse_args()

    schema = db.get_schema_metadata()
    if args.table not in schema:
        print(f"Table '{args.table}' does not exist. Known tables: {', '.join(sorted(schema))}")
        sys.exit(1)

    df = pd.read_csv(args.csv_path)
    df = df.where(pd.notnull(df), None)  # NaN -> NULL

    table_columns = set(schema[args.table])
    unknown = [c for c in df.columns if c not in table_columns]
    if unknown:
        print(f"CSV has columns not present in '{args.table}': {', '.join(unknown)}")
        print(f"Table columns are: {', '.join(schema[args.table])}")
        sys.exit(1)

    cols = list(df.columns)
    col_sql = ", ".join(f'"{c}"' for c in cols)
    rows = [tuple(r) for r in df[cols].itertuples(index=False, name=None)]

    conn = psycopg2.connect(config.DATABASE_URL)
    cur = conn.cursor()
    try:
        if args.truncate:
            cur.execute(f'DELETE FROM "{args.table}";')
            print(f"Cleared existing rows from '{args.table}'.")

        execute_values(cur, f'INSERT INTO "{args.table}" ({col_sql}) VALUES %s', rows)
        conn.commit()
        print(f"Loaded {len(rows)} rows into '{args.table}'.")
    except Exception as e:
        conn.rollback()
        print(f"Load failed, nothing was written: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
