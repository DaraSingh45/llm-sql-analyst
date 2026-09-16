from unittest.mock import MagicMock, patch
import pytest
import requests as requests_module
from src.embeddings import embed_text


def _resp(status_code, error=None, embedding=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    if status_code == 200:
        r.json.return_value = {"embedding": embedding or [0.1, 0.2, 0.3]}
    elif error is not None:
        r.json.return_value = {"error": error}
    else:
        r.json.side_effect = ValueError("not json")
        r.text = text
    return r


def test_transient_failure_then_success_recovers_without_raising():
    """Reproduces the exact reported pattern: the call right after a model
    cold-loads briefly 500s, but the same request succeeds moments later.
    embed_text must retry through this rather than aborting the run."""
    calls = [_resp(500, error="model is still loading"), _resp(200)]
    with patch("src.embeddings.requests.post", side_effect=calls), \
         patch("src.embeddings.time.sleep"):  # skip the real backoff delay
        vec = embed_text("some markdown chunk")
    assert list(vec) == [pytest.approx(0.1), pytest.approx(0.2), pytest.approx(0.3)]


def test_persistent_failure_raises_with_ollama_detail_after_retries():
    calls = [_resp(500, error="out of memory")] * 3
    with patch("src.embeddings.requests.post", side_effect=calls), \
         patch("src.embeddings.time.sleep"):
        with pytest.raises(RuntimeError, match="out of memory"):
            embed_text("some text", max_retries=3)


def test_non_json_error_body_falls_back_to_raw_text():
    calls = [_resp(500, text="internal server error")] * 3
    with patch("src.embeddings.requests.post", side_effect=calls), \
         patch("src.embeddings.time.sleep"):
        with pytest.raises(RuntimeError, match="internal server error"):
            embed_text("some text", max_retries=3)


def test_connection_error_does_not_retry():
    """A refused connection won't fix itself by retrying -- fail fast with a
    clear 'is Ollama running?' message instead of waiting through 3 retries."""
    with patch("src.embeddings.requests.post",
               side_effect=requests_module.exceptions.ConnectionError("refused")):
        with pytest.raises(RuntimeError, match="Is it running"):
            embed_text("some text")


def test_success_on_first_try_returns_vector():
    with patch("src.embeddings.requests.post", return_value=_resp(200, embedding=[1.0, 2.0])):
        vec = embed_text("some text")
    assert list(vec) == [pytest.approx(1.0), pytest.approx(2.0)]
