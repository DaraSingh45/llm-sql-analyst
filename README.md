# LLM SQL Analyst with Retrieval & Evaluation

A natural-language-to-SQL analytics system for a synthetic HR dataset.
Ask a question like *"Which department had the highest monthly attrition?"*
and it retrieves relevant schema docs, prompts a local LLM to write SQL,
validates that SQL before running it, executes it against PostgreSQL, and
falls back safely instead of blindly trusting the model.

Built to run entirely on-device: **Ollama (`llama3.2:1b`) + PostgreSQL**,
no cloud API keys, tuned for an low RAM machine.

## Architecture

```
question
   │
   ▼
[retriever.py] ── embeds question (Ollama "all-minilm") ─────┐
   │                                                          │
   │   cosine-similarity search over a small in-memory        │
   │   vector index built from schema_docs/ (build_index.py)  │
   ▼                                                          │
retrieved: relevant schema docs, business definitions, ◄──────┘
few-shot examples (NOT the whole DB schema every time)
   │
   ▼
[prompt_builder.py] ── assembles prompt with only relevant context
   │
   ▼
[llm.py] ── Ollama chat API ("llama3.2:1b") generates SQL
   │
   ▼
[sql_validator.py] ── checks: single SELECT only, no
   │                   INSERT/UPDATE/DELETE/DROP/etc, tables
   │                   and columns exist in the real schema,
   │                   syntax parses cleanly (sqlglot)
   │
   ├── invalid ──► retry once with the validator's error fed
   │                back to the model, then fall back
   │
   ▼ valid
[query_executor.py] ── runs SQL against PostgreSQL
   │
   ├── execution error ──► fallback, no crash
   ▼
result (pandas DataFrame) returned to the user
```

Fallback behavior triggers on: low-relevance retrieval (question doesn't
match the schema at all), the model explicitly saying `NO_QUERY: <reason>`,
SQL that fails validation after one retry, or a query that fails at
execution time. Nothing is executed on a hunch.

## Why this stack (given 8GB RAM)

- **No cloud API, no heavy ML libraries.** Everything goes through Ollama's
  local HTTP API (`requests`), so there's no `torch`/`transformers` install.
- **Embedding model: `all-minilm`** (~46MB) instead of a larger embedder —
  plenty for a handful of schema docs, and leaves headroom for `llama3.2:1b`
  (~1.3GB loaded) plus Postgres (~50-100MB) to run at the same time.
- **Vector store is just NumPy** (`src/embeddings.py:VectorStore`) — no
  FAISS/Chroma. The corpus here is a few dozen chunks; brute-force cosine
  similarity is instant and has zero extra dependencies.
- **Sequential, single-question processing** — no batching multiple
  questions through the LLM in parallel, to keep peak memory low.

If your machine is ever under memory pressure: close other apps before
running `evaluation/run_evaluation.py` (it calls the LLM once per question,
which is more sustained load than the interactive demo).

## Project layout

```
llm-sql-analyst/
├── app.py                     # web UI server (python app.py)
├── templates/index.html       # the web UI itself
├── config.py                  # central config (reads .env)
├── data/
│   ├── init_db.sql             # table definitions
│   ├── migrations/             # schema changes, applied in order
│   └── generate_seed_data.py   # synthetic HR data generator
├── schema_docs/                 # <-- the RAG corpus
│   ├── tables/*.md               (schema descriptions)
│   ├── business_definitions.md   (attrition, tenure, etc.)
│   └── example_qa.md             (few-shot NL -> SQL examples)
├── src/
│   ├── db.py                   # Postgres connection + schema introspection
│   ├── embeddings.py           # Ollama embeddings + VectorStore
│   ├── build_index.py          # builds the vector index from schema_docs/
│   ├── retriever.py            # retrieval + low-confidence detection
│   ├── prompt_builder.py       # assembles the LLM prompt
│   ├── llm.py                  # Ollama chat call (SQL generation)
│   ├── sql_validator.py        # pre-execution validation layer
│   ├── query_executor.py       # runs validated SQL
│   └── pipeline.py             # orchestrates the whole flow + fallbacks
├── evaluation/
│   ├── eval_dataset.json       # questions + hand-written "gold" SQL
│   ├── metrics.py               # execution success / correctness / etc.
│   ├── run_evaluation.py       # runs the dataset, writes results + report
│   └── consistency_check.py    # repeats questions, measures stability
├── scripts/
│   ├── setup_db.sh             # native-Postgres setup (not needed with Docker)
│   ├── run_demo.py             # interactive CLI
│   ├── load_csv.py             # load a CSV into a table
│   ├── apply_migration.py      # apply a .sql migration
│   └── check_schema_sync.py    # catches docs drifting from the real schema
└── tests/                       # unit tests for the validator + metrics
```

## Evaluation approach

`evaluation/eval_dataset.json` has ~12 questions, most with a hand-written
"gold" SQL query. `run_evaluation.py` runs each question through the full
pipeline and computes, per question and in aggregate:

- **Execution success** — did the generated SQL run without error?
- **Result correctness** — does the result match the gold query's result
  (values compared, not exact column names/order)?
- **Schema adherence** — does the generated query touch the same
  tables/columns as the gold query?
- **Fallback correctness** — for 3 deliberately unanswerable questions
  (ambiguous, a delete request, an out-of-scope question), did the system
  correctly refuse instead of guessing?

