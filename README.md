# Banking Transaction Reconciliation API

A bank receives a **daily transaction file**. This service imports the file (CSV or Excel), compares every record
with the transactions stored in **SQL Server**, and reports missing, mismatched and duplicate payments. A **React
dashboard** (`frontend/`) puts the whole workflow in the browser.

**Backend:** FastAPI · Pydantic · SQLAlchemy · SQL Server · Alembic · pandas · pytest
**Frontend:** React 19 · TypeScript · Vite · React Router · Recharts · Vitest
**Delivery:** Docker · Docker Compose · nginx · GitLab CI

> ⚠️ Learning project: use **synthetic data only**. Never load real customer records or banking credentials.
> All sample data in this repo is generated (`Synthetic Customer NNN`, fake `SYNT` bank code).

![Dashboard](docs/screenshots/frontend/02-dashboard.png)

---

## Features

| # | Requirement | Where |
|---|---|---|
| 1 | Import transactions from CSV or Excel | `app/services/importer.py` — pandas, header aliases, per-row validation with row numbers |
| 2 | Store transactions in SQL Server | `app/models.py`, Alembic migration `alembic/versions/0001_initial_schema.py` |
| 3 | Create / retrieve / update / search endpoints | `app/routers/transactions.py` |
| 4 | Detect duplicate transaction references | In-file duplicates on upload, `GET /imports/{id}/duplicates`, unique ledger reference (409 on conflict) |
| 5 | Compare amounts, dates, references, statuses | `app/services/reconciliation.py` (+ currency, account number, configurable tolerances) |
| 6 | Unmatched-transaction reports | `GET /reconciliations/{id}/report?format=json\|csv\|xlsx` |
| 7 | Logging, tests, authentication, API docs | Request-ID logging (text/JSON), 54 pytest + 16 Vitest tests, JWT + roles, Swagger/ReDoc |
| + | Web dashboard | `frontend/` — React app for uploads, reconciliation review, search and reports ([details](frontend/README.md)) |

### Reconciliation rules

Records are matched on **normalised reference** (trimmed, upper-cased). Each file record ends up in one category:

| Category | Meaning |
|---|---|
| `MATCHED` | Reference found; amount, date, status, currency and account agree (within tolerance) |
| `MISMATCHED` | Reference found but one or more fields differ — `mismatched_fields` / `details` say which |
| `MISSING_IN_DATABASE` | In the bank file, not in the ledger |
| `MISSING_IN_FILE` | In the ledger within the file's date range (or a custom period), not in the bank file |
| `DUPLICATE_IN_FILE` | Reference repeated in the file; the first occurrence is reconciled, the repeats are flagged |

Tolerances: `amount_tolerance` (e.g. `0.05`) and `date_tolerance_days` (e.g. `1`) per run, defaults from settings.

### Import format

Required columns: `reference`, `amount`, `transaction_date`, `status`. Optional: `account_number`, `customer_name`,
`currency` (default `USD`), `description`. Common header variants are accepted (`Txn Ref`, `Value Date`,
`Payment Status`, `IBAN`, …). Amounts like `1,250.00`, `$12`, `(45.10)` and dates like `2026-10-21`, `21/10/2026`
are parsed; status synonyms (`SETTLED`, `POSTED`, `DECLINED`, `REFUNDED`, …) map to
`PENDING | COMPLETED | FAILED | REVERSED`. Invalid rows are reported with their spreadsheet row number and never
stored.

### Roles

| Role | Can |
|---|---|
| `viewer` | Read transactions, imports, runs and reports |
| `analyst` | + upload files, run reconciliations, create/update transactions |
| `admin` | + create users |

---

## Screenshots — React dashboard

Captured from the production build talking to the real API, with three days of synthetic data. The day-21 file
was uploaded and reconciled through the UI.

**Sign in**

![Login](docs/screenshots/frontend/01-login.png)

**Upload the daily file** — validation summary, duplicate references, reconcile with optional tolerances/period

![Daily import](docs/screenshots/frontend/03-daily-import-upload.png)

**Reconciliation run** — category cards, donut, exceptions with file-vs-ledger values; differing fields highlighted

![Run](docs/screenshots/frontend/04-reconciliation-run.png)

**Filtered to mismatches**

![Mismatched](docs/screenshots/frontend/05-reconciliation-mismatched.png)

**Transactions** — search, sort, page; create and edit

