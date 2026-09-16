"""
Interactive CLI demo.

Usage:
    python -m scripts.run_demo
"""
from src import pipeline


def main():
    print("LLM SQL Analyst -- type a question, or 'exit' to quit.\n")
    while True:
        question = input("Ask> ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        result = pipeline.answer_question(question)

        if result.status == "success":
            print(f"\nSQL:\n{result.sql}\n")
            print(result.dataframe.to_string(index=False))
        else:
            print(f"\n[{result.status}] Could not answer safely.")
            for r in result.reasons:
                print(f"  - {r}")
        print()


if __name__ == "__main__":
    main()
