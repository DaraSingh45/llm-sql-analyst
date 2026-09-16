import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://llm_sql_user:llm_sql_pass@localhost:5432/llm_sql_analyst"
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-minilm")

TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", 6))
RETRIEVAL_MIN_SCORE = float(os.getenv("RETRIEVAL_MIN_SCORE", 0.18))

SCHEMA_DOCS_DIR = BASE_DIR / "schema_docs"
VECTOR_INDEX_PATH = BASE_DIR / os.getenv("VECTOR_INDEX_PATH", "outputs/vector_index.pkl")
EVAL_DATASET_PATH = BASE_DIR / "evaluation" / "eval_dataset.json"
EVAL_RESULTS_DIR = BASE_DIR / "evaluation" / "results"
