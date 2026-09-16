## Example: Highest attrition department
Q: Which department had the highest attrition in 2024?
SQL:
SELECT d.department_name, COUNT(*) AS attrition_count
FROM employees e
JOIN departments d ON e.department_id = d.department_id
WHERE e.termination_date >= '2024-01-01' AND e.termination_date < '2025-01-01'
GROUP BY d.department_name
ORDER BY attrition_count DESC
LIMIT 1;

## Example: Monthly attrition trend
Q: What is the monthly attrition count for the Engineering department in 2024?
SQL:
SELECT DATE_TRUNC('month', e.termination_date)::date AS month, COUNT(*) AS attrition_count
FROM employees e
JOIN departments d ON e.department_id = d.department_id
WHERE d.department_name = 'Engineering'
  AND e.termination_date >= '2024-01-01' AND e.termination_date < '2025-01-01'
GROUP BY month
ORDER BY month;

## Example: Current headcount
Q: How many employees are currently active?
SQL:
SELECT COUNT(*) AS active_headcount
FROM employees
WHERE employment_status = 'Active';

## Example: Average salary by department
Q: What is the average salary by department?
SQL:
SELECT d.department_name, ROUND(AVG(e.salary), 2) AS avg_salary
FROM employees e
JOIN departments d ON e.department_id = d.department_id
GROUP BY d.department_name
ORDER BY avg_salary DESC;

## Example: Top paid active employees
Q: List the top 5 highest paid active employees.
SQL:
SELECT first_name, last_name, salary
FROM employees
WHERE employment_status = 'Active'
ORDER BY salary DESC
LIMIT 5;
