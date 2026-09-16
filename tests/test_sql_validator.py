from src.sql_validator import validate

SCHEMA = {
    "employees": ["employee_id", "first_name", "last_name", "department_id", "salary",
                  "termination_date", "employment_status", "hire_date", "job_title"],
    "departments": ["department_id", "department_name"],
}


def test_valid_select_passes():
    sql = "SELECT first_name, last_name FROM employees WHERE employment_status = 'Active'"
    result = validate(sql, SCHEMA)
    assert result.is_valid, result.errors


def test_rejects_non_select():
    sql = "DELETE FROM employees WHERE employee_id = 1"
    result = validate(sql, SCHEMA)
    assert not result.is_valid


def test_rejects_unknown_table():
    sql = "SELECT * FROM salaries_history"
    result = validate(sql, SCHEMA)
    assert not result.is_valid
    assert any("Unknown table" in e for e in result.errors)


def test_rejects_unknown_column():
    sql = "SELECT ssn FROM employees"
    result = validate(sql, SCHEMA)
    assert not result.is_valid
    assert any("Unknown column" in e for e in result.errors)


def test_rejects_multiple_statements():
    sql = "SELECT * FROM employees; DROP TABLE employees;"
    result = validate(sql, SCHEMA)
    assert not result.is_valid


def test_strips_code_fences():
    sql = "```sql\nSELECT department_id FROM employees\n```"
    result = validate(sql, SCHEMA)
    assert result.is_valid, result.errors


def test_allows_group_by_and_order_by_on_output_alias():
    sql = ("SELECT department_id, COUNT(*) AS attrition_count FROM employees "
           "GROUP BY department_id ORDER BY attrition_count DESC")
    result = validate(sql, SCHEMA)
    assert result.is_valid, result.errors


def test_allows_ctes_and_their_output_columns():
    sql = (
        "WITH t AS (SELECT COUNT(*) AS cnt FROM employees) "
        "SELECT cnt FROM t"
    )
    result = validate(sql, SCHEMA)
    assert result.is_valid, result.errors


def test_bare_unaliased_column_still_checked_against_schema():
    # Regression guard: alias detection must not accidentally treat every
    # un-aliased SELECT column as a "known alias" (that would defeat the
    # unknown-column check entirely).
    sql = "SELECT ssn FROM employees"
    result = validate(sql, SCHEMA)
    assert not result.is_valid
    assert any("Unknown column" in e for e in result.errors)
