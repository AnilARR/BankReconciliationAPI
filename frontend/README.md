# ReconDesk — Reconciliation Dashboard (React)

Web dashboard for the [Banking Transaction Reconciliation API](../README.md). Analysts upload the bank's daily
file, run reconciliations, investigate exceptions and download reports without touching Swagger or curl.

**Stack:** React 19 · TypeScript · Vite · React Router · Recharts · Vitest + Testing Library · nginx (Docker)

![Dashboard](../docs/screenshots/frontend/02-dashboard.png)

## Pages

| Page | What it does |
|---|---|
| **Login** | JWT sign-in; the session survives page reloads (sessionStorage) and ends automatically when the token expires |
| **Dashboard** | Ledger size and volume, latest match rate, open exceptions, category donut, trend of recent runs, recent files, ledger by status |
| **Transactions** | Search the ledger (reference, customer, account, status, date and amount ranges), sortable columns, paging; create/edit transactions; bulk-import a ledger file |
| **Daily imports** | Drag-and-drop CSV/Excel upload with per-row validation errors and duplicate references; import history; reconcile straight from the upload result |
| **Import batch** | Batch stats, reconcile with optional amount/date tolerances and period, runs for the batch, file records (repeat rows highlighted), duplicate references |
| **Reconciliations** | History of all runs with per-category counts and match rate |
| **Run detail** | Clickable category cards, filter tabs (all exceptions / any category), reference lookup, file-vs-ledger values with differing fields highlighted, CSV/Excel report download |
| **Users** (admin) | List users and create viewer / analyst / admin accounts |

The UI follows the API's roles: viewers get a read-only interface, analysts can upload, reconcile and edit, and
only admins see user management.

## Running locally

Start the API first (see the root README); it listens on `http://localhost:8000`.

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

The Vite dev server proxies `/api` and `/health` to the API, so the browser sees a single origin and no CORS
configuration is needed. Point it elsewhere with `VITE_API_TARGET=http://host:port npm run dev`.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Type-check and produce `dist/` (route-level code splitting keeps charts out of the login bundle) |
| `npm run preview` | Serve the production build locally (same proxy as dev) |
| `npm run typecheck` | TypeScript only |
| `npm test` | Vitest + Testing Library (16 tests, `fetch` mocked) |

## Deployment

`docker compose up --build` in the repo root also builds this folder. The image serves the static build with nginx
on port 8080 (published as <http://localhost:3000>) and proxies `/api` to the `api` container:
SPA route fallback, immutable caching for hashed assets, 12 MB upload limit, basic security headers.

To host the static build on another origin instead, build with `VITE_API_BASE_URL=https://your-api` and allow that
origin on the API with `RECON_CORS_ORIGINS='["https://your-dashboard"]'`.

## Structure

```
src/
  api/          client.ts (fetch + auth + errors + downloads), endpoints.ts, types.ts (mirror of the API schemas)
  auth/         AuthContext — login, session restore, role flags, auto sign-out on 401
  components/   Layout (sidebar), ui.tsx (cards, badges, modal, dropzone, pagination…), charts.tsx, ImportFeedback
  pages/        One component per route
  utils/        Formatting, match-rate maths, category colours, useAsync hook
  test/         Test setup and a fetch-mocking helper
```
