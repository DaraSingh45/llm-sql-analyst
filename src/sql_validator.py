"""Strict read-only PostgreSQL SQL validation."""

import re

import sqlglot
from sqlglot import exp


DISALLOWED_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "copy",
}


class ValidationResult:
    def __init__(
        self,
        is_valid,
        errors=None,
        tables=None,
        columns=None,
        sql=None,
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.tables = tables or set()
        self.columns = columns or set()
        self.sql = sql

    def __repr__(self):
        return (
            f"ValidationResult("
            f"is_valid={self.is_valid}, "
            f"errors={self.errors})"
        )


def _strip_code_fences(raw_sql: str) -> str:
    text = raw_sql.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().lower() in {"```sql", "```"}:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines)

    if text.lower().startswith("sql\n"):
        text = text[4:]

    return text.strip().rstrip(";").strip()


def _extract_schema_columns(schema):
    return {
        table.lower(): {column.lower() for column in columns}
        for table, columns in schema.items()
    }


def _collect_table_aliases(parsed):
    aliases = {}

    for table in parsed.find_all(exp.Table):
        table_name = table.name.lower()

        if table.alias:
            aliases[table.alias.lower()] = table_name

        aliases[table_name] = table_name

    return aliases


def validate(raw_sql: str, schema: dict) -> ValidationResult:
    sql = _strip_code_fences(raw_sql)

    if not sql:
        return ValidationResult(
            False,
            ["Empty SQL"],
            sql=sql,
        )

    tokens = set(
        re.findall(r"[a-zA-Z_]+", sql.lower())
    )

    disallowed = tokens & DISALLOWED_KEYWORDS

    if disallowed:
        return ValidationResult(
            False,
            [
                "Disallowed keyword(s) detected: "
                + ", ".join(sorted(disallowed))
            ],
            sql=sql,
        )

    try:
        statements = [
            statement
            for statement in sqlglot.parse(
                sql,
                read="postgres",
            )
            if statement is not None
        ]

    except Exception as exc:
        return ValidationResult(
            False,
            [f"Syntax error: {exc}"],
            sql=sql,
        )

    if len(statements) != 1:
        return ValidationResult(
            False,
            ["Query must contain exactly one statement"],
            sql=sql,
        )

    try:
        parsed = sqlglot.parse_one(
            sql,
            read="postgres",
        )

    except Exception as exc:
        return ValidationResult(
            False,
            [f"Syntax error: {exc}"],
            sql=sql,
        )

    if not isinstance(parsed, exp.Select):
        return ValidationResult(
            False,
            [
                "Only SELECT statements are allowed "
                f"(got {type(parsed).__name__})"
            ],
            sql=sql,
        )

    errors = []

    schema_columns = _extract_schema_columns(schema)

    cte_names = {
        cte.alias.lower()
        for cte in parsed.find_all(exp.CTE)
        if cte.alias
    }

    tables = {
        table.name.lower()
        for table in parsed.find_all(exp.Table)
    }

    unknown_tables = (
        tables
        - set(schema_columns.keys())
        - cte_names
    )

    if unknown_tables:
        errors.append(
            "Unknown table(s): "
            + ", ".join(sorted(unknown_tables))
        )

    table_aliases = _collect_table_aliases(parsed)

    known_output_aliases = set()

    for select in parsed.find_all(exp.Select):
        for expression in select.expressions:
            if expression.alias:
                known_output_aliases.add(
                    expression.alias.lower()
                )

    columns = {
        column.name.lower()
        for column in parsed.find_all(exp.Column)
        if column.name
    }

    for column in parsed.find_all(exp.Column):
        column_name = column.name.lower()

        if column_name in known_output_aliases:
            continue

        qualifier = (
            column.table.lower()
            if column.table
            else None
        )

        if qualifier:
            actual_table = table_aliases.get(qualifier)

            if actual_table in schema_columns:
                if (
                    column_name
                    not in schema_columns[actual_table]
                ):
                    errors.append(
                        f"Unknown column '{column.name}' "
                        f"for table '{actual_table}'"
                    )

            elif qualifier in cte_names:
                continue

            else:
                errors.append(
                    f"Unknown table/alias qualifier '{column.table}' "
                    f"for column '{column.name}'"
                )

        else:
            matching_tables = [
                table
                for table, table_columns in schema_columns.items()
                if column_name in table_columns
            ]

            if not matching_tables:
                errors.append(
                    f"Unknown column(s) referenced: {column.name}"
                )

    if not parsed.expressions:
        errors.append(
            "Query does not select any columns or expressions"
        )

    errors = list(dict.fromkeys(errors))

    return ValidationResult(
        is_valid=not errors,
        errors=errors,
        tables=tables,
        columns=columns,
        sql=sql,
    )