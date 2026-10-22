"""ORM models.

Column types are chosen to map cleanly onto SQL Server: ``Numeric(18, 2)`` -> DECIMAL(18,2),
``Unicode`` -> NVARCHAR, ``DateTime(timezone=True)`` -> DATETIMEOFFSET.

Reconciliation items deliberately store *snapshots* plus plain ids instead of foreign keys to
statement records / ledger transactions: SQL Server rejects multiple cascade paths, and a
reconciliation report must stay readable even if the ledger changes afterwards.
"""

import enum
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TransactionStatus(enum.StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class UserRole(enum.StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


class ReconciliationCategory(enum.StrEnum):
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    MISSING_IN_DATABASE = "MISSING_IN_DATABASE"
    MISSING_IN_FILE = "MISSING_IN_FILE"
    DUPLICATE_IN_FILE = "DUPLICATE_IN_FILE"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.VIEWER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transaction(Base):
    """A transaction in the bank's own ledger (the "database side" of reconciliation)."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    account_number: Mapped[str | None] = mapped_column(String(34), index=True)
    customer_name: Mapped[str | None] = mapped_column(Unicode(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str | None] = mapped_column(Unicode(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ImportBatch(Base):
    """One uploaded daily transaction file."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(Unicode(255))
    file_type: Mapped[str] = mapped_column(String(10))
    uploaded_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)

    records: Mapped[list["StatementRecord"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", passive_deletes=True
    )
    runs: Mapped[list["ReconciliationRun"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", passive_deletes=True
    )


class StatementRecord(Base):
    """A single valid row from an imported file (the "file side" of reconciliation)."""

    __tablename__ = "statement_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(64), index=True)
    account_number: Mapped[str | None] = mapped_column(String(34))
    customer_name: Mapped[str | None] = mapped_column(Unicode(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    transaction_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Unicode(500))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)

    batch: Mapped[ImportBatch] = relationship(back_populates="records")


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    run_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    amount_tolerance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    date_tolerance_days: Mapped[int] = mapped_column(Integer)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    file_records: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    mismatched: Mapped[int] = mapped_column(Integer, default=0)
    missing_in_database: Mapped[int] = mapped_column(Integer, default=0)
    missing_in_file: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_in_file: Mapped[int] = mapped_column(Integer, default=0)

    batch: Mapped[ImportBatch] = relationship(back_populates="runs")
    items: Mapped[list["ReconciliationItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class ReconciliationItem(Base):
    __tablename__ = "reconciliation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(30), index=True)
    reference: Mapped[str] = mapped_column(String(64), index=True)
    statement_record_id: Mapped[int | None] = mapped_column(Integer)
    transaction_id: Mapped[int | None] = mapped_column(Integer)
    file_row_number: Mapped[int | None] = mapped_column(Integer)
    file_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    db_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    file_date: Mapped[date | None] = mapped_column(Date)
    db_date: Mapped[date | None] = mapped_column(Date)
    file_status: Mapped[str | None] = mapped_column(String(20))
    db_status: Mapped[str | None] = mapped_column(String(20))
    mismatched_fields: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[str | None] = mapped_column(Unicode(1000))

    run: Mapped[ReconciliationRun] = relationship(back_populates="items")
