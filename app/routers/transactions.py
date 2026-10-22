import logging
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction, TransactionStatus
from app.routers._uploads import duplicate_list, error_list, read_and_parse
from app.schemas import LedgerImportResult, Page, TransactionCreate, TransactionRead, TransactionUpdate
from app.security import AnalystUser, CurrentUser
from app.services.importer import find_duplicate_references
from app.services.reconciliation import load_ledger_by_reference

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["Transactions"])

DbSession = Annotated[Session, Depends(get_db)]

SORT_COLUMNS = {
    "transaction_date": Transaction.transaction_date,
    "amount": Transaction.amount,
    "reference": Transaction.reference,
    "created_at": Transaction.created_at,
}


def _get_or_404(db: Session, transaction_id: int) -> Transaction:
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return txn


def _reference_taken(db: Session, reference: str, exclude_id: int | None = None) -> bool:
    query = select(Transaction.id).where(Transaction.reference == reference)
    if exclude_id is not None:
        query = query.where(Transaction.id != exclude_id)
    return db.scalar(query) is not None


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED, summary="Create a transaction")
def create_transaction(payload: TransactionCreate, user: AnalystUser, db: DbSession) -> Transaction:
    if _reference_taken(db, payload.reference):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate transaction reference")
    txn = Transaction(**payload.model_dump(mode="python"))
    txn.status = payload.status.value
    db.add(txn)
    try:
        db.commit()
    except IntegrityError:  # concurrent insert of the same reference
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate transaction reference") from None
    db.refresh(txn)
    logger.info("Transaction %s created by %s", txn.reference, user.username)
    return txn


@router.get("", response_model=Page[TransactionRead], summary="Search transactions")
def search_transactions(
    user: CurrentUser,
    db: DbSession,
    reference: Annotated[str | None, Query(description="Case-insensitive partial match")] = None,
    account_number: str | None = None,
    customer_name: Annotated[str | None, Query(description="Partial match")] = None,
    status_: Annotated[TransactionStatus | None, Query(alias="status")] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: Literal["transaction_date", "amount", "reference", "created_at"] = "transaction_date",
    sort_order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    filters = []
    if reference:
        filters.append(Transaction.reference.contains(reference.strip().upper(), autoescape=True))
    if account_number:
        filters.append(Transaction.account_number == account_number.strip())
    if customer_name:
        filters.append(Transaction.customer_name.icontains(customer_name.strip(), autoescape=True))
    if status_:
        filters.append(Transaction.status == status_.value)
    if currency:
        filters.append(Transaction.currency == currency.upper())
    if min_amount is not None:
        filters.append(Transaction.amount >= min_amount)
    if max_amount is not None:
        filters.append(Transaction.amount <= max_amount)
    if date_from:
        filters.append(Transaction.transaction_date >= date_from)
    if date_to:
        filters.append(Transaction.transaction_date <= date_to)

    total = db.scalar(select(func.count()).select_from(Transaction).where(*filters)) or 0
    sort_column = SORT_COLUMNS[sort_by]
    order = sort_column.desc() if sort_order == "desc" else sort_column.asc()
    # SQL Server requires a deterministic ORDER BY for OFFSET/FETCH paging.
    items = db.scalars(
        select(Transaction).where(*filters).order_by(order, Transaction.id).offset(offset).limit(limit)
    ).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/by-reference/{reference}", response_model=TransactionRead, summary="Get a transaction by reference")
def get_by_reference(reference: str, user: CurrentUser, db: DbSession) -> Transaction:
    txn = db.scalar(select(Transaction).where(Transaction.reference == reference.strip().upper()))
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return txn


@router.get("/{transaction_id}", response_model=TransactionRead, summary="Get a transaction")
def get_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> Transaction:
    return _get_or_404(db, transaction_id)


def _apply_update(db: Session, txn: Transaction, changes: dict, username: str) -> Transaction:
    if "reference" in changes and _reference_taken(db, changes["reference"], exclude_id=txn.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate transaction reference")
    for field, value in changes.items():
        setattr(txn, field, value.value if isinstance(value, TransactionStatus) else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate transaction reference") from None
    db.refresh(txn)
    logger.info("Transaction %s updated by %s fields=%s", txn.reference, username, sorted(changes))
    return txn


@router.put("/{transaction_id}", response_model=TransactionRead, summary="Replace a transaction")
def replace_transaction(
    transaction_id: int, payload: TransactionCreate, user: AnalystUser, db: DbSession
) -> Transaction:
    txn = _get_or_404(db, transaction_id)
    return _apply_update(db, txn, payload.model_dump(), user.username)


@router.patch("/{transaction_id}", response_model=TransactionRead, summary="Partially update a transaction")
def update_transaction(
    transaction_id: int, payload: TransactionUpdate, user: AnalystUser, db: DbSession
) -> Transaction:
    txn = _get_or_404(db, transaction_id)
    changes = payload.model_dump(exclude_unset=True)
    required = {"reference", "amount", "currency", "transaction_date", "status"}
    nulled = sorted(f for f in required if f in changes and changes[f] is None)
    if nulled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Fields cannot be null: {nulled}"
        )
    return _apply_update(db, txn, changes, user.username)


@router.post(
    "/import",
    response_model=LedgerImportResult,
    summary="Bulk-load ledger transactions from CSV/Excel",
    description=(
        "Loads valid rows into the ledger. Rows whose reference already exists in the ledger, and repeated "
        "references inside the file (all but the first occurrence), are skipped and reported."
    ),
)
async def import_ledger(user: AnalystUser, db: DbSession, file: UploadFile = File(...)) -> LedgerImportResult:
    parsed = await read_and_parse(file)
    duplicates = find_duplicate_references(parsed.rows)
    existing = load_ledger_by_reference(db, (txn.reference for _, txn in parsed.rows))

    to_insert: list[Transaction] = []
    seen: set[str] = set()
    for _, row in parsed.rows:
        if row.reference in existing or row.reference in seen:
            continue
        seen.add(row.reference)
        txn = Transaction(**row.model_dump())
        txn.status = row.status.value
        to_insert.append(txn)

    db.add_all(to_insert)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Conflicting references were inserted concurrently; retry"
        ) from None
    logger.info("Ledger import file=%s by=%s inserted=%d", parsed.filename, user.username, len(to_insert))
    return LedgerImportResult(
        filename=parsed.filename,
        total_rows=parsed.total_rows,
        inserted=len(to_insert),
        invalid_rows=len(parsed.errors),
        skipped_existing=sorted(existing),
        duplicates=duplicate_list(duplicates),
        errors=error_list(parsed),
    )