![Transactions](docs/screenshots/frontend/06-transactions-search.png)

![Edit](docs/screenshots/frontend/07-edit-transaction.png)

**Import batch detail and duplicate references**

![Batch](docs/screenshots/frontend/08-import-batch-detail.png)

**Reconciliation history**

![History](docs/screenshots/frontend/09-reconciliation-history.png)

**User management (admin only)**

![Users](docs/screenshots/frontend/10-user-management.png)

**Responsive layout**

<img src="docs/screenshots/frontend/11-mobile-dashboard.png" width="320" alt="Mobile dashboard">

## Screenshots — API (Swagger UI)

Taken from a local run against the synthetic sample data (200 ledger rows, 204-row bank file).

![Swagger UI](docs/screenshots/01-swagger-overview.png)

**Log in via the Authorize button (OAuth2 password flow → JWT)**

![Authorize](docs/screenshots/02-authorized.png)

**Upload the daily file** — 204 rows, 4 duplicate references detected

![Upload](docs/screenshots/03-upload-daily-file.png)

**Run a reconciliation** — 184 matched, 12 mismatched, 4 missing in DB, 4 missing in file, 4 duplicates

![Reconcile](docs/screenshots/04-run-reconciliation.png)

**Unmatched-transaction report (JSON)**

![Report JSON](docs/screenshots/05-unmatched-report.png)

**Same report downloaded as CSV** (`format=csv`; `format=xlsx` adds a summary sheet)

![Report CSV](docs/screenshots/08-unmatched-report-csv.png)

**Search transactions** — partial reference, status, amount/date ranges, sorting, paging

![Search](docs/screenshots/06-search-transactions.png)

**Duplicate references in an import batch**

![Duplicates](docs/screenshots/07-duplicate-references.png)

**Test suite**

![pytest](docs/screenshots/09-pytest-results.png)

---

## Quick start

### Option A — Docker Compose (SQL Server 2022 + API + dashboard)

```bash
cp .env.example .env          # edit the placeholder passwords / secret
docker compose up --build
```

The API container creates the `BankRecon` database, runs `alembic upgrade head` and creates the bootstrap admin.

* Dashboard: <http://localhost:3000> (sign in with `RECON_ADMIN_USERNAME` / `RECON_ADMIN_PASSWORD`)
* API docs: <http://localhost:8000/docs>

### Option B — Local Python (SQLite, no SQL Server needed)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export RECON_ADMIN_USERNAME=admin RECON_ADMIN_PASSWORD='ChangeMe-LocalAdmin-1'
alembic upgrade head
uvicorn app.main:app --reload

# in a second terminal
cd frontend && npm install && npm run dev      # http://localhost:5173 (proxies /api to :8000)
```

To use a local SQL Server instead, set `RECON_DATABASE_URL` (see `.env.example`) and install the
[Microsoft ODBC Driver 18](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).

### Try the full workflow

```bash
python scripts/generate_synthetic_data.py --count 200       # writes sample_data/*.csv|xlsx

TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/token \
  -d "username=admin&password=ChangeMe-LocalAdmin-1" | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

# 1. Seed the ledger (the "database side")
curl -s -H "$AUTH" -F file=@sample_data/ledger_transactions.csv localhost:8000/api/v1/transactions/import

# 2. Upload the bank's daily file
curl -s -H "$AUTH" -F file=@sample_data/bank_daily_file.xlsx localhost:8000/api/v1/imports

# 3. Reconcile batch 1
curl -s -H "$AUTH" -H "Content-Type: application/json" -d '{"batch_id": 1}' localhost:8000/api/v1/reconciliations

