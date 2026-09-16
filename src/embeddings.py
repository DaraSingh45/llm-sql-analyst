"""
Embedding client (via local Ollama) + a minimal in-memory vector store.

We deliberately avoid FAISS/Chroma/sentence-transformers here: the corpus is
small (schema docs + business definitions + a handful of examples), so a
plain numpy cosine-similarity search is enough and keeps the dependency
footprint (and RAM usage) tiny -- important on an 8GB machine that's also
running Ollama.
"""
import pickle
import time

import numpy as np
import requests
import config


def embed_text(text: str, max_retries: int = 3) -> np.ndarray:
    """Get an embedding vector for text via a local Ollama embedding model.

    Retries on failure: local model servers can briefly 500 right after a
    model finishes cold-loading (a request landing while the runtime is
    still settling), even though the exact same call succeeds a moment
    later. Retrying is cheap and turns that transient failure into a
    non-issue instead of aborting the whole indexing run.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                f"{config.OLLAMA_HOST}/api/embeddings",
                json={"model": config.EMBEDDING_MODEL, "prompt": text},
                timeout=60,
            )
        except requests.exceptions.ConnectionError as e:
            last_error = RuntimeError(
                f"Can't reach Ollama at {config.OLLAMA_HOST}. Is it running? ({e})"
            )
            break  # connection refused won't fix itself by retrying

        if resp.status_code == 200:
            return np.array(resp.json()["embedding"], dtype=np.float32)

        # Ollama's error responses carry a JSON body like {"error": "..."}
        # that names the real problem (model not loaded, out of memory,
        # unknown model name). A bare raise_for_status() hides that detail
        # behind a generic "500 Server Error", which isn't diagnosable.
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        last_error = RuntimeError(
            f"Ollama embedding request failed ({resp.status_code}) for model "
            f"'{config.EMBEDDING_MODEL}': {detail}"
        )
        if attempt < max_retries:
            print(f"  ! embedding attempt {attempt} failed ({detail}), retrying...")
            time.sleep(1.5 * attempt)

    raise last_error


class VectorStore:
    """A minimal in-memory vector store with cosine similarity search."""

    def __init__(self):
        self.ids = []
        self.texts = []
        self.metadatas = []
        self.embeddings = None  # np.ndarray, shape (n, dim)

    def add(self, doc_id: str, text: str, embedding: np.ndarray, metadata: dict):
        self.ids.append(doc_id)
        self.texts.append(text)
        self.metadatas.append(metadata)
        embedding = embedding.reshape(1, -1)
        self.embeddings = embedding if self.embeddings is None else np.vstack([self.embeddings, embedding])

    def search(self, query_embedding: np.ndarray, top_k: int = 4):
        if self.embeddings is None or len(self.ids) == 0:
            return []
        q = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        mat = self.embeddings / (np.linalg.norm(self.embeddings, axis=1, keepdims=True) + 1e-8)
        scores = mat @ q
        top_idx = np.argsort(-scores)[:top_k]
        return [
            {
                "id": self.ids[i],
                "text": self.texts[i],
                "metadata": self.metadatas[i],
                "score": float(scores[i]),
            }
            for i in top_idx
        ]

    def save(self, path):
        with open(str(path), "wb") as f:
            pickle.dump(
                {
                    "ids": self.ids,
                    "texts": self.texts,
                    "metadatas": self.metadatas,
                    "embeddings": self.embeddings,
                },
                f,
            )

    @classmethod
    def load(cls, path):
        with open(str(path), "rb") as f:
            data = pickle.load(f)
        store = cls()
        store.ids = data["ids"]
        store.texts = data["texts"]
        store.metadatas = data["metadatas"]
        store.embeddings = data["embeddings"]
        return store
