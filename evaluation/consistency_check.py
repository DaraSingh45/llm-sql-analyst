"""
Measures answer consistency: runs the same question through the pipeline
multiple times and checks whether the result is stable. Useful because LLM
output isn't fully deterministic even at low temperature.

Usage:
    python -m evaluation.consistency_check
"""
import json
import pandas as pd
import config
from src import pipeline
from evaluation import metrics

N_REPEATS = 3


def main():
    with open(config.EVAL_DATASET_PATH) as f:
        dataset = json.load(f)

    candidates = [item for item in dataset if not item.get("expect_fallback")][:5]
    rows = []

    for item in candidates:
        question = item["question"]
        results = [pipeline.answer_question(question) for _ in range(N_REPEATS)]
        dfs = [r.dataframe for r in results if r.status == "success"]

        if len(dfs) >= 2:
            base = metrics.normalize_df(dfs[0])
            consistent = all(metrics.normalize_df(df) == base for df in dfs[1:])
        else:
            consistent = False  # not even always executable => not consistent

        rows.append({
            "id": item["id"],
            "question": question,
            "successful_runs": len(dfs),
            "total_runs": N_REPEATS,
            "consistent": consistent,
        })

    df = pd.DataFrame(rows)
    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.EVAL_RESULTS_DIR / "consistency_report.csv", index=False)
    print(df.to_string(index=False))
    print(f"\nWrote -> {config.EVAL_RESULTS_DIR / 'consistency_report.csv'}")


if __name__ == "__main__":
    main()
