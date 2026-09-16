# Setup Guide

One document, start to finish: what you need installed, every command in the
order it has to run and why, how to use the system day to day, and how to
point it at your own data instead of the synthetic demo dataset.

`README.md` describes the architecture and design decisions. This document
is the runbook — if you just want to get it running or change something,
start here.

---

## 1. What you need installed

| Tool | Why this project needs it |
|---|---|
| **Docker Desktop** (or Docker Engine + Compose on Linux) | Runs PostgreSQL in an isolated container with a fixed, known configuration. You don't install or configure Postgres by hand, and it can't collide with a Postgres you already have for something else. |
| **Ollama**, with `llama3.2:1b` pulled | Runs the language model that turns your question into SQL — entirely on your machine, no API key, no per-request cost, no data leaving your computer. `llama3.2:1b` was chosen specifically because it's small enough to run on 8GB of RAM. |
| **Python 3.10+** | Runs the actual pipeline: retrieval, prompt building, SQL validation, query execution, the evaluation harness, and the Flask web UI. |

Check what you already have:

```powershell
docker --version
docker compose version
ollama --version
python --version
```

If `docker compose version` fails but `docker --version` works, you have an
old standalone `docker-compose` — install Docker Desktop instead, it bundles
the newer `compose` subcommand this guide uses.

---

## 2. Setup, in order

Each step depends on the one before it — they're listed in the order they
have to happen, with the reason why.

### Step 1 — Unzip the project

```powershell
cd D:\                                          # wherever you keep projects
Expand-Archive llm-sql-analyst.zip -DestinationPath D:\ -Force
cd D:\llm-sql-analyst
```

Everything else in this guide is run from inside this folder.

### Step 2 — Create a Python environment and install dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Why first:** an isolated environment means this project's exact dependency
versions (Flask, pandas, psycopg2, sqlglot, requests) don't collide with
anything else on your machine, and don't silently break if you update
something else later.

### Step 3 — Create your `.env` file

```powershell
copy .env.example .env
```

**Why:** `config.py` reads this file for the database connection string and
the Ollama model names. The defaults already match `docker-compose.yml`
exactly, so there's nothing to edit yet — but this has to exist before any
Python script that imports `config` will run.

### Step 4 — Start PostgreSQL

```powershell
docker compose up -d
docker exec llm_sql_analyst_db pg_isready -U llm_sql_user
```

Wait for `accepting connections` before continuing.

**Why now:** nothing downstream — creating tables, loading data, running
the app — can connect to a database that isn't running yet. This has to
come before every other data step.

### Step 5 — Create the tables

```powershell
docker cp data/init_db.sql llm_sql_analyst_db:/init_db.sql
docker exec -it llm_sql_analyst_db psql -U llm_sql_user -d llm_sql_analyst -f /init_db.sql
```

Verify:
```powershell
docker exec llm_sql_analyst_db psql -U llm_sql_user -d llm_sql_analyst -c "\dt"
```
Expect `departments` and `employees`.

**Why now:** the database exists (Step 4) but is empty — no tables. This
step runs `data/init_db.sql`, which defines the schema. Data can't be
loaded into tables that don't exist yet.

### Step 6 — Pull the embedding model

```powershell
ollama pull all-minilm
ollama list
```

Confirm both `llama3.2:1b` and `all-minilm` are listed.

**Why now, specifically before Step 8:** the index-build step calls this
exact model to turn each piece of documentation into a vector. If it isn't
pulled yet, that step fails immediately.

### Step 7 — Load data

```powershell
python -m data.generate_seed_data
```
Expect: `Inserted 6 departments and 900 employees.`

**Why now:** this is the synthetic HR dataset the validator and query
executor will actually query against. (Section 4 below covers loading your
own data instead.)

### Step 8 — Build the search index

```powershell
python -m src.build_index
```
Expect 16 lines ending with `Saved vector index -> ...`.

**Why now, and why last of the data steps:** this reads every file in
`schema_docs/` and embeds it using the model from Step 6, producing the
index the retriever searches at question time. **This step must be re-run
any time you edit anything in `schema_docs/`** — the index is a snapshot,
not a live view.

