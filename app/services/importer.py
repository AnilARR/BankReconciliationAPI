"""Parse daily transaction files (CSV / Excel) with pandas and validate each row with Pydantic."""

import io
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from app.schemas import TransactionCreate

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".csv": "csv", ".xlsx": "xlsx"}

# Canonical column name -> accepted header spellings (compared after normalisation).
COLUMN_ALIASES: dict[str, set[str]] = {
    "reference": {
        "reference",
        "ref",
        "txn_ref",
        "transaction_reference",
        "transaction_ref",
        "payment_reference",
        "transaction_id",
        "txn_id",
    },
    "account_number": {"account_number", "account", "account_no", "acct_no", "iban"},
    "customer_name": {"customer_name", "customer", "name", "beneficiary", "payee"},
    "amount": {"amount", "txn_amount", "transaction_amount", "value"},
    "currency": {"currency", "ccy", "currency_code"},
    "transaction_date": {"transaction_date", "date", "txn_date", "value_date", "posting_date", "booking_date"},
    "status": {"status", "payment_status", "txn_status", "transaction_status"},
    "description": {"description", "narrative", "details", "memo", "remarks"},
}
REQUIRED_COLUMNS = ("reference", "amount", "transaction_date", "status")

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")


class FileFormatError(ValueError):
    """The file cannot be processed at all (unreadable, wrong type, missing columns)."""


@dataclass
class RowError:
    row_number: int
    reference: str | None
    errors: list[str]


@dataclass
class ParsedFile:
    filename: str
    file_type: str
    total_rows: int
    rows: list[tuple[int, TransactionCreate]] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)


def detect_file_type(filename: str) -> str:
    file_type = SUPPORTED_EXTENSIONS.get(Path(filename).suffix.lower())
    if file_type is None:
        raise FileFormatError(f"Unsupported file type '{Path(filename).suffix}'. Use .csv or .xlsx")
    return file_type


def _normalise_header(header: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(header).strip().lower()).strip("_")


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    lookup = {alias: canonical for canonical, aliases in COLUMN_ALIASES.items() for alias in aliases}
    renamed: dict[Any, str] = {}
    for column in df.columns:
        canonical = lookup.get(_normalise_header(column))
        if canonical and canonical not in renamed.values():
            renamed[column] = canonical
    df = df.rename(columns=renamed)[list(renamed.values())]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise FileFormatError(f"Missing required column(s): {', '.join(missing)}")
    return df


def read_dataframe(content: bytes, file_type: str) -> pd.DataFrame:
    try:
        if file_type == "csv":
            # Keep everything as text: references like "000123" must not lose leading zeros.
            return pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, encoding="utf-8-sig")
        return pd.read_excel(io.BytesIO(content), dtype=object, engine="openpyxl")
    except FileFormatError:
        raise
    except Exception as exc:  # pandas raises many different error types for malformed input
        raise FileFormatError(f"Could not read {file_type.upper()} file: {exc}") from exc


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def clean_amount(value: Any) -> Decimal | Any:
    """Accept '1,250.50', '$1250.50', '(45.00)' (accounting negative) and numeric cells."""
    if _is_blank(value):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[,\s$€£()]", "", text)
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return value  # let Pydantic report a readable error
    return -amount if negative else amount


def parse_date(value: Any) -> date | Any:
    if _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return value  # let Pydantic report a readable error


def _cell_text(value: Any) -> str | None:
    if _is_blank(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # Excel stores numeric references/accounts as floats
    return str(value).strip()


def _format_validation_error(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in err['loc']) or 'row'}: {err['msg']}" for err in exc.errors()]


def parse_transactions(content: bytes, filename: str) -> ParsedFile:
    file_type = detect_file_type(filename)
    df = normalise_columns(read_dataframe(content, file_type))
    df = df[~df.apply(lambda r: all(_is_blank(v) for v in r), axis=1)]  # drop fully empty lines

    parsed = ParsedFile(filename=filename, file_type=file_type, total_rows=len(df))
    for index, raw in df.iterrows():
        row_number = int(index) + 2  # +1 for the header row, +1 for 1-based numbering
        data = {
            "reference": _cell_text(raw.get("reference")),
            "account_number": _cell_text(raw.get("account_number")),
            "customer_name": _cell_text(raw.get("customer_name")),
            "amount": clean_amount(raw.get("amount")),
            "transaction_date": parse_date(raw.get("transaction_date")),
            "status": _cell_text(raw.get("status")),
            "description": _cell_text(raw.get("description")),
        }
        currency = _cell_text(raw.get("currency"))
        if currency:
            data["currency"] = currency
        try:
            parsed.rows.append((row_number, TransactionCreate(**data)))
        except ValidationError as exc:
            parsed.errors.append(RowError(row_number, data["reference"], _format_validation_error(exc)))

    logger.info(
        "Parsed file=%s type=%s total=%d valid=%d invalid=%d",
        filename,
        file_type,
        parsed.total_rows,
        len(parsed.rows),
        len(parsed.errors),
    )
    return parsed


def find_duplicate_references(rows: list[tuple[int, TransactionCreate]]) -> dict[str, list[int]]:
    """Return {reference: [row numbers]} for every reference that appears more than once."""
    positions: dict[str, list[int]] = defaultdict(list)
    for row_number, txn in rows:
        positions[txn.reference].append(row_number)
    return {ref: sorted(nums) for ref, nums in positions.items() if len(nums) > 1}
