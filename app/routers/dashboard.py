from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ImportBatch, ReconciliationRun, Transaction
from app.schemas import DashboardSummary, ImportBatchRead, ReconciliationRunRead, StatusTotal
from app.security import CurrentUser

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary, summary="Figures for the dashboard home page")
def summary(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    recent: Annotated[int, Query(ge=1, le=50, description="How many recent runs / imports to return")] = 10,
) -> DashboardSummary:
    by_status = db.execute(
        select(Transaction.status, func.count(), func.coalesce(func.sum(Transaction.amount), 0))
        .group_by(Transaction.status)
        .order_by(Transaction.status)
    ).all()
    recent_runs = db.scalars(select(ReconciliationRun).order_by(ReconciliationRun.id.desc()).limit(recent)).all()
    recent_imports = db.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).limit(recent)).all()
    return DashboardSummary(
        transaction_count=sum(count for _, count, _ in by_status),
        transaction_volume=sum((total for _, _, total in by_status), start=0),
        transactions_by_status=[StatusTotal(status=s, count=c, amount=a) for s, c, a in by_status],
        import_count=db.scalar(select(func.count()).select_from(ImportBatch)) or 0,
        run_count=db.scalar(select(func.count()).select_from(ReconciliationRun)) or 0,
        latest_run=ReconciliationRunRead.model_validate(recent_runs[0]) if recent_runs else None,
        recent_runs=[ReconciliationRunRead.model_validate(r) for r in recent_runs],
        recent_imports=[ImportBatchRead.model_validate(b) for b in recent_imports],
    )