Any query that **executes successfully but returns the wrong result** is
written out separately to `evaluation/results/semantic_failures.md` — this
is the most important failure mode to catch, since "it ran" is not the same
as "it's right." `consistency_check.py` re-runs a sample of questions 3x
each to see how often the model gives a stable answer.

## Setup

See the exact commands at the end of the chat response this project was
generated in. Short version:

1. Install PostgreSQL (or `docker compose up -d`), create the DB, apply
   `data/init_db.sql`.
2. `pip install -r requirements.txt`, copy `.env.example` to `.env`.
3. `ollama pull all-minilm` (embeddings — you already have `llama3.2:1b`).
4. `python -m data.generate_seed_data` — loads synthetic HR data.
5. `python -m src.build_index` — embeds `schema_docs/` into the vector index.
6. `python app.py` — open <http://localhost:5000> and ask questions.
7. `python -m evaluation.run_evaluation` — run the evaluation harness.

## Using the web UI

```bash
python app.py
```

Then open <http://localhost:5000>. The page shows a health line telling you
if the database, Ollama, or the vector index isn't ready, so a blank result
is never a mystery.

Each question becomes a record in the log, colour-coded on its left edge:

| Edge | Meaning |
|---|---|
| Green | SQL passed validation, ran, and returned rows |
| Amber | The system declined to answer (ambiguous or out of scope) |
| Red | Validation blocked the SQL, or it failed while running |

The generated SQL is always shown, even when the query was blocked — seeing
the SQL the model *wanted* to run is the point. "Context retrieved for this
question" expands to show which schema chunks the retriever picked and their
similarity scores, which is how you debug a bad answer: usually the model
wasn't given the right documentation, not that it can't write SQL.

There's also a terminal interface if you prefer: `python -m scripts.run_demo`.

## Getting data into the database

Three ways, depending on what you have.

**1. Regenerate the synthetic dataset** (900 employees, fixed random seed):

```bash
python -m data.generate_seed_data
```

This clears both tables and reloads them, so it's a clean reset.

**2. Load your own CSV.** The CSV's header row must match the target table's
column names:

```bash
python -m scripts.load_csv path/to/employees.csv employees
python -m scripts.load_csv path/to/employees.csv employees --truncate
```

`--truncate` empties the table first. The loader checks your columns against
the real table before writing anything and inserts in a single transaction,
so a bad file fails without leaving half a load behind.

**3. Write SQL directly.** Open a shell inside the container:

```bash
docker exec -it llm_sql_analyst_db psql -U llm_sql_user -d llm_sql_analyst
```

```sql
INSERT INTO departments (department_name) VALUES ('Legal');

INSERT INTO employees
  (first_name, last_name, department_id, job_title, hire_date,
   termination_date, employment_status, salary)
VALUES
  ('Asha', 'Menon', 1, 'Data Analyst', '2023-04-01', NULL, 'Active', 92000);
```

`\dt` lists tables, `\d employees` describes one, `\q` quits.

## Adding or changing a table

This is the part with a catch. Two separate things need to know about your
schema:

- **The validator** reads the live database through
  `information_schema` every time it runs, so it picks up schema changes on
  its own. No code change needed.
- **The LLM** only knows what's in `schema_docs/`. If you add a table but
  don't document it, the model never learns the table exists — it keeps
  writing queries against the old schema, and you get confidently wrong
  answers rather than an obvious error.

So a schema change is always three steps: change the database, update the
docs, rebuild the index.

**Step 1 — change the database.** Write a `.sql` file in `data/migrations/`
and apply it. Two worked examples ship with the project:

```bash
# Adds a new performance_reviews table
python -m scripts.apply_migration data/migrations/001_add_performance_reviews.sql

# Adds a work_location column to employees
python -m scripts.apply_migration data/migrations/002_example_alter_table.sql
```

The whole file runs in one transaction — if any statement fails, nothing is
committed, so a broken migration can't half-apply.

**Step 2 — document it.** For a new table, add
`schema_docs/tables/<table_name>.md`. Copy the shape of
`schema_docs/tables/employees.md`: a `## Table: <name>` heading, a column
table with plain-English descriptions, and notes about how it joins to other
tables. For a changed table, edit the existing file. If the change introduces
a business concept ("what counts as a good review?"), add it to
`schema_docs/business_definitions.md`, and add a worked example to
`schema_docs/example_qa.md` if the new queries have a non-obvious shape.

Write these for a reader who has never seen your database. Vague column
descriptions are the single biggest cause of wrong SQL.

**Step 3 — check and rebuild.**

```bash
python -m scripts.check_schema_sync
python -m src.build_index
```

`check_schema_sync` compares the live database against `schema_docs/` and
tells you about tables with no documentation, columns you forgot to write
down, docs for tables that no longer exist, and an index that's older than
the docs. It exits non-zero on a problem, so you can wire it into CI.

Optionally, add questions covering the new table to
`evaluation/eval_dataset.json` with a hand-written `gold_sql`, then re-run
`python -m evaluation.run_evaluation` to see whether the model handles the
expanded schema.

## Known limitations (by design, documented rather than hidden)

- Column-existence checking in `sql_validator.py` checks a column name
  against the union of all tables' columns, not per-table — fine for this
  two-table schema, would need per-alias resolution for a larger schema.
- The seeded dataset is synthetic (see `data/generate_seed_data.py`) with a
  fixed random seed, so results are reproducible but not "real" HR data.
- `result_correctness` compares row values, ignoring column names/order —
  intentional, since an LLM may alias columns differently than the gold
  query while still being correct.
