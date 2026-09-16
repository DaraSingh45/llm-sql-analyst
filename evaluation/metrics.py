"""Metric functions used by run_evaluation.py"""
import pandas as pd


def execution_success(status: str) -> bool:
    return status == "success"


def normalize_df(df: pd.DataFrame) -> list:
    """Turn a DataFrame into a sorted list of row-tuples (values only, ignoring
    column names/order) so results can be compared even if the LLM aliases
    columns differently than the gold query."""
    if df is None or df.empty:
        return []
    normalized = []
    for row in df.values.tolist():
        norm_row = tuple(round(v, 2) if isinstance(v, (int, float)) else str(v) for v in row)
        normalized.append(norm_row)
    return sorted(normalized, key=lambda r: str(r))


def result_correctness(actual_df: pd.DataFrame, expected_df: pd.DataFrame) -> bool:
    return normalize_df(actual_df) == normalize_df(expected_df)


def schema_adherence(used_tables: set, used_columns: set, gold_tables: set, gold_columns: set) -> float:
    """Fraction of gold tables/columns that also appear in the generated query.
    1.0 = generated query touches exactly the same tables/columns as the gold query."""
    gold_all = gold_tables | gold_columns
    if not gold_all:
        return 1.0
    used_all = used_tables | used_columns
    overlap = len(gold_all & used_all)
    return round(overlap / len(gold_all), 2)


def fallback_correct(status: str, expect_fallback: bool) -> bool:
    is_fallback = status != "success"
    return is_fallback == expect_fallback