### Step 9 — Run the tests

```powershell
python -m pytest tests/ -v
```
Expect all tests to pass.

**Why:** confirms the offline-testable logic (SQL validation, chunking,
metrics, the web app's routes) is intact *before* you trust the live
system — a fast, no-dependency-on-Ollama sanity check.

### Step 10 — Launch it

```powershell
python app.py
```

Open **http://localhost:5000**. The status dot in the header should be
green. Ask a question.

**Why last:** the web app's `/api/ask` endpoint calls the full pipeline —
retrieval (needs Step 8), the LLM (needs Ollama running with the model from
the prerequisites), validation (needs Step 5's schema), and execution
(needs Step 7's data). It's the step that exercises everything before it.

### Step 11 — Run the evaluation harness (optional, but this is the point of the project)

Stop the web server first (`Ctrl+C`), or open a second terminal and repeat
Step 2's `cd` + `Activate.ps1` there:

```powershell
python -m evaluation.run_evaluation
python -m evaluation.consistency_check
```

Results land in `evaluation\results\`: `evaluation_results.csv`,
`semantic_failures.md`, `consistency_report.csv`.

---

## 3. Using it day to day

Steps 2, 3, 5, 6, 7, 8 are one-time. Coming back later:

```powershell
cd D:\llm-sql-analyst
docker compose up -d
.venv\Scripts\Activate.ps1
python app.py
```

Useful Docker commands:

| Command | What it does |
|---|---|
| `docker compose stop` | Stop the database, keep all data |
| `docker compose start` | Start it again |
| `docker compose logs -f` | Watch Postgres logs (Ctrl-C to exit) |
| `docker compose down` | Stop and remove the container (data survives, stored in a Docker volume) |
| `docker compose down -v` | Stop and **delete all data** — you'd redo Steps 5 and 7 |

Open a SQL shell any time:
```powershell
docker exec -it llm_sql_analyst_db psql -U llm_sql_user -d llm_sql_analyst
```
(`\dt` lists tables, `\d employees` describes one, `\q` quits.)

---

## 4. Using your own data instead of the synthetic dataset

Four options, from least to most involved.

### Option A — Regenerate the synthetic dataset

```powershell
python -m data.generate_seed_data
```
Clears both tables and reloads 900 fresh synthetic rows. Good for resetting
to a known state.

### Option B — Load your own CSV into the existing tables

Your CSV's header row must match the target table's column names exactly.

```powershell
python -m scripts.load_csv path\to\employees.csv employees
python -m scripts.load_csv path\to\employees.csv employees --truncate
```

`--truncate` empties the table first. The loader checks every column
against the real table *before* writing anything, and inserts in a single
transaction — a bad file fails cleanly instead of half-loading.

### Option C — Write SQL directly

```powershell
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

### Option D — Point the whole system at a different PostgreSQL database

Instead of the Docker container, you can connect this project to any
PostgreSQL database you already have — on your machine, a cloud instance,
wherever. Edit `.env`:

```
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<database>
```

Then re-run the setup from **Step 8 onward** (index build, tests, launch) —
but read Section 5 first. This is the part that's easy to get wrong:
pointing at a different database changes what tables/columns actually
exist, and the system has two separate places that need to agree on that.

**This project only supports PostgreSQL** (the code talks to it via
`psycopg2`). Pointing `DATABASE_URL` at MySQL, SQLite, or anything else
will not work without changing `src/db.py`.

---

## 5. Adding or changing tables — the part with a catch

Two different things need to know your schema, and only one of them
updates itself:

- **The SQL validator** reads the live database automatically, every time
  it runs (`src/db.py:get_schema_metadata()`, via `information_schema`).
  Change a table, and validation immediately reflects the new shape — no
  code change needed.
- **The language model** only knows what's written in `schema_docs/`. If
  you add a table or column without documenting it there, the model never
  learns it exists. It keeps writing queries against the old schema — and
  because those queries are often still syntactically valid, you get
  **confidently wrong answers**, not an obvious error.

So a schema change is always three steps, in this order:

### Step 1 — Change the database

Write a `.sql` file in `data\migrations\` and apply it:

```powershell
python -m scripts.apply_migration data\migrations\001_add_performance_reviews.sql
```

Runs the whole file in one transaction — if any statement fails, nothing
is committed, so a broken migration can't leave the schema half-changed.
Two worked examples ship in `data\migrations\`: one adds a new table, one
adds a column to `employees`.

### Step 2 — Document it

For a new table, add `schema_docs\tables\<table_name>.md`. Copy the shape
of `schema_docs\tables\employees.md`: a `## Table: <name>` heading, a
column table with plain-English descriptions, and notes on how it joins to
other tables. For a changed table, edit the existing file. Write it for a
reader who's never seen your database — a vague column description is the
single biggest cause of wrong SQL.

### Step 3 — Check and rebuild

```powershell
python -m scripts.check_schema_sync
python -m src.build_index
```

`check_schema_sync` compares the live database against `schema_docs\` and
tells you about: tables with no documentation, columns you forgot to write
down, docs describing a table that no longer exists, and an index that's
older than your docs. It exits non-zero on a problem.

Then rebuild the index so the model actually sees the update — this is the
step people forget, and the one that causes silent wrong answers if
skipped.

---

## 6. Switching models

Both the LLM and the embedding model are set in `.env`:

```
LLM_MODEL=llama3.2:1b
EMBEDDING_MODEL=all-minilm
```

To try a different model, pull it first, then update `.env`, then rebuild
the index (the embedding model in particular — the index is tied to
whichever model produced it):

```powershell
ollama pull <model-name>
# edit .env
python -m src.build_index
```

Keep RAM in mind — anything larger than `llama3.2:1b` will use noticeably
more memory, and on an 8GB machine that can mean closing other applications
while the model is loaded.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | Virtual environment not activated | `.venv\Scripts\Activate.ps1` |
| PowerShell rejects `<` for file redirection | `<` isn't a redirect operator in PowerShell | Use `docker cp` + `-f`, or `Get-Content file \| docker exec -i ...` |
| `connection refused` (port 5432) | Postgres container not up yet | `docker compose up -d`, then wait for `pg_isready` to say `accepting connections` |
| `port is already allocated` | A native Postgres is already using 5432 | Stop it, or remap the container to `5433:5432` in `docker-compose.yml` and update `.env` to match |
| `relation "employees" does not exist` | Step 5 (create tables) wasn't applied | Re-run Step 5 |
| "The vector index is missing" in the web UI | Step 8 (`build_index`) was never run, or failed partway | Run `python -m src.build_index` and watch the output for errors |
| `Ollama embedding request failed (500)` | Varies — could be Ollama not running, the model not pulled, or (rare) a genuinely oversized chunk | Check `ollama list`, check `ollama ps` for memory pressure, re-run — the embedder retries automatically on transient failures and now prints Ollama's actual error message |
| Everything is very slow / system freezes | 8GB RAM under pressure from Ollama + Docker + a browser | Close other apps, especially the browser, while running `evaluation.run_evaluation` |
| Web UI shows "database unreachable" / "Ollama unreachable" | Whichever service named isn't running | Check that specific service: `docker compose ps` or `ollama list` |

---

## 8. Full command reference

Everything in this guide, in one block, for copy-paste:

```powershell
# One-time setup
cd D:\llm-sql-analyst
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
docker exec llm_sql_analyst_db pg_isready -U llm_sql_user
docker cp data/init_db.sql llm_sql_analyst_db:/init_db.sql
docker exec -it llm_sql_analyst_db psql -U llm_sql_user -d llm_sql_analyst -f /init_db.sql
ollama pull all-minilm
python -m data.generate_seed_data
python -m src.build_index
python -m pytest tests/ -v

# Run it
python app.py

# Evaluate it (separate terminal, or after Ctrl+C)
python -m evaluation.run_evaluation
python -m evaluation.consistency_check

# Coming back later
cd D:\llm-sql-analyst
docker compose up -d
.venv\Scripts\Activate.ps1
python app.py
```
