-- Worked example: adds a new table to the dataset.
-- Apply with:
--   python -m scripts.apply_migration data/migrations/001_add_performance_reviews.sql
-- Then document it in schema_docs/tables/performance_reviews.md and rebuild
-- the index, or the model won't know the table exists.

CREATE TABLE IF NOT EXISTS performance_reviews (
    review_id     SERIAL PRIMARY KEY,
    employee_id   INTEGER NOT NULL REFERENCES employees(employee_id),
    review_date   DATE NOT NULL,
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    reviewer_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_reviews_employee ON performance_reviews(employee_id);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON performance_reviews(review_date);
