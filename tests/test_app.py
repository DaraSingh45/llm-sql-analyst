import datetime
import decimal
import json

import pandas as pd

from app import app, df_to_payload


def test_payload_is_strict_json_safe():
    """Regression guard: NaN/NaT must become null. json.dumps emits a bare
    NaN literal otherwise, which JSON.parse rejects in the browser -- any
    NULL in a result would break the results table."""
    df = pd.DataFrame({
        "name": ["Sales", None],
        "amount": [decimal.Decimal("91234.56"), None],
        "day": [datetime.date(2024, 1, 1), pd.NaT],
    })
    payload = df_to_payload(df)
    json.dumps(payload, allow_nan=False)  # raises if NaN slipped through
    assert payload["rows"][1][0] is None
    assert payload["rows"][1][1] is None
    assert payload["rows"][1][2] is None


def test_payload_converts_types():
    df = pd.DataFrame({
        "amount": [decimal.Decimal("10.50")],
        "day": [datetime.date(2024, 3, 1)],
    })
    payload = df_to_payload(df)
    assert payload["rows"][0][0] == 10.5
    assert payload["rows"][0][1] == "2024-03-01"


def test_payload_truncates_large_results():
    payload = df_to_payload(pd.DataFrame({"n": range(500)}), max_rows=200)
    assert payload["truncated"] is True
    assert payload["total_rows"] == 500
    assert len(payload["rows"]) == 200


def test_payload_handles_none():
    assert df_to_payload(None)["rows"] == []


def test_index_page_renders():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SQL Analyst" in resp.get_data(as_text=True)


def test_empty_question_rejected():
    client = app.test_client()
    resp = client.post("/api/ask", json={"question": "   "})
    assert resp.status_code == 400


def test_status_endpoint_survives_missing_services():
    """/api/status must report what's down, not raise."""
    client = app.test_client()
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "database" in body and "ollama" in body and "index" in body
