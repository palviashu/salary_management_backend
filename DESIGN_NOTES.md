# Salary Management Backend — Design Notes

## Project Overview
REST API for an HR salary management system serving ~10,000 employees across multiple countries.
Built with **FastAPI + SQLAlchemy (sync) + PostgreSQL**.

---

## Architecture

```
app/
├── config.py        # Pydantic settings — reads .env
├── database.py      # SQLAlchemy engine + session factory
├── main.py          # App factory (create_app pattern)
├── models/          # SQLAlchemy ORM models
├── schemas/         # Pydantic request/response models
├── routers/         # FastAPI route handlers (thin layer)
└── services/        # Business logic
```

**Pattern:** Router → Service → DB.
Routers stay thin (just HTTP concerns). All business logic lives in service classes injected via `Depends`.

---

## Data Model

```
Employee
  └── SalaryContract  (one-to-many, one is_active at a time)
  └── PayrollRecord   (one per payroll batch)

PayrollBatch
  └── PayrollRecord   (one per employee per batch)
```

### Key Design Decisions

- `PayrollRecord` stores **salary snapshots** (`base_salary_snapshot`, `net_salary_snapshot`, etc.) —
  immutable audit trail so historical records are never affected by future contract changes.
- `SalaryContract.net_salary` is a computed `@property` (not a DB column) —
  always derived from `base + allowances - deductions`.
- Soft delete on `Employee` via `is_active` flag —
  `DELETE /employees/{id}` deactivates, not removes.
  A separate `DELETE /employees/{id}/permanent` does a hard delete.

---

## Payroll Lifecycle

```
POST /payroll/batches              → creates batch (DRAFT status)
GET  /payroll/batches/{id}         → review records + total payroll
POST /payroll/batches/{id}/approve → marks all records SUCCESS, batch → PAID
```

**Batch statuses:** `PROCESSING → DRAFT → PAID` (or `FAILED`)

Bulk insert uses `executemany` in 2,000-row chunks for performance (avoids ORM overhead for 10k records).

---

## API Surface

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET / POST | `/api/v1/employees` | List (paginated, filterable) + create |
| GET / PATCH / DELETE | `/api/v1/employees/{id}` | Read, update, deactivate |
| DELETE | `/api/v1/employees/{id}/permanent` | Hard delete |
| GET / POST | `/api/v1/payroll/batches` | List batches + run payroll |
| GET | `/api/v1/payroll/batches/{id}` | Batch detail + paginated records |
| POST | `/api/v1/payroll/batches/{id}/approve` | Approve batch |
| GET / POST | `/api/v1/contracts/*` | Salary contract management |
| GET | `/api/v1/analytics/dashboard` | Summary dashboard |
| GET | `/api/v1/analytics/by-department` | Breakdown by department |
| GET | `/api/v1/analytics/by-country` | Breakdown by country |
| GET | `/api/v1/analytics/salary-distribution` | Salary histogram buckets |

---

## Analytics Endpoints

All computed with raw SQLAlchemy aggregates (no ORM object loading):

- **Dashboard** — active/inactive counts, total & avg monthly payroll, latest batch status
- **By department / by country** — headcount, total net salary, avg net salary
- **Salary distribution** — bucketed histogram (< 30k, 30k–60k, 60k–90k, 90k–120k, 120k–150k, 150k–200k, > 200k)

---

## Key Technical Choices

| Decision | Rationale |
|----------|-----------|
| Sync SQLAlchemy (`psycopg2`) | Simpler stack; avoids greenlet/asyncpg complexity for CRUD-heavy workload |
| `asyncpg` only in seed script | Seed needs high-throughput bulk insert; app doesn't |
| `join_transaction_mode="create_savepoint"` in tests | Lets `session.commit()` in services work during tests without actually committing — full rollback after each test |
| `Numeric(12, 2)` for all money columns | Avoids float precision errors in salary calculations |
| Composite indexes on filter columns | `(department, country)`, `(batch_id, status)` for the most common query patterns |
| App factory pattern (`create_app()`) | Makes it easy to create isolated app instances in tests with overridden dependencies |

---

## Database Indexes

| Table | Index | Purpose |
|-------|-------|---------|
| employees | `(department, country)` | Filtered list queries |
| employees | `(last_name, first_name)` | Name search sorting |
| employees | `employee_id`, `is_active` | Lookup + active filter |
| salary_contracts | `(employee_id, is_active)` | Active contract lookup per employee |
| payroll_records | `(batch_id, status)` | Batch record queries |
| payroll_batches | `status` | Filter by batch status |

---

## Seed Script

`scripts/seed.py` generates 10,000 employees with realistic salaries:

- Uses `Faker` with fixed `seed(42)` — reproducible output
- Salary ranges defined per department, adjusted by country multiplier
- Uses `asyncpg` directly with `UNNEST` bulk inserts (2,000-row chunks)
- Idempotent via `ON CONFLICT DO NOTHING` on `employee_id`
- Expected runtime: under 10 seconds

**Run from project root:**
```bash
python scripts/seed.py
```

---

## Running the Project

```bash
# Start dev server
uvicorn app.main:app --reload

# Apply DB migrations
alembic upgrade head

# Generate new migration after model changes
alembic revision --autogenerate -m "description"

# Run tests
pytest

# Seed database
python scripts/seed.py
```

**API Docs:** http://127.0.0.1:8000/docs
**Health check:** http://127.0.0.1:8000/health

---

## Environment Variables (`.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Sync PostgreSQL URL (`postgresql+psycopg2://...`) |
| `ASYNC_DATABASE_URL` | Async PostgreSQL URL (`postgresql+asyncpg://...`) — used by seed script |
| `ALLOWED_ORIGINS` | CORS allowed origins (JSON list) |
| `DEBUG` | Set to `true` to log all SQL queries |
