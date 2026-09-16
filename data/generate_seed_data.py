"""
Generates a synthetic HR dataset (departments + employees) and loads it into
PostgreSQL. Re-run any time to reset the demo data.

Usage:
    python -m data.generate_seed_data
"""
import random
from datetime import date, timedelta
import psycopg2
import config

random.seed(42)

DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Customer Support", "Finance", "Human Resources"]

JOB_TITLES = {
    "Engineering": ["Software Engineer", "Senior Software Engineer", "QA Engineer", "DevOps Engineer"],
    "Sales": ["Account Executive", "Sales Development Rep", "Sales Manager"],
    "Marketing": ["Marketing Specialist", "Content Strategist", "Marketing Manager"],
    "Customer Support": ["Support Agent", "Support Team Lead"],
    "Finance": ["Financial Analyst", "Accountant", "Finance Manager"],
    "Human Resources": ["HR Generalist", "Recruiter", "HR Manager"],
}

SALARY_RANGE = {
    "Engineering": (85000, 165000),
    "Sales": (55000, 130000),
    "Marketing": (55000, 115000),
    "Customer Support": (45000, 80000),
    "Finance": (60000, 125000),
    "Human Resources": (55000, 110000),
}

FIRST_NAMES = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David","Elizabeth",
               "William","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Charles","Karen",
               "Priya","Wei","Fatima","Carlos","Aisha","Hiro","Elena","Mohammed","Grace","Liam",
               "Noah","Olivia","Ava","Emma","Sophia","Mia","Ethan","Lucas","Amara","Kwame"]
LAST_NAMES = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
              "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin",
              "Patel","Chen","Khan","Nguyen","Kim","Silva","Kumar","Okafor","Rossi","Muller"]

START = date(2021, 1, 1)
END = date(2025, 9, 1)
N_EMPLOYEES = 900


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def build_rows():
    rows = []
    for _ in range(N_EMPLOYEES):
        dept = random.choice(DEPARTMENTS)
        hire = random_date(START, END - timedelta(days=30))

        # ~28% overall attrition, weighted so Sales & Customer Support churn more
        attrition_weight = {"Sales": 0.42, "Customer Support": 0.38}.get(dept, 0.20)
        terminated = random.random() < attrition_weight

        term_date = None
        status = "Active"
        if terminated:
            min_term = hire + timedelta(days=60)
            if min_term < END:
                term_date = random_date(min_term, END)
                status = "Terminated"

        title = random.choice(JOB_TITLES[dept])
        lo, hi = SALARY_RANGE[dept]
        salary = round(random.uniform(lo, hi), 2)

        rows.append((random.choice(FIRST_NAMES), random.choice(LAST_NAMES), dept, title, hire, term_date, status, salary))
    return rows


def main():
    conn = psycopg2.connect(config.DATABASE_URL)
    cur = conn.cursor()

    cur.execute("DELETE FROM employees;")
    cur.execute("DELETE FROM departments;")

    dept_ids = {}
    for name in DEPARTMENTS:
        cur.execute("INSERT INTO departments (department_name) VALUES (%s) RETURNING department_id;", (name,))
        dept_ids[name] = cur.fetchone()[0]

    rows = build_rows()
    for first, last, dept, title, hire, term, status, salary in rows:
        cur.execute(
            """
            INSERT INTO employees
                (first_name, last_name, department_id, job_title, hire_date,
                 termination_date, employment_status, salary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (first, last, dept_ids[dept], title, hire, term, status, salary),
        )

    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(DEPARTMENTS)} departments and {len(rows)} employees.")


if __name__ == "__main__":
    main()
