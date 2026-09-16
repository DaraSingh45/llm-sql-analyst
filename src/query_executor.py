"""Safe execution layer for validated read-only SQL."""

from dataclasses import dataclass

import pandas as pd

from src import db


@dataclass
class ExecutionResult:
    success: bool
    dataframe: pd.DataFrame = None
    error: str = None


def execute(sql: str) -> ExecutionResult:
    try:
        dataframe = db.run_query(sql)

        return ExecutionResult(
            success=True,
            dataframe=dataframe,
        )

    except Exception as exc:
        return ExecutionResult(
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )