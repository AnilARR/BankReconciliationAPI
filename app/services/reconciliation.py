"""Compare imported file records against ledger transactions.

The matching core (:func:`reconcile_records`) is a pure function so it can be unit tested without
a database; :func:`run_reconciliation` loads data, calls it, and persists the results.

Rules
-----
* Records are matched on normalised reference.
* The first occurrence of a reference in the file is reconciled; later occurrences are reported as
  ``DUPLICATE_IN_FILE``.
* A matched pair is ``MISMATCHED`` when amount (beyond tolerance), date (beyond tolerance), status,
  currency or account number differ.
* Ledger transactions dated inside the reconciliation period but absent from the file are
  ``MISSING_IN_FILE``.
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ImportBatch,
    ReconciliationCategory,
    ReconciliationItem,
    ReconciliationRun,
    StatementRecord,
    Transaction,
)

logger = logging.getLogger(__name__)

# SQL Server allows at most 2100 parameters per statement; keep IN (...) lists well below it.
IN_CLAUSE_CHUNK = 1000


class RecordLike(Protocol):
    id: int
    reference: str
    account_number: str | None
    amount: Decimal
    currency: str
    transaction_date: date
    status: str


@dataclass(frozen=True)
class ReconciliationConfig:
    amount_tolerance: Decimal = Decimal("0.00")
    date_tolerance_days: int = 0


@dataclass
class ItemResult:
    category: ReconciliationCategory
    reference: str
    statement_record_id: int | None = None
    transaction_id: int | None = None
    file_row_number: int | None = None
    file_amount: Decimal | None = None
    db_amount: Decimal | None = None
    file_date: date | None = None
    db_date: date | None = None
    file_status: str | None = None
    db_status: str | None = None
    mismatched_fields: list[str] | None = None
    details: str | None = None


def _status(value: Any) -> str:
    return getattr(value, "value", value)


def compare_records(file_rec: RecordLike, txn: RecordLike, config: ReconciliationConfig) -> dict[str, str]:
    """Return {field: human readable difference} for every field that does not reconcile."""
    diffs: dict[str, str] = {}
    amount_delta = abs(Decimal(file_rec.amount) - Decimal(txn.amount))
    if amount_delta > config.amount_tolerance:
        diffs["amount"] = f"amount: file={file_rec.amount} db={txn.amount} (diff {amount_delta})"
    day_delta = abs((file_rec.transaction_date - txn.transaction_date).days)
    if day_delta > config.date_tolerance_days:
        diffs["transaction_date"] = (
            f"transaction_date: file={file_rec.transaction_date} db={txn.transaction_date} ({day_delta} day(s))"
        )
    if _status(file_rec.status) != _status(txn.status):
        diffs["status"] = f"status: file={_status(file_rec.status)} db={_status(txn.status)}"
    if file_rec.currency != txn.currency:
        diffs["currency"] = f"currency: file={file_rec.currency} db={txn.currency}"
    if file_rec.account_number and txn.account_number and file_rec.account_number != txn.account_number:
        diffs["account_number"] = f"account_number: file={file_rec.account_number} db={txn.account_number}"
    return diffs


def _file_side(rec: Any) -> dict[str, Any]:
    return {
        "statement_record_id": rec.id,
        "file_row_number": getattr(rec, "row_number", None),
        "file_amount": rec.amount,
        "file_date": rec.transaction_date,
        "file_status": _status(rec.status),
    }


def _db_side(txn: Any) -> dict[str, Any]:
    return {
        "transaction_id": txn.id,
        "db_amount": txn.amount,
        "db_date": txn.transaction_date,
        "db_status": _status(txn.status),
    }


def reconcile_records(
    file_records: Sequence[Any],
    ledger_by_reference: dict[str, Any],
    ledger_in_period: Iterable[Any],
    config: ReconciliationConfig,
) -> list[ItemResult]:
    results: list[ItemResult] = []
    seen: dict[str, Any] = {}

    for rec in sorted(file_records, key=lambda r: (getattr(r, "row_number", 0), r.id)):
        ref = rec.reference
        if ref in seen:
            first = seen[ref]
            results.append(
                ItemResult(
                    ReconciliationCategory.DUPLICATE_IN_FILE,
                    ref,
                    **_file_side(rec),
                    details=f"Duplicate of row {getattr(first, 'row_number', '?')}",
                )
            )
            continue
        seen[ref] = rec

        txn = ledger_by_reference.get(ref)
        if txn is None:
            results.append(
                ItemResult(
                    ReconciliationCategory.MISSING_IN_DATABASE,
                    ref,
                    **_file_side(rec),
                    details="Reference not found in ledger",
                )
            )
            continue

        diffs = compare_records(rec, txn, config)
        category = ReconciliationCategory.MISMATCHED if diffs else ReconciliationCategory.MATCHED
        results.append(
            ItemResult(
                category,
                ref,
                **_file_side(rec),
                **_db_side(txn),
                mismatched_fields=list(diffs) or None,
                details="; ".join(diffs.values()) or None,
            )
        )

    for txn in ledger_in_period:
        if txn.reference not in seen:
            results.append(
                ItemResult(
                    ReconciliationCategory.MISSING_IN_FILE,
                    txn.reference,
                    **_db_side(txn),
                    details="Ledger transaction not present in file",
                )
            )
    return results


def _chunks(values: Sequence[str], size: int = IN_CLAUSE_CHUNK) -> Iterable[Sequence[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def load_ledger_by_reference(db: Session, references: Iterable[str]) -> dict[str, Transaction]:
    unique_refs = sorted(set(references))
    found: dict[str, Transaction] = {}
    for chunk in _chunks(unique_refs):
        for txn in db.scalars(select(Transaction).where(Transaction.reference.in_(chunk))):
            found[txn.reference] = txn
    return found


def run_reconciliation(
    db: Session,
    batch: ImportBatch,
    run_by: str,
    config: ReconciliationConfig,
    period_start: date | None = None,
    period_end: date | None = None,
) -> ReconciliationRun:
    records = list(db.scalars(select(StatementRecord).where(StatementRecord.batch_id == batch.id)))
    if records:
        period_start = period_start or min(r.transaction_date for r in records)
        period_end = period_end or max(r.transaction_date for r in records)

    ledger_by_ref = load_ledger_by_reference(db, (r.reference for r in records))
    ledger_in_period: list[Transaction] = []
    if period_start and period_end:
        ledger_in_period = list(
            db.scalars(
                select(Transaction)
                .where(Transaction.transaction_date.between(period_start, period_end))
                .order_by(Transaction.transaction_date, Transaction.reference)
            )
        )

    results = reconcile_records(records, ledger_by_ref, ledger_in_period, config)
    counts = {c: 0 for c in ReconciliationCategory}
    for item in results:
        counts[item.category] += 1

    run = ReconciliationRun(
        batch_id=batch.id,
        run_by=run_by,
        amount_tolerance=config.amount_tolerance,
        date_tolerance_days=config.date_tolerance_days,
        period_start=period_start,
        period_end=period_end,
        file_records=len(records),
        matched=counts[ReconciliationCategory.MATCHED],
        mismatched=counts[ReconciliationCategory.MISMATCHED],
        missing_in_database=counts[ReconciliationCategory.MISSING_IN_DATABASE],
        missing_in_file=counts[ReconciliationCategory.MISSING_IN_FILE],
        duplicates_in_file=counts[ReconciliationCategory.DUPLICATE_IN_FILE],
    )
    run.items = [
        ReconciliationItem(
            category=item.category.value,
            reference=item.reference,
            statement_record_id=item.statement_record_id,
            transaction_id=item.transaction_id,
            file_row_number=item.file_row_number,
            file_amount=item.file_amount,
            db_amount=item.db_amount,
            file_date=item.file_date,
            db_date=item.db_date,
            file_status=item.file_status,
            db_status=item.db_status,
            mismatched_fields=",".join(item.mismatched_fields) if item.mismatched_fields else None,
            details=item.details,
        )
        for item in results
    ]
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info(
        "Reconciliation run=%d batch=%d by=%s matched=%d mismatched=%d missing_db=%d missing_file=%d duplicates=%d",
        run.id,
        batch.id,
        run_by,
        run.matched,
        run.mismatched,
        run.missing_in_database,
        run.missing_in_file,
        run.duplicates_in_file,
    )
    return run
