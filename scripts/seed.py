"""
Seed script: generates 10,000 realistic employees with salary contracts.

Usage (from backend/):
    python scripts/seed.py

Uses asyncpg directly (bypasses SQLAlchemy/greenlet) for maximum
compatibility and performance.

Design:
- Faker with fixed seed(42) for reproducibility
- Realistic salary ranges by department, adjusted by country multiplier
- COPY-style bulk insert via asyncpg executemany for speed
- Idempotent: ON CONFLICT DO NOTHING on employee_id
- Expected runtime: under 10 seconds for 10,000 employees + contracts
"""

import asyncio
import os
import random
import selectors
import sys
import time
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg
from faker import Faker

from app.config import settings

fake = Faker()
Faker.seed(42)
random.seed(42)

DEPARTMENTS = {
    "Engineering":  (80_000, 180_000),
    "Product":      (90_000, 160_000),
    "Sales":        (55_000, 120_000),
    "HR":           (50_000, 95_000),
    "Finance":      (70_000, 140_000),
    "Marketing":    (55_000, 110_000),
    "Operations":   (45_000, 100_000),
    "Legal":        (100_000, 200_000),
    "Design":       (65_000, 130_000),
    "Data Science": (85_000, 175_000),
}

COUNTRIES = {
    "United States":  1.00,
    "United Kingdom": 0.85,
    "Germany":        0.88,
    "Canada":         0.87,
    "Australia":      0.90,
    "India":          0.28,
    "Singapore":      0.92,
    "Netherlands":    0.86,
    "France":         0.82,
    "Brazil":         0.35,
}

COUNTRY_CURRENCIES = {
    "United States": "USD",
    "United Kingdom": "GBP",
    "Germany": "EUR",
    "Canada": "CAD",
    "Australia": "AUD",
    "India": "INR",
    "Singapore": "SGD",
    "Netherlands": "EUR",
    "France": "EUR",
    "Brazil": "BRL",
}

DEPT_LIST = list(DEPARTMENTS.keys())
COUNTRY_LIST = list(COUNTRIES.keys())
DEPT_WEIGHTS = [15, 12, 14, 8, 10, 10, 12, 5, 7, 7]


def _parse_async_url(url: str) -> dict:
    # postgresql+asyncpg://user:pass@host:port/dbname -> dict for asyncpg.connect
    url = url.replace("postgresql+asyncpg://", "")
    user_pass, rest = url.split("@", 1)
    user, password = user_pass.split(":", 1)
    host_port, dbname = rest.split("/", 1)
    if ":" in host_port:
        host, port = host_port.split(":", 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    return {"user": user, "password": password, "host": host, "port": port, "database": dbname}


def _salary(dept: str, country: str) -> tuple[float, float, float]:
    lo, hi = DEPARTMENTS[dept]
    multiplier = COUNTRIES[country]
    base = round(random.randint(lo, hi) * multiplier, 2)
    allowances = round(base * random.uniform(0.05, 0.15), 2)
    deductions = round(base * random.uniform(0.08, 0.20), 2)
    return base, allowances, deductions


def _random_date_in_past(years: int = 3) -> date:
    days_back = random.randint(30, years * 365)
    return date.today() - timedelta(days=days_back)


async def seed(n: int = 10_000) -> None:
    conn_args = _parse_async_url(settings.ASYNC_DATABASE_URL)
    conn = await asyncpg.connect(**conn_args)

    try:
        existing_count = await conn.fetchval("SELECT COUNT(*) FROM employees")
        print(f"Found {existing_count} existing employees")

        # Generate unique employee rows
        seen_ids: set[str] = set()
        seen_emails: set[str] = set()

        employee_rows = []
        attempts = 0
        while len(employee_rows) < n and attempts < n * 5:
            attempts += 1
            dept = random.choices(DEPT_LIST, weights=DEPT_WEIGHTS, k=1)[0]
            country = random.choice(COUNTRY_LIST)

            emp_id = f"EMP{random.randint(10000, 99999)}"
            if emp_id in seen_ids:
                continue

            email = fake.unique.email()
            if email in seen_emails:
                continue

            seen_ids.add(emp_id)
            seen_emails.add(email)

            employee_rows.append((
                emp_id,
                fake.first_name(),
                fake.last_name(),
                email,
                dept,
                country,
                True,
            ))

        print(f"Generated {len(employee_rows):,} employee records, inserting…")

        # Insert employees and get back their db ids + dept + country
        CHUNK = 2000
        inserted = []  # list of (db_id, dept, country)
        for i in range(0, len(employee_rows), CHUNK):
            chunk = employee_rows[i : i + CHUNK]
            rows = await conn.fetch(
                """
                INSERT INTO employees (employee_id, first_name, last_name, email, department, country, is_active)
                SELECT * FROM UNNEST($1::text[], $2::text[], $3::text[], $4::text[], $5::text[], $6::text[], $7::bool[])
                  AS t(employee_id, first_name, last_name, email, department, country, is_active)
                ON CONFLICT (employee_id) DO NOTHING
                RETURNING id, department, country
                """,
                [r[0] for r in chunk],
                [r[1] for r in chunk],
                [r[2] for r in chunk],
                [r[3] for r in chunk],
                [r[4] for r in chunk],
                [r[5] for r in chunk],
                [r[6] for r in chunk],
            )
            inserted.extend(rows)
            print(f"  employees: {min(i + CHUNK, len(employee_rows)):,}/{len(employee_rows):,}")

        # Build contracts for newly inserted employees
        contract_rows = []
        for row in inserted:
            emp_db_id, dept, country = row["id"], row["department"], row["country"]
            base, allowances, deductions = _salary(dept, country)
            currency = COUNTRY_CURRENCIES[country]
            contract_rows.append((
                emp_db_id,
                base,
                allowances,
                deductions,
                _random_date_in_past(),
                currency,
                True,
            ))

        print(f"Inserting {len(contract_rows):,} salary contracts…")
        for i in range(0, len(contract_rows), CHUNK):
            chunk = contract_rows[i : i + CHUNK]
            await conn.execute(
                """
                INSERT INTO salary_contracts
                  (employee_id, base_salary, allowances, deductions, effective_from, currency, is_active)
                SELECT * FROM UNNEST($1::int[], $2::numeric[], $3::numeric[], $4::numeric[],
                                     $5::date[], $6::text[], $7::bool[])
                  AS t(employee_id, base_salary, allowances, deductions, effective_from, currency, is_active)
                """,
                [r[0] for r in chunk],
                [r[1] for r in chunk],
                [r[2] for r in chunk],
                [r[3] for r in chunk],
                [r[4] for r in chunk],
                [r[5] for r in chunk],
                [r[6] for r in chunk],
            )
            print(f"  contracts: {min(i + CHUNK, len(contract_rows)):,}/{len(contract_rows):,}")

        final_count = await conn.fetchval("SELECT COUNT(*) FROM employees")
        print(f"\nDone. Total employees in DB: {final_count:,}")

    finally:
        await conn.close()


if __name__ == "__main__":
    start = time.perf_counter()
    # Python 3.14 on Windows defaults to ProactorEventLoop which is incompatible
    # with asyncpg's SSL negotiation. SelectorEventLoop works correctly.
    asyncio.run(
        seed(10_000),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
    elapsed = time.perf_counter() - start
    print(f"Elapsed: {elapsed:.1f}s")
