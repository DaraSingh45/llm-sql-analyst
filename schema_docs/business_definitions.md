## Definition: Attrition
An employee "attrites" (leaves the company) on their termination_date. An
attrition event is counted in whichever month/year termination_date falls in.

## Definition: Monthly attrition
The count of employees whose termination_date falls within a given calendar
month. Typically computed with DATE_TRUNC('month', termination_date).

## Definition: Attrition rate
For a given period: (number of employees terminated during the period) /
(number of employees active at the start of the period). Expressed as a
percentage.

## Definition: Headcount
The count of employees with employment_status = 'Active' as of a given date
(or as of "today" if no date is specified).

## Definition: Tenure
For an employee, tenure = termination_date - hire_date (for terminated
employees) or CURRENT_DATE - hire_date (for active employees), usually
expressed in years.

## Definition: Active employee
An employee with termination_date IS NULL and employment_status = 'Active'.
