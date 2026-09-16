"""
Regression coverage for the doc-chunking fix: a real chunk (the employees
table) once produced "input length exceeds the context length" from
all-minilm's 256-token limit, because chunking only split on '## ' headers
with no cap on how big a resulting section could get.
"""
import random
import tempfile
from pathlib import Path

from src.build_index import chunk_markdown, collect_documents, MAX_CHUNK_WORDS


def _write(text: str) -> Path:
    p = Path(tempfile.mktemp(suffix=".md"))
    p.write_text(text, encoding="utf-8")
    return p


def test_short_doc_is_not_needlessly_split():
    p = _write("## Table: small\nJust one short sentence.\n")
    chunks = chunk_markdown(p)
    assert len(chunks) == 1


def test_real_employees_doc_stays_under_budget():
    """The exact file and content that triggered the original failure."""
    chunks = chunk_markdown(Path("schema_docs/tables/employees.md"))
    assert len(chunks) > 1, "expected the real table to require splitting"
    assert all(len(c.split()) <= MAX_CHUNK_WORDS for c in chunks)


def test_split_pieces_keep_their_heading():
    """A chunk retrieved on its own must still say which table it describes --
    not just the first piece of a split section."""
    chunks = chunk_markdown(Path("schema_docs/tables/employees.md"))
    assert all("employees" in c.lower() for c in chunks)


def test_large_synthetic_table_all_pieces_under_budget():
    """Adversarial case well beyond anything in the real corpus."""
    synthetic = "## Table: giant\nDescription.\n\n" + "\n".join(
        f"| col_{i} | TEXT | some longer description text for column number {i} |"
        for i in range(30)
    )
    chunks = chunk_markdown(_write(synthetic))
    assert all(len(c.split()) <= MAX_CHUNK_WORDS for c in chunks)
    assert all("giant" in c.lower() for c in chunks)


def test_heading_reservation_holds_across_varying_line_lengths():
    """Regression guard: an earlier version of this fix split the body
    first and hoped the heading, once prepended, still fit -- it did for
    one table shape but a table with slightly different line lengths
    regrouped differently and pushed a piece back over budget. The budget
    must hold regardless of how lines happen to group."""
    for desc_suffix in ["", " here", " extra words here too"]:
        text = "## Table: giant\nDescription.\n\n" + "\n".join(
            f"| col_{i} | TEXT | some longer description text for column number {i}{desc_suffix} |"
            for i in range(30)
        )
        chunks = chunk_markdown(_write(text))
        assert all(len(c.split()) <= MAX_CHUNK_WORDS for c in chunks), desc_suffix


def test_budget_holds_under_randomized_table_shapes():
    """Fuzz check across randomized column counts and description lengths,
    fixed seed for reproducibility."""
    rng = random.Random(1)
    for _ in range(30):
        n_cols = rng.randint(1, 80)
        desc_len = rng.randint(1, 20)
        text = "## Table: fuzz\nDescription.\n\n" + "\n".join(
            f"| col_{i} | TEXT | " + " ".join(["word"] * desc_len) + " |" for i in range(n_cols)
        )
        chunks = chunk_markdown(_write(text))
        assert all(len(c.split()) <= MAX_CHUNK_WORDS for c in chunks), (n_cols, desc_len)


def test_full_corpus_never_exceeds_budget():
    docs = collect_documents()
    assert len(docs) > 0
    offenders = [(doc_id, len(text.split())) for doc_id, text, _ in docs if len(text.split()) > MAX_CHUNK_WORDS]
    assert not offenders, f"chunks over budget: {offenders}"
