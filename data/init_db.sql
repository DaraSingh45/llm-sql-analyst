DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS departments;

CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    department_name TEXT UNIQUE NOT NULL
);

CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(department_id),
    job_title TEXT NOT NULL,
    hire_date DATE NOT NULL,
    termination_date DATE,
    employment_status TEXT NOT NULL CHECK (employment_status IN ('Active', 'Terminated')),
    salary NUMERIC(10, 2) NOT NULL
);

CREATE INDEX idx_employees_department ON employees(department_id);
CREATE INDEX idx_employees_termination_date ON employees(termination_date);
