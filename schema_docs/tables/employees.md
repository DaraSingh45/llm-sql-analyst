## Table: employees
One row per employee, including current and past (terminated) employees.

| Column | Type | Description |
|---|---|---|
| employee_id | INTEGER (PK) | Unique identifier for the employee |
| first_name | TEXT | Employee's first name |
| last_name | TEXT | Employee's last name |
| department_id | INTEGER (FK -> departments.department_id) | Department the employee belongs to |
| job_title | TEXT | Job title, e.g. "Software Engineer", "Account Manager" |
| hire_date | DATE | Date the employee was hired |
| termination_date | DATE, nullable | Date the employee left the company. NULL means the employee is still active. |
| employment_status | TEXT | 'Active' or 'Terminated'. Kept in sync with termination_date. |
| salary | NUMERIC | Annual salary in USD |

Notes:
- To find active employees: `employment_status = 'Active'` (equivalently `termination_date IS NULL`).
- To find employees who left in a period: filter `termination_date` within that date range.
- Always JOIN employees to departments on department_id to get a human-readable department name.
