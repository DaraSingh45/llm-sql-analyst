"""
Compares the live database schema against the documentation in schema_docs/.

This catches the failure mode that's easy to miss: you change a table, the
validator picks the change up automatically (it introspects the live
database), but the LLM keeps writing queries against the old schema because
schema_docs/ still describes the old shape. Silent wrong answers follow.

Usage:
    python -m scripts.check_schema_sync
"""
import sys

import config
from src import db

TABLES_DIR = config.SCHEMA_DOCS_DIR / "tables"


def documented_tables():
    """Maps table name -> full text of its doc file, based on filename."""
    return {p.stem: p.read_text(encoding="utf-8") for p in TABLES_DIR.glob("*.md")}


def main():
    try:
        live = db.get_schema_metadata()
    except Exception as e:
        print(f"Can't read the database schema: {e}")
        sys.exit(1)

    docs = documented_tables()
    problems = []

    for table, columns in sorted(live.items()):
        if table not in docs:
            problems.append(
                f"Table '{table}' exists in the database but has no "
                f"schema_docs/tables/{table}.md file."
            )
            continue
        text = docs[table].lower()
        missing = [c for c in columns if c.lower() not in text]
        if missing:
            problems.append(
                f"Table '{table}': column(s) not mentioned in "
                f"schema_docs/tables/{table}.md -> {', '.join(missing)}"
            )

    for documented in sorted(docs):
        if documented not in live:
            problems.append(
                f"schema_docs/tables/{documented}.md describes a table that no "
                f"longer exists in the database."
            )

    print(f"Database tables: {', '.join(sorted(live)) or '(none)'}")
    print(f"Documented tables: {', '.join(sorted(docs)) or '(none)'}\n")

    if not problems:
        print("Documentation matches the database.")
        if not config.VECTOR_INDEX_PATH.exists():
            print("\nThe vector index hasn't been built yet: python -m src.build_index")
        else:
            doc_mtime = max((p.stat().st_mtime for p in TABLES_DIR.glob("*.md")), default=0)
            if doc_mtime > config.VECTOR_INDEX_PATH.stat().st_mtime:
                print("\nDocs changed after the index was built. Rebuild it:")
                print("  python -m src.build_index")
        return

    print(f"Found {len(problems)} thing(s) to fix:\n")
    for p in problems:
        print(f"  - {p}")
    print("\nUpdate the files above, then rebuild the index:")
    print("  python -m src.build_index")
    sys.exit(1)


if __name__ == "__main__":
    main()
