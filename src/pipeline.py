"""
Reliable end-to-end pipeline:

Question
-> RAG
-> Prompt
-> LLM
-> SQL validation
-> Intent validation
-> PostgreSQL
-> Result-shape validation
-> Final result
"""

from dataclasses import dataclass, field

import pandas as pd

from src import (
    retriever,
    prompt_builder,
    llm,
    sql_validator,
    intent_validator,
    query_executor,
    db,
)


MAX_RETRIES = 2


@dataclass
class PipelineResult:
    question: str
    status: str
    sql: str = None
    dataframe: pd.DataFrame = None
    reasons: list = field(default_factory=list)
    context_used: list = field(default_factory=list)
    validation_tables: set = field(default_factory=set)
    validation_columns: set = field(default_factory=set)


def _fallback(
    question,
    status,
    reasons,
    context,
    validation=None,
    sql=None,
    dataframe=None,
):
    return PipelineResult(
        question=question,
        status=status,
        sql=sql,
        dataframe=dataframe,
        reasons=reasons,
        context_used=context,
        validation_tables=validation.tables if validation else set(),
        validation_columns=validation.columns if validation else set(),
    )


def answer_question(question: str) -> PipelineResult:
    context = retriever.retrieve_context(question)

    if retriever.is_low_confidence(context):
        return _fallback(
            question,
            "fallback_ambiguous",
            ["No sufficiently relevant schema context was found."],
            context,
        )

    schema = db.get_schema_metadata()
    previous_error = None

    for attempt in range(MAX_RETRIES + 1):

        prompt = prompt_builder.build_prompt(
            question,
            context,
            previous_error=previous_error,
        )

        raw_output = llm.generate_sql(prompt)

        if raw_output.strip().upper().startswith("NO_QUERY"):
            return _fallback(
                question,
                "fallback_ambiguous",
                [raw_output.strip()],
                context,
            )

        validation = sql_validator.validate(
            raw_output,
            schema,
        )

        if not validation.is_valid:
            previous_error = "; ".join(validation.errors)

            if attempt == MAX_RETRIES:
                return _fallback(
                    question,
                    "fallback_invalid_sql",
                    validation.errors,
                    context,
                    validation=validation,
                    sql=validation.sql,
                )

            continue

        intent_errors = intent_validator.validate_question_intent(
            question,
            validation.sql,
        )

        if intent_errors:
            previous_error = "; ".join(intent_errors)

            if attempt == MAX_RETRIES:
                return _fallback(
                    question,
                    "fallback_semantic_mismatch",
                    intent_errors,
                    context,
                    validation=validation,
                    sql=validation.sql,
                )

            continue

        execution = query_executor.execute(validation.sql)

        if not execution.success:
            previous_error = (
                f"Database execution failed: {execution.error}"
            )

            if attempt == MAX_RETRIES:
                return _fallback(
                    question,
                    "fallback_execution_error",
                    [execution.error],
                    context,
                    validation=validation,
                    sql=validation.sql,
                )

            continue

        result_errors = intent_validator.validate_result_shape(
            question,
            execution.dataframe,
        )

        if result_errors:
            previous_error = "; ".join(result_errors)

            if attempt == MAX_RETRIES:
                return _fallback(
                    question,
                    "fallback_result_mismatch",
                    result_errors,
                    context,
                    validation=validation,
                    sql=validation.sql,
                    dataframe=execution.dataframe,
                )

            continue

        return PipelineResult(
            question=question,
            status="success",
            sql=validation.sql,
            dataframe=execution.dataframe,
            context_used=context,
            validation_tables=validation.tables,
            validation_columns=validation.columns,
        )

    return _fallback(
        question,
        "fallback_invalid_sql",
        ["Maximum validation attempts exceeded."],
        context,
    )