import pandas as pd
from evaluation.metrics import result_correctness, schema_adherence, fallback_correct


def test_result_correctness_ignores_column_names_and_order():
    a = pd.DataFrame({"dept": ["Sales", "Engineering"], "n": [10, 5]})
    b = pd.DataFrame({"department_name": ["Engineering", "Sales"], "attrition_count": [5, 10]})
    assert result_correctness(a, b) is True


def test_result_correctness_detects_mismatch():
    a = pd.DataFrame({"dept": ["Sales"], "n": [10]})
    b = pd.DataFrame({"dept": ["Sales"], "n": [11]})
    assert result_correctness(a, b) is False


def test_schema_adherence_full_overlap():
    score = schema_adherence({"employees"}, {"salary"}, {"employees"}, {"salary"})
    assert score == 1.0


def test_fallback_correct():
    assert fallback_correct("fallback_ambiguous", True) is True
    assert fallback_correct("success", True) is False
