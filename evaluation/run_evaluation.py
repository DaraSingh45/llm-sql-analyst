"""
Runs the full evaluation dataset through the pipeline and measures:
  - SQL execution success
  - result correctness vs. a hand-written "gold" query
  - schema adherence (tables/columns touched vs. the gold query)
  - fallback correctness (did we correctly refuse ambiguous / unsupported asks)

Also flags "semantically incorrect but syntactically valid" cases: the model
produced SQL that ran successfully but returned the wrong answer. These are
saved separately for documentation -- the failure mode that's easiest to
miss without an evaluation harness.

Usage:
    python -m evaluation.run_evaluation
"""
import json
import pandas as pd

import config
from src import pipeline, sql_validator, db
from evaluation import metrics


def load_dataset():
    with open(config.EVAL_DATASET_PATH) as f:
        return json.load(f)


def get_gold_result_and_refs(gold_sql, schema):
    gold_df = db.run_query(gold_sql)
    gold_validation = sql_validator.validate(gold_sql, schema)
    return gold_df, gold_validation.tables, gold_validation.columns


def main():
    dataset = load_dataset()
    schema = db.get_schema_metadata()
    rows = []
    semantic_failures = []

    for item in dataset:
        question = item["question"]
        expect_fallback = item.get("expect_fallback", False)
        gold_sql = item.get("gold_sql")

        result = pipeline.answer_question(question)

        row = {
            "id": item["id"],
            "category": item.get("category"),
            "question": question,
            "expect_fallback": expect_fallback,
            "status": result.status,
            "generated_sql": result.sql,
            "fallback_correct": metrics.fallback_correct(result.status, expect_fallback),
            "execution_success": metrics.execution_success(result.status),
            "result_correct": None,
            "schema_adherence": None,
        }

        if not expect_fallback and gold_sql:
            gold_df, gold_tables, gold_columns = get_gold_result_and_refs(gold_sql, schema)
            row["schema_adherence"] = metrics.schema_adherence(
                result.validation_tables, result.validation_columns, gold_tables, gold_columns
            )
            if result.status == "success":
                correct = metrics.result_correctness(result.dataframe, gold_df)
                row["result_correct"] = correct
                if not correct:
                    semantic_failures.append({
                        "id": item["id"],
                        "question": question,
                        "generated_sql": result.sql,
                        "gold_sql": gold_sql,
                        "generated_result_preview": result.dataframe.head(5).to_dict(orient="records"),
                        "expected_result_preview": gold_df.head(5).to_dict(orient="records"),
                    })

        rows.append(row)

    results_df = pd.DataFrame(rows)
    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(config.EVAL_RESULTS_DIR / "evaluation_results.csv", index=False)

    n = len(results_df)
    fallback_acc = results_df["fallback_correct"].mean()
    non_fallback = results_df[~results_df["expect_fallback"]]
    exec_rate = non_fallback["execution_success"].mean() if len(non_fallback) else float("nan")
    correctness_rate = (
        non_fallback["result_correct"].dropna().mean()
        if non_fallback["result_correct"].notna().any() else float("nan")
    )
    avg_schema_adherence = (
        non_fallback["schema_adherence"].dropna().mean()
        if non_fallback["schema_adherence"].notna().any() else float("nan")
    )

    print("\n=== Evaluation summary ===")
    print(f"Total questions:              {n}")
    print(f"Fallback handling accuracy:   {fallback_acc:.0%}")
    print(f"SQL execution success rate:   {exec_rate:.0%}")
    print(f"Result correctness rate:      {correctness_rate:.0%}")
    print(f"Avg. schema adherence:        {avg_schema_adherence:.2f}")
    print(f"Semantically incorrect (but ran successfully): {len(semantic_failures)}")

    if semantic_failures:
        report_path = config.EVAL_RESULTS_DIR / "semantic_failures.md"
        with open(report_path, "w") as f:
            f.write("# Syntactically valid but semantically incorrect SQL\n\n")
            f.write(
                "These queries executed without error but returned a different "
                "result than the hand-written gold query -- a reminder that "
                "execution success alone does not mean the answer is correct.\n\n"
            )
            for case in semantic_failures:
                f.write(f"## {case['id']}: {case['question']}\n\n")
                f.write(f"**Generated SQL:**\n```sql\n{case['generated_sql']}\n```\n\n")
                f.write(f"**Gold SQL:**\n```sql\n{case['gold_sql']}\n```\n\n")
                f.write(f"**Generated result (preview):** {case['generated_result_preview']}\n\n")
                f.write(f"**Expected result (preview):** {case['expected_result_preview']}\n\n---\n\n")
        print(f"Wrote failure examples -> {report_path}")

    print(f"Wrote full results -> {config.EVAL_RESULTS_DIR / 'evaluation_results.csv'}")


if __name__ == "__main__":
    main()
