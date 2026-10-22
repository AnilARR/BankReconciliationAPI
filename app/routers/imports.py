import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ImportBatch, StatementRecord
from app.routers._uploads import duplicate_list, error_list, read_and_parse
from app.schemas import (
    DuplicateReference,
    ImportBatchRead,
    Page,
    StatementImportResult,
    StatementRecordRead,
)
from app.security import AnalystUser, CurrentUser
from app.services.importer import find_duplicate_references

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/imports", tags=["Daily file imports"])

DbSession = Annotated[Session, Depends(get_db)]


def _get_batch_or_404(db: Session, batch_id: int) -> ImportBatch:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")
    return batch


@router.post(
    "",
    response_model=StatementImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload the bank's daily transaction file (CSV/Excel)",
    description=(
        "Validates every row, stores valid rows as a new import batch and reports invalid rows and duplicate "
        "references. Run a reconciliation on the returned batch id afterwards."
    ),
)
async def upload_statement(user: AnalystUser, db: DbSession, file: UploadFile = File(...)) -> StatementImportResult:
    parsed = await read_and_parse(file)
    if not parsed.rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "File contains no valid rows", "errors": [e.model_dump() for e in error_list(parsed)]},
        )
    duplicates = find_duplicate_references(parsed.rows)

    batch = ImportBatch(
        filename=parsed.filename,
        file_type=parsed.file_type,
        uploaded_by=user.username,
        total_rows=parsed.total_rows,
        valid_rows=len(parsed.rows),
        invalid_rows=len(parsed.errors),
        duplicate_rows=sum(len(rows) - 1 for rows in duplicates.values()),
    )
    seen: set[str] = set()
    for row_number, row in parsed.rows:
        batch.records.append(
            StatementRecord(
                row_number=row_number,
                is_duplicate=row.reference in seen,
                **row.model_dump(exclude={"status"}),
                status=row.status.value,
            )
        )
        seen.add(row.reference)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    logger.info(
        "Statement import batch=%d file=%s by=%s valid=%d invalid=%d duplicates=%d",
        batch.id,
        batch.filename,
        user.username,
        batch.valid_rows,
        batch.invalid_rows,
        batch.duplicate_rows,
    )
    return StatementImportResult(
        batch=ImportBatchRead.model_validate(batch),
        duplicates=duplicate_list(duplicates),
        errors=error_list(parsed),
    )


@router.get("", response_model=Page[ImportBatchRead], summary="List import batches")
def list_batches(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    total = db.scalar(select(func.count()).select_from(ImportBatch)) or 0
    items = db.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).offset(offset).limit(limit)).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/{batch_id}", response_model=ImportBatchRead, summary="Get an import batch")
def get_batch(batch_id: int, user: CurrentUser, db: DbSession) -> ImportBatch:
    return _get_batch_or_404(db, batch_id)


@router.get("/{batch_id}/records", response_model=Page[StatementRecordRead], summary="Records in an import batch")
def list_records(
    batch_id: int,
    user: CurrentUser,
    db: DbSession,
    duplicates_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    _get_batch_or_404(db, batch_id)
    filters = [StatementRecord.batch_id == batch_id]
    if duplicates_only:
        filters.append(StatementRecord.is_duplicate.is_(True))
    total = db.scalar(select(func.count()).select_from(StatementRecord).where(*filters)) or 0
    items = db.scalars(
        select(StatementRecord).where(*filters).order_by(StatementRecord.row_number).offset(offset).limit(limit)
    ).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get(
    "/{batch_id}/duplicates",
    response_model=list[DuplicateReference],
    summary="Duplicate transaction references in an import batch",
)
def list_duplicates(batch_id: int, user: CurrentUser, db: DbSession) -> list[DuplicateReference]:
    _get_batch_or_404(db, batch_id)
    duplicated = (
        select(StatementRecord.reference)
        .where(StatementRecord.batch_id == batch_id)
        .group_by(StatementRecord.reference)
        .having(func.count() > 1)
    )
    rows = db.execute(
        select(StatementRecord.reference, StatementRecord.row_number)
        .where(StatementRecord.batch_id == batch_id, StatementRecord.reference.in_(duplicated))
        .order_by(StatementRecord.reference, StatementRecord.row_number)
    ).all()
    grouped: dict[str, list[int]] = {}
    for reference, row_number in rows:
        grouped.setdefault(reference, []).append(row_number)
    return duplicate_list(grouped)
