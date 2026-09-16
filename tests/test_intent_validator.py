import pandas as pd

from src.intent_validator import (
    validate_question_intent,
    validate_result_shape,
)


def test_each_department_requires_group_by():
    question = "How many employees are currently working in each department?"

    sql = """
    SELECT d.department_name, COUNT(*) AS employee_count
    FROM employees e
    JOIN departments d
      ON e.department_id = d.department_id
    WHERE e.employment_status = 'Active'
    GROUP BY d.department_name
    """

    errors = validate_question_intent(question, sql)

    assert errors == []


def test_each_department_rejects_limit_one():
    question = "How many employees are currently working in each department?"

    sql = """
    SELECT d.department_name, COUNT(*) AS employee_count
    FROM employees e
    JOIN departments d
      ON e.department_id = d.department_id
    WHERE e.employment_status = 'Active'
    GROUP BY d.department_name
    ORDER BY employee_count DESC
    LIMIT 1
    """

    errors = validate_question_intent(question, sql)

    assert any("LIMIT 1" in error for error in errors)


def test_each_department_requires_active_filter():
    question = "How many employees are currently working in each department?"

    sql = """
    SELECT d.department_name, COUNT(*) AS employee_count
    FROM employees e
    JOIN departments d
      ON e.department_id = d.department_id
    GROUP BY d.department_name
    """

    errors = validate_question_intent(question, sql)

    assert any("employment_status" in error for error in errors)


def test_highest_department_allows_limit_one():
    question = "Which department currently has the highest headcount?"

    sql = """
    SELECT d.department_name, COUNT(*) AS headcount
    FROM employees e
    JOIN departments d
      ON e.department_id = d.department_id
    WHERE e.employment_status = 'Active'
    GROUP BY d.department_name
    ORDER BY headcount DESC
    LIMIT 1
    """

    errors = validate_question_intent(question, sql)

    assert errors == []


def test_result_shape_detects_single_row_for_each_department():
    question = "How many employees are currently working in each department?"

    dataframe = pd.DataFrame({
        "department_name": ["Human Resources"],
        "employee_count": [131],
    })

    errors = validate_result_shape(
        question,
        dataframe,
    )

    assert len(errors) == 1