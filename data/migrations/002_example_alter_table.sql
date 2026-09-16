-- Worked example: changing an existing table.
-- Adds a work location column to employees.
--
-- Apply with:
--   python -m scripts.apply_migration data/migrations/002_example_alter_table.sql
-- Then add the column to the table in schema_docs/tables/employees.md and run
--   python -m scripts.check_schema_sync
--   python -m src.build_index

ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS work_location TEXT;

-- Backfill something sensible so the column isn't entirely NULL.
UPDATE employees
SET work_location = CASE (employee_id % 3)
    WHEN 0 THEN 'Remote'
    WHEN 1 THEN 'Bengaluru'
    ELSE 'Kochi'
END
WHERE work_location IS NULL;