# 4. Download the unmatched report
curl -s -H "$AUTH" "localhost:8000/api/v1/reconciliations/1/report?format=csv" -o unmatched.csv
```

---

## API overview

Interactive docs: **`/docs`** (Swagger UI) and **`/redoc`**. All endpoints are under `/api/v1` and need a bearer token.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/token` | Log in, returns JWT |
| GET | `/auth/me` | Current user |
| GET / POST | `/auth/users` | List / create users (admin) |
| POST | `/transactions` | Create ledger transaction (409 on duplicate reference) |
| GET | `/transactions` | Search: `reference`, `account_number`, `customer_name`, `status`, `currency`, `min_amount`, `max_amount`, `date_from`, `date_to`, `sort_by`, `sort_order`, `limit`, `offset` |
| GET | `/transactions/{id}` · `/transactions/by-reference/{ref}` | Retrieve |
| PUT / PATCH | `/transactions/{id}` | Replace / partial update |
| POST | `/transactions/import` | Bulk-load ledger from CSV/Excel |
| POST | `/imports` | Upload daily bank file |
| GET | `/imports` · `/imports/{id}` · `/imports/{id}/records` · `/imports/{id}/duplicates` | Inspect batches |
| POST | `/reconciliations` | Reconcile a batch (`batch_id`, optional tolerances / period) |
| GET | `/reconciliations` · `/reconciliations/{id}` · `/reconciliations/{id}/items` | Runs and items (filter by `category`, `exceptions_only`, `reference`) |
| GET | `/reconciliations/{id}/report` | Unmatched report, `format=json\|csv\|xlsx`, `include_matched` |
| GET | `/dashboard/summary` | Ledger totals by status, import/run counts, latest and recent runs, recent imports |
| GET | `/health` | Liveness + DB check (outside `/api/v1`, no auth) |

---

## Project layout

```
app/
  main.py               FastAPI app, request-ID logging middleware, health, OpenAPI metadata
  config.py             Settings (env prefix RECON_)
  database.py           Engine/session (SQL Server fast_executemany, SQLite for tests)
  models.py             ORM: users, transactions, import_batches, statement_records, reconciliation_*
  schemas.py            Pydantic validation (references, money, currency, status synonyms)
  security.py           PBKDF2 password hashing, JWT, role dependencies
  logging_config.py     Text or JSON logs with request IDs
  routers/              auth, transactions, imports, reconciliation
  services/             importer (pandas), reconciliation (matching engine), reports (CSV/Excel)
alembic/                Migrations
scripts/                Synthetic data generator, DB bootstrap, container entrypoint
tests/                  Unit + API tests
sample_data/            Generated synthetic files
frontend/               React + TypeScript dashboard (Vite), nginx Dockerfile — see frontend/README.md
Dockerfile              Multi-stage (test / runtime) with ODBC Driver 18
docker-compose.yml      SQL Server 2022 + API + dashboard
.gitlab-ci.yml          lint → test (SQLite, real SQL Server, frontend) → build & push both images
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `RECON_DATABASE_URL` | `sqlite:///./reconciliation.db` | `mssql+pyodbc://…` for SQL Server |
| `RECON_JWT_SECRET_KEY` | dev placeholder | **Required** when `RECON_ENVIRONMENT=production` (startup fails otherwise) |
| `RECON_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | |
| `RECON_ADMIN_USERNAME` / `RECON_ADMIN_PASSWORD` | — | Bootstrap admin, created only when the users table is empty |
| `RECON_AMOUNT_TOLERANCE` / `RECON_DATE_TOLERANCE_DAYS` | `0.00` / `0` | Default reconciliation tolerances |
| `RECON_MAX_UPLOAD_SIZE_MB` | `10` | Larger uploads get HTTP 413 |
| `RECON_LOG_LEVEL` / `RECON_LOG_JSON` | `INFO` / `false` | JSON logs suit container log shippers |
| `RECON_CORS_ORIGINS` | `[]` | JSON list of browser origins; only needed if the dashboard is hosted on another origin |

## Testing

```bash
pytest --cov                    # SQLite in-memory, ~2 s
ruff check . && ruff format --check .
cd frontend && npm run typecheck && npm test     # 16 Vitest tests
TEST_DATABASE_URL='mssql+pyodbc://…/BankReconTest?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes' pytest
```

Tests cover the importer (formats, aliases, error rows, Excel types), the matching engine (every category,
tolerances, duplicate ordering), auth and roles, all API endpoints, report downloads, and an Alembic
upgrade → `alembic check` → downgrade round trip that fails if models and migrations drift apart.

## SQL Server notes

* `DECIMAL(18,2)` for money, `NVARCHAR` for names, `DATETIMEOFFSET` for audit timestamps.
* Reference lookups are chunked (1,000 per `IN` list) to stay under SQL Server's 2,100-parameter limit.
* Paging always has a deterministic `ORDER BY` (required by `OFFSET … FETCH`).
* Reconciliation items store snapshots + plain ids rather than FKs to avoid SQL Server's
  "multiple cascade paths" restriction and to keep historical reports stable when the ledger changes.
