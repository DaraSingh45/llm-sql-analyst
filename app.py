"""
Web UI for the LLM SQL Analyst.

Run with:
    python app.py
then open http://localhost:5000

The UI deliberately shows the generated SQL and the validation verdict
alongside the answer -- the point of this project is that model output gets
inspected, not trusted on sight.
"""
import datetime
import decimal
import math
import traceback

import pandas as pd
from flask import Flask, jsonify, render_template, request

import config

app = Flask(__name__)


def _json_safe(value):
    """Convert pandas/psycopg2 values into something JSON can carry.

    NaN/NaT must become null: json.dumps happily writes a bare NaN literal,
    which is not valid JSON and makes JSON.parse throw in the browser. Any
    NULL in a query result would otherwise break the results table.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if pd.isna(value):  # catches NaT, pd.NA
            return None
    except (TypeError, ValueError):
        pass  # pd.isna raises on array-likes; those aren't null scalars
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def df_to_payload(df, max_rows=200):
    """Turn a DataFrame into {columns, rows, truncated, total_rows}."""
    if df is None:
        return {"columns": [], "rows": [], "truncated": False, "total_rows": 0}
    total = len(df)
    view = df.head(max_rows)
    return {
        "columns": [str(c) for c in view.columns],
        "rows": [[_json_safe(v) for v in row] for row in view.values.tolist()],
        "truncated": total > max_rows,
        "total_rows": total,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """Reports whether the database and Ollama are reachable, so the UI can
    tell the user what's actually broken instead of failing silently."""
    status = {
        "database": {"ok": False, "detail": None},
        "ollama": {"ok": False, "detail": None},
        "index": {"ok": config.VECTOR_INDEX_PATH.exists(), "detail": None},
        "model": config.LLM_MODEL,
    }

    try:
        from src import db

        schema = db.get_schema_metadata()
        counts = {}
        for table in schema:
            try:
                counts[table] = int(db.run_query(f'SELECT COUNT(*) AS n FROM "{table}"')["n"][0])
            except Exception:
                counts[table] = None
        status["database"]["ok"] = True
        status["database"]["detail"] = {"tables": counts}
    except Exception as e:
        status["database"]["detail"] = str(e)

    try:
        import requests

        r = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
        status["ollama"]["ok"] = True
        status["ollama"]["detail"] = {"models": names}
    except Exception as e:
        status["ollama"]["detail"] = str(e)

    if not status["index"]["ok"]:
        status["index"]["detail"] = "Vector index not built. Run: python -m src.build_index"

    return jsonify(status)


@app.route("/api/ask", methods=["POST"])
def api_ask():
    question = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Enter a question first."}), 400

    try:
        from src import pipeline

        result = pipeline.answer_question(question)
    except FileNotFoundError:
        return jsonify({
            "error": "The vector index is missing. Build it with: python -m src.build_index"
        }), 503
    except Exception as e:
        app.logger.error(traceback.format_exc())
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500

    return jsonify({
        "question": result.question,
        "status": result.status,
        "sql": result.sql,
        "reasons": result.reasons,
        "tables_used": sorted(result.validation_tables),
        "columns_used": sorted(result.validation_columns),
        "context_used": [
            {
                "type": c["metadata"].get("type"),
                "source": c["metadata"].get("source"),
                "score": round(c["score"], 3),
                "text": c["text"],
            }
            for c in result.context_used
        ],
        "result": df_to_payload(result.dataframe),
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
