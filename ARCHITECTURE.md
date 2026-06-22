# Salary Management Backend — Architecture Diagrams

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT / BROWSER                         │
│                  (Frontend / Swagger UI / Tests)                │
└────────────────────────────┬────────────────────────────────────┘
                             │  HTTP (REST)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FASTAPI APP                              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │  /employees  │  │  /payroll    │  │  /analytics           │ │
│  │  Router      │  │  Router      │  │  Router               │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬────────────┘ │
│         │                 │                      │              │
│  ┌──────▼───────┐  ┌──────▼───────┐             │              │
│  │  Employee    │  │  Payroll     │             │              │
│  │  Service     │  │  Service     │             │              │
│  └──────┬───────┘  └──────┬───────┘             │              │
│         │                 │                      │              │
│  ┌──────▼─────────────────▼──────────────────────▼───────────┐ │
│  │               SQLAlchemy ORM (Sync / psycopg2)            │ │
│  └──────────────────────────────┬────────────────────────────┘ │
└─────────────────────────────────┼───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                         │
│                                                                 │
│   employees │ salary_contracts │ payroll_batches │             │
│             │                  │  payroll_records │            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Application Layer Structure

```
┌─────────────────────────────────────────────────┐
│                  HTTP Request                   │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              CORS Middleware                    │
│         (allow origins from .env)               │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│                  ROUTERS                        │
│  • Validate request via Pydantic schema         │
│  • Inject service via Depends()                 │
│  • Return response model                        │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│                 SERVICES                        │
│  • All business logic lives here                │
│  • Raise HTTPException on rule violations       │
│  • Call SQLAlchemy ORM / core queries           │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              DATABASE SESSION                   │
│  • get_db() yields Session per request          │
│  • Auto-closed after response                   │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│               PostgreSQL (psycopg2)             │
└─────────────────────────────────────────────────┘
```

---

## 3. Entity Relationship Diagram

```
┌──────────────────────────────┐
│           employees          │
├──────────────────────────────┤
│ PK  id              INTEGER  │
│     employee_id     VARCHAR  │◄──────────────────────────┐
│     first_name      VARCHAR  │                           │
│     last_name       VARCHAR  │                           │
│     email           VARCHAR  │                           │
│     department      VARCHAR  │                           │
│     country         VARCHAR  │                           │
│     is_active       BOOLEAN  │                           │
│     created_at      DATETIME │                           │
│     updated_at      DATETIME │                           │
└──────────────┬───────────────┘                           │
               │ 1                                         │
               │                                           │
        ┌──────┴──────┐                                    │
        │             │                                    │
        │ *           │ *                                  │
┌───────▼──────────┐  ┌────────────────────────┐          │
│  salary_contracts│  │    payroll_records     │          │
├──────────────────┤  ├────────────────────────┤          │
│ PK id  INTEGER   │  │ PK id        INTEGER   │          │
│ FK employee_id   │  │ FK batch_id  INTEGER──►┼──┐       │
│    base_salary   │  │ FK employee_id         │  │       │
│    allowances    │  │    base_salary_snapshot│  │       │
│    deductions    │  │    allowances_snapshot │  │       │
│    effective_from│  │    deductions_snapshot │  │       │
│    currency      │  │    net_salary_snapshot │  │       │
│    is_active     │  │    status   (ENUM)     │  │       │
│    created_at    │  │    paid_at             │  │       │
│    updated_at    │  └────────────────────────┘  │       │
└──────────────────┘                              │       │
                                                  │ 1     │
                                         ┌────────▼─────────────┐
                                         │    payroll_batches   │
                                         ├──────────────────────┤
                                         │ PK id     INTEGER    │
                                         │    pay_period_start  │
                                         │    pay_period_end    │
                                         │    status   (ENUM)   │
                                         │    processed_at      │
                                         │    created_at        │
                                         └──────────────────────┘
```

---

## 4. Payroll Batch State Machine

