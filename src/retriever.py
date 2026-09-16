"""Retrieves the most relevant schema docs / definitions / examples for a question."""
import config
from src.embeddings import embed_text, VectorStore

_store_cache = None


def _get_store():
    global _store_cache
    if _store_cache is None:
        _store_cache = VectorStore.load(config.VECTOR_INDEX_PATH)
    return _store_cache


def retrieve_context(question: str, top_k: int = None):
    top_k = top_k or config.TOP_K_RETRIEVAL
    store = _get_store()
    q_emb = embed_text(question)
    return store.search(q_emb, top_k=top_k)


def is_low_confidence(results) -> bool:
    """If the best retrieval score is below threshold, the question is likely
    unrelated to the schema / too ambiguous to answer safely -- this feeds
    the pipeline's fallback behavior instead of blindly forwarding it to the LLM."""
    if not results:
        return True
    return results[0]["score"] < config.RETRIEVAL_MIN_SCORE
