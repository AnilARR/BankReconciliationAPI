"""FastAPI application factory."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app import __version__
from app.config import DEFAULT_JWT_SECRET, get_settings
from app.database import SessionLocal, engine
from app.logging_config import configure_logging, request_id_var
from app.models import User, UserRole
from app.routers import auth, imports, reconciliation, transactions
from app.security import hash_password

logger = logging.getLogger("app")

API_PREFIX = "/api/v1"

DESCRIPTION = """
Reconciles the bank's **daily transaction file** (CSV or Excel) against transactions stored in SQL Server.

**Typical workflow**

1. `POST /api/v1/auth/token` - log in (use the **Authorize** button above).
2. `POST /api/v1/imports` - upload the daily file; invalid rows and duplicate references are reported.
3. `POST /api/v1/reconciliations` - reconcile the batch against the ledger.
4. `GET /api/v1/reconciliations/{run_id}/report?format=csv` - download the unmatched-transaction report.

Roles: `viewer` (read only), `analyst` (read, import, reconcile, create/update transactions), `admin` (everything,
including user management).

*Use synthetic data only.*
"""

TAGS = [
    {"name": "Authentication", "description": "JWT login and user management."},
    {"name": "Transactions", "description": "Ledger transactions: create, retrieve, update, search, bulk load."},
    {"name": "Daily file imports", "description": "Upload and inspect daily bank files."},
    {"name": "Reconciliation", "description": "Compare imported files with the ledger and produce reports."},
    {"name": "Health", "description": "Liveness / readiness."},
]


def bootstrap_admin() -> None:
    settings = get_settings()
    if not (settings.admin_username and settings.admin_password):
        return
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is not None:
            return
        db.add(
            User(
                username=settings.admin_username,
                hashed_password=hash_password(settings.admin_password),
                role=UserRole.ADMIN.value,
            )
        )
        db.commit()
        logger.info("Bootstrap admin user '%s' created", settings.admin_username)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.jwt_secret_key == DEFAULT_JWT_SECRET:
        if settings.environment == "production":
            raise RuntimeError("RECON_JWT_SECRET_KEY must be set in production")
        logger.warning("Using the default JWT secret - set RECON_JWT_SECRET_KEY outside local development")
    try:
        bootstrap_admin()
    except Exception:
        logger.exception("Could not bootstrap admin user (have migrations been applied?)")
    logger.info(
        "%s v%s started (env=%s, db=%s)",
        settings.app_name,
        __version__,
        settings.environment,
        engine.url.render_as_string(hide_password=True),
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info("%s %s -> %d (%.1f ms)", request.method, request.url.path, response.status_code, duration_ms)
        request_id_var.reset(token)
        return response

    for router in (auth.router, transactions.router, imports.router, reconciliation.router):
        app.include_router(router, prefix=API_PREFIX)

    @app.get("/health", tags=["Health"], summary="Liveness and database connectivity")
    def health() -> JSONResponse:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return JSONResponse({"status": "ok", "database": "ok"})
        except Exception:
            logger.exception("Health check: database unavailable")
            return JSONResponse({"status": "degraded", "database": "unavailable"}, status_code=503)

    return app


app = create_app()