```
                    POST /payroll/batches
                           │
                           ▼
                    ┌─────────────┐
                    │ PROCESSING  │  ← batch created, records being inserted
                    └──────┬──────┘
                           │  bulk insert PayrollRecords (PENDING)
                           ▼
                    ┌─────────────┐
                    │    DRAFT    │  ← ready for review
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
   POST /batches/{id}/approve      (rejected / error)
              │                         │
              ▼                         ▼
       ┌────────────┐            ┌────────────┐
       │    PAID    │            │   FAILED   │
       └────────────┘            └────────────┘
   records → SUCCESS          records → FAILED
```

---

## 5. Request Flow — Run Payroll

```
Client                  Router              PayrollService          Database
  │                       │                       │                    │
  │  POST /payroll/batches│                       │                    │
  │──────────────────────►│                       │                    │
  │                       │  svc.run_payroll()    │                    │
  │                       │──────────────────────►│                    │
  │                       │                       │  check duplicate   │
  │                       │                       │───────────────────►│
  │                       │                       │◄───────────────────│
  │                       │                       │                    │
  │                       │                       │  INSERT batch      │
  │                       │                       │  (PROCESSING)      │
  │                       │                       │───────────────────►│
  │                       │                       │◄── batch.id ───────│
  │                       │                       │                    │
  │                       │                       │  SELECT active     │
  │                       │                       │  contracts         │
  │                       │                       │───────────────────►│
  │                       │                       │◄── contracts ──────│
  │                       │                       │                    │
  │                       │                       │  bulk INSERT       │
  │                       │                       │  payroll_records   │
  │                       │                       │  (2000/chunk)      │
  │                       │                       │───────────────────►│
  │                       │                       │                    │
  │                       │                       │  UPDATE batch      │
  │                       │                       │  status → DRAFT    │
  │                       │                       │───────────────────►│
  │                       │                       │    COMMIT          │
  │                       │                       │───────────────────►│
  │                       │◄── BatchSummary ───────│                    │
  │◄── 201 Created ───────│                       │                    │
```

---

## 6. Test Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     pytest session                      │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │  test_engine (session-scoped)                  │    │
│  │  • connects to salary_management_test DB       │    │
│  │  • Base.metadata.create_all() at start         │    │
│  │  • Base.metadata.drop_all() at end             │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │  db fixture (function-scoped)                  │    │
│  │  • opens connection                            │    │
│  │  • BEGIN outer transaction                     │    │
│  │  • yields Session                              │    │
│  │  • ROLLBACK after test ← no data persists      │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │  client fixture (function-scoped)              │    │
│  │  • creates FastAPI app                         │    │
│  │  • overrides get_db → test session             │    │
│  │  • yields TestClient                           │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

  service.commit() → SAVEPOINT release (not real commit)
  outer transaction stays open → rollback after test
```

---

## 7. Folder Structure

```
salary_management_backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py               ← create_app() factory
│   ├── config.py             ← Settings (pydantic-settings)
│   ├── database.py           ← engine, SessionLocal, get_db()
│   │
│   ├── models/
│   │   ├── base.py           ← DeclarativeBase, TimestampMixin
│   │   ├── employee.py
│   │   ├── salary_contract.py
│   │   ├── payroll_batch.py
│   │   └── payroll_record.py
│   │
│   ├── schemas/
│   │   ├── common.py         ← PaginatedResponse[T]
│   │   ├── employee.py
│   │   ├── salary_contract.py
│   │   ├── payroll.py
│   │   └── analytics.py
│   │
│   ├── routers/
│   │   ├── employees.py
│   │   ├── contracts.py
│   │   ├── payroll.py
│   │   └── analytics.py
│   │
│   └── services/
│       ├── employee_service.py
│       ├── contract_service.py
│       └── payroll_service.py
│
├── alembic/
│   ├── env.py
│   └── versions/
│
├── scripts/
│   └── seed.py               ← bulk insert 10k employees
│
├── tests/
│   └── conftest.py
│
├── .env
├── alembic.ini
├── pyproject.toml
├── DESIGN_NOTES.md
└── ARCHITECTURE.md
```
