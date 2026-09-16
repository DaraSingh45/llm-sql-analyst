import re

import sqlglot
from sqlglot import exp


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def _has_group_by(parsed) -> bool:
    return parsed.args.get("group") is not None


def _has_limit(parsed) -> bool:
    return parsed.args.get("limit") is not None


def _get_limit_value(parsed):
    limit = parsed.args.get("limit")

    if limit is None:
        return None

    expression = limit.args.get("expression")

    if isinstance(expression, exp.Literal):
        try:
            return int(expression.this)
        except (TypeError, ValueError):
            return None

    return None


def _contains_active_filter(parsed) -> bool:
    for equality in parsed.find_all(exp.EQ):
        left = equality.left
        right = equality.right

        left_name = getattr(left, "name", "")
        left_name = str(left_name).lower()

        right_value = ""

        if isinstance(right, exp.Literal):
            right_value = str(right.this).lower()
        elif isinstance(right, exp.Identifier):
            right_value = str(right.this).lower()
        else:
            right_value = str(getattr(right, "this", right)).lower()

        if left_name == "employment_status" and right_value == "active":
            return True

    return False


def _contains_department_group(parsed) -> bool:
    if not _has_group_by(parsed):
        return False

    group = parsed.args.get("group")

    if group is None:
        return False

    for expression in group.expressions:
        if isinstance(expression, exp.Column):
            column_name = str(expression.name).lower()

            if column_name in {
                "department_name",
                "department_id",
            }:
                return True

    return False


def _contains_month_group(parsed) -> bool:
    if not _has_group_by(parsed):
        return False

    group = parsed.args.get("group")

    if group is None:
        return False

    group_sql = group.sql(dialect="postgres").lower()

    month_patterns = [
        "date_trunc('month'",
        'date_trunc("month"',
        "date_trunc(month",
    ]

    return any(pattern in group_sql for pattern in month_patterns)


def _contains_year_group(parsed) -> bool:
    if not _has_group_by(parsed):
        return False

    group = parsed.args.get("group")

    if group is None:
        return False

    group_sql = group.sql(dialect="postgres").lower()

    year_patterns = [
        "date_trunc('year'",
        'date_trunc("year"',
        "date_trunc(year",
    ]

    return any(pattern in group_sql for pattern in year_patterns)


def _contains_termination_date(parsed) -> bool:
    for column in parsed.find_all(exp.Column):
        if str(column.name).lower() == "termination_date":
            return True

    return False


def _question_requests_each_department(question: str) -> bool:
    patterns = [
        r"\beach department\b",
        r"\bevery department\b",
        r"\bby department\b",
        r"\bper department\b",
        r"\bfor each department\b",
        r"\bfor every department\b",
    ]

    return any(re.search(pattern, question) for pattern in patterns)


def _question_requests_each_month(question: str) -> bool:
    patterns = [
        r"\beach month\b",
        r"\bevery month\b",
        r"\bby month\b",
        r"\bper month\b",
        r"\bmonthly\b",
    ]

    return any(re.search(pattern, question) for pattern in patterns)


def _question_requests_each_year(question: str) -> bool:
    patterns = [
        r"\beach year\b",
        r"\bevery year\b",
        r"\bby year\b",
        r"\bper year\b",
        r"\byearly\b",
    ]

    return any(re.search(pattern, question) for pattern in patterns)


def _question_requests_ranking(question: str) -> bool:
    ranking_words = [
        "highest",
        "lowest",
        "top",
        "bottom",
        "maximum",
        "minimum",
        "largest",
        "smallest",
        "most",
        "least",
        "best",
        "worst",
        "rank",
        "ranking",
    ]

    return any(
        re.search(rf"\b{re.escape(word)}\b", question)
        for word in ranking_words
    )


def _question_requests_current_headcount(question: str) -> bool:
    headcount_terms = [
        "headcount",
        "currently working",
        "currently employed",
        "currently active",
        "active employees",
        "current employees",
        "employees currently",
    ]

    return any(term in question for term in headcount_terms)


def _question_requests_monthly_attrition(question: str) -> bool:
    return (
        "monthly attrition" in question
        or (
            "attrition" in question
            and _question_requests_each_month(question)
        )
    )


def _question_requests_yearly_grouping(question: str) -> bool:
    return _question_requests_each_year(question)


def validate_question_intent(question: str, sql: str):
    errors = []

    normalized_question = _normalize_question(question)

    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
    except Exception as exc:
        return [f"Unable to parse SQL for intent validation: {exc}"]

    requests_each_department = _question_requests_each_department(
        normalized_question
    )

    requests_ranking = _question_requests_ranking(
        normalized_question
    )

    requests_current_headcount = _question_requests_current_headcount(
        normalized_question
    )

    requests_monthly_attrition = _question_requests_monthly_attrition(
        normalized_question
    )

    requests_yearly_grouping = _question_requests_yearly_grouping(
        normalized_question
    )

    has_group_by = _has_group_by(parsed)
    has_limit = _has_limit(parsed)
    limit_value = _get_limit_value(parsed)

    if requests_each_department:
        if not has_group_by:
            errors.append(
                "The question asks for results for each department, "
                "but the SQL does not contain GROUP BY."
            )

        elif not _contains_department_group(parsed):
            errors.append(
                "The question asks for results for each department, "
                "but the SQL does not group by department."
            )

        if has_limit and limit_value == 1 and not requests_ranking:
            errors.append(
                "The question asks for every department, but the SQL "
                "uses LIMIT 1 and would return only one department."
            )

    if requests_current_headcount:
        if not _contains_active_filter(parsed):
            errors.append(
                "The question asks about current/active employees, "
                "but the SQL does not explicitly filter "
                "employment_status = 'Active'."
            )

    if requests_monthly_attrition:
        if not has_group_by:
            errors.append(
                "The question asks for monthly attrition, "
                "but the SQL does not contain GROUP BY."
            )

        if not _contains_month_group(parsed):
            errors.append(
                "The question asks for monthly attrition, "
                "but the SQL does not group by calendar month."
            )

        if not _contains_termination_date(parsed):
            errors.append(
                "The question asks about attrition, "
                "but the SQL does not reference termination_date."
            )

    if requests_yearly_grouping:
        if not has_group_by:
            errors.append(
                "The question asks for results by year, "
                "but the SQL does not contain GROUP BY."
            )

        if not _contains_year_group(parsed):
            errors.append(
                "The question asks for yearly results, "
                "but the SQL does not group by calendar year."
            )

    return errors


def validate_result_shape(question: str, result) -> list[str]:
    errors = []

    normalized_question = _normalize_question(question)

    requests_each_department = _question_requests_each_department(
        normalized_question
    )

    requests_each_month = _question_requests_each_month(
        normalized_question
    )

    requests_each_year = _question_requests_each_year(
        normalized_question
    )

    if result is None:
        return errors

    try:
        row_count = len(result)
    except TypeError:
        return errors

    if requests_each_department and row_count <= 1:
        errors.append(
            "The question asks for results for each department, "
            f"but the query returned only {row_count} row(s)."
        )

    if requests_each_month and row_count <= 1:
        errors.append(
            "The question asks for results by month, "
            f"but the query returned only {row_count} row(s)."
        )

    if requests_each_year and row_count <= 1:
        errors.append(
            "The question asks for results by year, "
            f"but the query returned only {row_count} row(s)."
        )

    return errors