"""Pydantic request/response models."""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ReconciliationCategory, TransactionStatus, UserRole

REFERENCE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\-_/.]{0,63}$")

# Bank files use many words for the same outcome; map them onto our canonical statuses.
STATUS_SYNONYMS: dict[str, TransactionStatus] = {
    "PENDING": TransactionStatus.PENDING,
    "PROCESSING": TransactionStatus.PENDING,
    "IN_PROGRESS": TransactionStatus.PENDING,
    "COMPLETED": TransactionStatus.COMPLETED,
    "COMPLETE": TransactionStatus.COMPLETED,
    "SUCCESS": TransactionStatus.COMPLETED,
    "SUCCESSFUL": TransactionStatus.COMPLETED,
    "SETTLED": TransactionStatus.COMPLETED,
    "POSTED": TransactionStatus.COMPLETED,
    "FAILED": TransactionStatus.FAILED,
    "DECLINED": TransactionStatus.FAILED,
    "REJECTED": TransactionStatus.FAILED,
    "REVERSED": TransactionStatus.REVERSED,
    "REFUNDED": TransactionStatus.REVERSED,
    "CHARGEBACK": TransactionStatus.REVERSED,
}

Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2)]


def normalize_reference(value: str) -> str:
    return value.strip().upper()


def normalize_status(value: Any) -> Any:
    if isinstance(value, str):
        key = value.strip().upper().replace(" ", "_").replace("-", "_")
        return STATUS_SYNONYMS.get(key, value)
    return value


def _clean_optional_str(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class _TransactionFields(BaseModel):
    @field_validator("reference", mode="before", check_fields=False)
    @classmethod
    def _validate_reference(cls, value: Any) -> Any:
        if value is None:
            return value
        value = normalize_reference(str(value))
        if not REFERENCE_PATTERN.match(value):
            raise ValueError("reference must be 1-64 chars: letters, digits, '-', '_', '/', '.'")
        return value

    @field_validator("status", mode="before", check_fields=False)
    @classmethod
    def _validate_status(cls, value: Any) -> Any:
        return normalize_status(value)

    @field_validator("currency", mode="before", check_fields=False)
    @classmethod
    def _validate_currency(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("account_number", "customer_name", "description", mode="before", check_fields=False)
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return _clean_optional_str(value)


class TransactionCreate(_TransactionFields):
    reference: str = Field(examples=["TXN-20261021-000123"])
    account_number: str | None = Field(default=None, max_length=34, examples=["GB00SYNT00000012345678"])
    customer_name: str | None = Field(default=None, max_length=200, examples=["Synthetic Customer 042"])
    amount: Money = Field(examples=["1250.75"])
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    transaction_date: date
    status: TransactionStatus
    description: str | None = Field(default=None, max_length=500)


class TransactionUpdate(_TransactionFields):
    reference: str | None = None
    account_number: str | None = Field(default=None, max_length=34)
    customer_name: str | None = Field(default=None, max_length=200)
    amount: Money | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    transaction_date: date | None = None
    status: TransactionStatus | None = None
    description: str | None = Field(default=None, max_length=500)


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    account_number: str | None
    customer_name: str | None
    amount: Decimal = Field(examples=["1250.75"])
    currency: str
    transaction_date: date
    status: TransactionStatus
    description: str | None
    created_at: datetime
    updated_at: datetime


class Page[T](BaseModel):
    total: int
    limit: int
    offset: int
    items: list[T]


class RowErrorOut(BaseModel):
    row_number: int
    reference: str | None
    errors: list[str]


class DuplicateReference(BaseModel):
    reference: str
    row_numbers: list[int]
    occurrences: int


class LedgerImportResult(BaseModel):
    filename: str
    total_rows: int
    inserted: int
    invalid_rows: int
    skipped_existing: list[str]
    duplicates: list[DuplicateReference]
    errors: list[RowErrorOut]


class ImportBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    uploaded_by: str
    created_at: datetime
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int


class StatementImportResult(BaseModel):
    batch: ImportBatchRead
    duplicates: list[DuplicateReference]
    errors: list[RowErrorOut]


class StatementRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    row_number: int
    reference: str
    account_number: str | None
    customer_name: str | None
    amount: Decimal = Field(examples=["1250.75"])
    currency: str
    transaction_date: date
    status: str
    description: str | None
    is_duplicate: bool


class ReconciliationRequest(BaseModel):
    batch_id: int
    amount_tolerance: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2, examples=["0.00"])
    date_tolerance_days: int | None = Field(default=None, ge=0, le=31)
    period_start: date | None = Field(default=None, description="Defaults to the earliest date in the file.")
    period_end: date | None = Field(default=None, description="Defaults to the latest date in the file.")


class ReconciliationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    run_by: str
    created_at: datetime
    amount_tolerance: Decimal = Field(examples=["0.00"])
    date_tolerance_days: int
    period_start: date | None
    period_end: date | None
    file_records: int
    matched: int
    mismatched: int
    missing_in_database: int
    missing_in_file: int
    duplicates_in_file: int


class ReconciliationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: ReconciliationCategory
    reference: str
    statement_record_id: int | None
    transaction_id: int | None
    file_row_number: int | None
    file_amount: Decimal | None = Field(examples=["1250.75"])
    db_amount: Decimal | None = Field(examples=["1250.75"])
    file_date: date | None
    db_date: date | None
    file_status: str | None
    db_status: str | None
    mismatched_fields: str | None
    details: str | None


class UnmatchedReport(BaseModel):
    run: ReconciliationRunRead
    items: list[ReconciliationItemRead]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime


class StatusTotal(BaseModel):
    status: str
    count: int
    amount: Decimal = Field(examples=["1250.75"])


class DashboardSummary(BaseModel):
    transaction_count: int
    transaction_volume: Decimal = Field(examples=["1250.75"])
    transactions_by_status: list[StatusTotal]
    import_count: int
    run_count: int
    latest_run: ReconciliationRunRead | None
    recent_runs: list[ReconciliationRunRead]
    recent_imports: list[ImportBatchRead]
