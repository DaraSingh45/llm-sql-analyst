"""
Builds the RAG vector index from schema_docs/.
Run this once, and again whenever you edit the documentation.

Usage:
    python -m src.build_index
"""
import re
from pathlib import Path
import config
from src.embeddings import embed_text, VectorStore

# Small local embedding models cap the input they'll accept -- all-minilm
# (all-MiniLM-L6-v2) tops out around 256 tokens. Markdown tables are
# pipe/punctuation-heavy, so word count under-counts tokens badly: a
# 175-word table chunk was measured exceeding that 256-token limit in
# practice ("input length exceeds the context length"), a ratio of ~1.5
# tokens/word for that content. 85 words leaves real headroom under 256
# tokens even after the heading prefix (see chunk_markdown) is added back
# onto continuation pieces.
MAX_CHUNK_WORDS = 85


def _split_on_headers(text: str) -> list:
    parts = re.split(r"\n(?=## )", text)
    return [p.strip() for p in parts if p.strip()]


def _split_by_budget(chunk: str, max_words: int) -> list:
    """Split a chunk into pieces at or under max_words: prefer breaking on
    blank lines (paragraph boundaries), and fall back to line-by-line
    splitting for a single paragraph that's too big on its own (e.g. a
    markdown table with many rows and no blank lines inside it)."""
    if len(chunk.split()) <= max_words:
        return [chunk]

    paragraphs = [p for p in re.split(r"\n\s*\n", chunk) if p.strip()]
    pieces, current, current_words = [], [], 0

    def flush():
        if current:
            pieces.append("\n\n".join(current).strip())

    for para in paragraphs:
        para_words = len(para.split())

        if para_words > max_words:
            flush()
            current, current_words = [], 0
            line_buf, line_words = [], 0
            for line in para.split("\n"):
                w = len(line.split())
                if w > max_words:
                    # a single line is itself too big (e.g. one giant
                    # unbroken paragraph with no internal line breaks) --
                    # last resort: split it by words directly
                    if line_buf:
                        pieces.append("\n".join(line_buf).strip())
                        line_buf, line_words = [], 0
                    words = line.split()
                    for start in range(0, len(words), max_words):
                        pieces.append(" ".join(words[start:start + max_words]))
                    continue
                if line_buf and line_words + w > max_words:
                    pieces.append("\n".join(line_buf).strip())
                    line_buf, line_words = [], 0
                line_buf.append(line)
                line_words += w
            if line_buf:
                pieces.append("\n".join(line_buf).strip())
            continue

        if current and current_words + para_words > max_words:
            flush()
            current, current_words = [], 0
        current.append(para)
        current_words += para_words

    flush()
    return [p for p in pieces if p.strip()]


def chunk_markdown(path: Path, max_words: int = MAX_CHUNK_WORDS) -> list:
    """Split a markdown file into '## '-header sections, then further split
    any section too long for a small embedding model's context window.

    The heading is kept on every resulting piece (not just the first), so
    a chunk retrieved on its own -- e.g. just the tail rows of a table --
    still identifies which table/section it describes. The body is split
    against a budget with the heading's word count already reserved out of
    it, so the heading + body combination is *guaranteed* to fit under
    max_words -- rather than splitting the body first and hoping the
    heading, once added back, still happens to fit.

    Assumes headings themselves stay short (a handful of words, as every
    "## " heading in this project's docs does). An implausibly long heading
    (dozens of words) is not itself split, so it could still exceed
    max_words on its own -- real markdown headings don't do this.
    """
    text = path.read_text(encoding="utf-8")
    header_chunks = _split_on_headers(text) or [text.strip()]

    final_chunks = []
    for chunk in header_chunks:
        if len(chunk.split()) <= max_words:
            final_chunks.append(chunk)
            continue

        heading, _, body = chunk.partition("\n")
        body = body.lstrip("\n")
        continued_heading = f"{heading} (continued)"
        reserve = max(len(heading.split()), len(continued_heading.split()))
        body_budget = max(max_words - reserve, 20)  # floor: never shrink to nothing

        body_pieces = _split_by_budget(body, body_budget)
        final_chunks.append(f"{heading}\n{body_pieces[0]}")
        final_chunks.extend(f"{continued_heading}\n{p}" for p in body_pieces[1:])

    return final_chunks


def collect_documents():
    docs = []  # list of (doc_id, text, metadata)

    tables_dir = config.SCHEMA_DOCS_DIR / "tables"
    for md_file in sorted(tables_dir.glob("*.md")):
        for i, chunk in enumerate(chunk_markdown(md_file)):
            docs.append((f"table::{md_file.stem}::{i}", chunk, {"type": "schema", "source": md_file.name}))

    defs_file = config.SCHEMA_DOCS_DIR / "business_definitions.md"
    for i, chunk in enumerate(chunk_markdown(defs_file)):
        docs.append((f"definition::{i}", chunk, {"type": "definition", "source": defs_file.name}))

    examples_file = config.SCHEMA_DOCS_DIR / "example_qa.md"
    for i, chunk in enumerate(chunk_markdown(examples_file)):
        docs.append((f"example::{i}", chunk, {"type": "example", "source": examples_file.name}))

    return docs


def main():
    docs = collect_documents()
    store = VectorStore()
    print(f"Embedding {len(docs)} document chunks using '{config.EMBEDDING_MODEL}' via Ollama...")
    for doc_id, text, meta in docs:
        emb = embed_text(text)
        store.add(doc_id, text, emb, meta)
        print(f"  + {doc_id} ({meta['type']})")

    config.VECTOR_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    store.save(config.VECTOR_INDEX_PATH)
    print(f"Saved vector index -> {config.VECTOR_INDEX_PATH} ({len(docs)} chunks)")


if __name__ == "__main__":
    main()
