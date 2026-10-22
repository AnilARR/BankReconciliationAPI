import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ImportBatch, ReconciliationCategory, ReconciliationItem, ReconciliationRun
from app.schemas import (
    Page,
    ReconciliationItemRead,
    ReconciliationRequest,
    ReconciliationRunRead,
    UnmatchedReport,
)
from app.security import AnalystUser, CurrentUser
from app.services import reports
from app.services.reconciliation import ReconciliationConfig, run_reconciliation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reconciliations", tags=["Reconciliation"])

DbSession = Annotated[Session, Depends(get_db)]

UNMATCHED_CATEGORIES = [c.value for c in ReconciliationCategory if c is not ReconciliationCategory.MATCHED]


def _get_run_or_404(db: Session, run_id: int) -> ReconciliationRun:
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation run not found")
    return run


@router.post(
    "",
    response_model=ReconciliationRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Reconcile an import batch against the ledger",
    description=(
        "Matches file records to ledger transactions by reference and compares amount, date, status, currency "
        "and account number. Produces MATCHED, MISMATCHED, MISSING_IN_DATABASE, MISSING_IN_FILE and "
        "DUPLICATE_IN_FILE items."
    ),
)
def create_run(payload: ReconciliationRequest, user: AnalystUser, db: DbSession) -> ReconciliationRun:
    batch = db.get(ImportBatch, payload.batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")
    if payload.period_start and payload.period_end and payload.period_start > payload.period_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="period_start must be on or before period_end"
        )
    settings = get_settings()
    config = ReconciliationConfig(
        amount_tolerance=payload.amount_tolerance
        if payload.amount_tolerance is not None
        else settings.amount_tolerance,
        date_tolerance_days=(
            payload.date_tolerance_days if payload.date_tolerance_days is not None else settings.date_tolerance_days
        ),
    )
    return run_reconciliation(db, batch, user.username, config, payload.period_start, payload.period_end)


@router.get("", response_model=Page[ReconciliationRunRead], summary="List reconciliation runs")
def list_runs(
    user: CurrentUser,
    db: DbSession,
    batch_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    filters = [ReconciliationRun.batch_id == batch_id] if batch_id is not None else []
    total = db.scalar(select(func.count()).select_from(ReconciliationRun).where(*filters)) or 0
    items = db.scalars(
        select(ReconciliationRun).where(*filters).order_by(ReconciliationRun.id.desc()).offset(offset).limit(limit)
    ).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/{run_id}", response_model=ReconciliationRunRead, summary="Reconciliation run summary")
def get_run(run_id: int, user: CurrentUser, db: DbSession) -> ReconciliationRun:
    return _get_run_or_404(db, run_id)


@router.get("/{run_id}/items", response_model=Page[ReconciliationItemRead], summary="Reconciliation items")
def list_items(
    run_id: int,
    user: CurrentUser,
    db: DbSession,
    category: ReconciliationCategory | None = None,
    reference: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    _get_run_or_404(db, run_id)
    filters = [ReconciliationItem.run_id == run_id]
    if category:
        filters.append(ReconciliationItem.category == category.value)
    if reference:
        filters.append(ReconciliationItem.reference == reference.strip().upper())
    total = db.scalar(select(func.count()).select_from(ReconciliationItem).where(*filters)) or 0
    items = db.scalars(
        select(ReconciliationItem).where(*filters).order_by(ReconciliationItem.id).offset(offset).limit(limit)
    ).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get(
    "/{run_id}/report",
    response_model=UnmatchedReport,
    summary="Unmatched-transaction report",
    description="All non-matched items of a run, as JSON (default), CSV or Excel (`format=csv|xlsx`).",
    responses={
        200: {
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
            }
        }
    },
)
def unmatched_report(
    run_id: int,
    user: CurrentUser,
    db: DbSession,
    format: Literal["json", "csv", "xlsx"] = "json",
    include_matched: bool = False,
):
    run = _get_run_or_404(db, run_id)
    query = select(ReconciliationItem).where(ReconciliationItem.run_id == run_id)
    if not include_matched:
        query = query.where(ReconciliationItem.category.in_(UNMATCHED_CATEGORIES))
    items = list(db.scalars(query.order_by(ReconciliationItem.category, ReconciliationItem.reference)))
    logger.info("Report run=%d format=%s items=%d requested by %s", run_id, format, len(items), user.username)

    filename = f"unmatched_report_run_{run_id}"
    if format == "csv":
        return Response(
            content=reports.to_csv(items),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    if format == "xlsx":
        return Response(
            content=reports.to_excel(run, items),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )
    return UnmatchedReport(
        run=ReconciliationRunRead.model_validate(run),
        items=[ReconciliationItemRead.model_validate(i) for i in items],
    )
