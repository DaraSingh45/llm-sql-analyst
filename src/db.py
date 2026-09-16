"""PostgreSQL connection + read helpers."""
import psycopg2
import pandas as pd
from contextlib import contextmanager
import config


@contextmanager
def get_connection():
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def run_query(sql: str, params=None) -> pd.DataFrame:
    """Execute a read-only SQL query and return a DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_schema_metadata() -> dict:
    """
    Introspects the database and returns {table_name: [col1, col2, ...]}.
    Used by the SQL validator to check that generated SQL only references
    real tables/columns (instead of trusting the model blindly).
    """
    query = """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    df = run_query(query)
    schema = {}
    for _, row in df.iterrows():
        schema.setdefault(row["table_name"], []).append(row["column_name"])
    return schema
