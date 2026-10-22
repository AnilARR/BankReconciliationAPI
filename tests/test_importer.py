from datetime import date
from decimal import Decimal

import pytest

from app.models import TransactionStatus
from app.services.importer import (
    FileFormatError,
    clean_amount,
    find_duplicate_references,
    parse_date,
    parse_transactions,
)
from tests.conftest import csv_bytes, xlsx_bytes


def test_parses_valid_csv():
    parsed = parse_transactions(csv_bytes("txn-1,ACC1,Synthetic A,100.50,usd,2026-10-21,settled,Card"), "daily.csv")
    assert parsed.total_rows == 1 and not parsed.errors
    row_number, txn = parsed.rows[0]
    assert row_number == 2
    assert txn.reference == "TXN-1"
    assert txn.amount == Decimal("100.50")
    assert txn.currency == "USD"
    assert txn.status is TransactionStatus.COMPLETED
    assert txn.transaction_date == date(2026, 10, 21)


def test_collects_row_errors_with_row_numbers():
    parsed = parse_transactions(
        csv_bytes(
            "TXN-1,,,100.00,USD,2026-10-21,COMPLETED,",
            "TXN-2,,,not-a-number,USD,2026-10-21,COMPLETED,",
            ",,,5.00,USD,2026-10-21,COMPLETED,",
            "TXN-4,,,5.00,USD,2026-13-45,COMPLETED,",
            "TXN-5,,,5.00,USD,2026-10-21,LOST,",
            "TXN-6,,,5.001,USD,2026-10-21,COMPLETED,",
        ),
        "daily.csv",
    )
    assert len(parsed.rows) == 1
    errors = {e.row_number: e for e in parsed.errors}
    assert set(errors) == {3, 4, 5, 6, 7}
    assert any("amount" in msg for msg in errors[3].errors)
    assert any("reference" in msg for msg in errors[4].errors)
    assert any("transaction_date" in msg for msg in errors[5].errors)
    assert any("status" in msg for msg in errors[6].errors)
    assert any("amount" in msg for msg in errors[7].errors)


def test_header_aliases_and_optional_columns():
    content = b'Txn Ref,Value Date,Amount,Payment Status\nABC-1,21/10/2026,"1,250.00",Posted\n'
    parsed = parse_transactions(content, "file.CSV")
    _, txn = parsed.rows[0]
    assert (txn.reference, txn.transaction_date, txn.amount, txn.currency) == (
        "ABC-1",
        date(2026, 10, 21),
        Decimal("1250.00"),
        "USD",
    )


def test_missing_required_column():
    with pytest.raises(FileFormatError, match="transaction_date"):
        parse_transactions(b"reference,amount,status\nA,1,COMPLETED\n", "x.csv")


def test_unsupported_extension():
    with pytest.raises(FileFormatError, match="Unsupported"):
        parse_transactions(b"whatever", "x.pdf")


def test_corrupt_excel_file():
    with pytest.raises(FileFormatError, match="Could not read"):
        parse_transactions(b"this is not a zip", "x.xlsx")


def test_parses_excel_with_native_types():
    content = xlsx_bytes(
        [
            {
                "reference": "TXN-9",
                "amount": 99.95,
                "transaction_date": date(2026, 10, 20),
                "status": "Success",
                "account_number": 12345678,
            },
        ]
    )
    parsed = parse_transactions(content, "daily.xlsx")
    assert not parsed.errors
    _, txn = parsed.rows[0]
    assert txn.amount == Decimal("99.95")
    assert txn.transaction_date == date(2026, 10, 20)
    assert txn.account_number == "12345678"


def test_blank_lines_are_ignored():
    parsed = parse_transactions(csv_bytes("TXN-1,,,1.00,USD,2026-10-21,COMPLETED,", ",,,,,,,"), "d.csv")
    assert parsed.total_rows == 1 and len(parsed.rows) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1,000.25", Decimal("1000.25")), ("$12", Decimal("12")), ("(45.10)", Decimal("-45.10")), (7.5, Decimal("7.5"))],
)
def test_clean_amount(raw, expected):
    assert clean_amount(raw) == expected


@pytest.mark.parametrize("raw", ["2026-10-21", "21/10/2026", "21-10-2026", "2026/10/21", "2026-10-21 00:00:00"])
def test_parse_date_formats(raw):
    assert parse_date(raw) == date(2026, 10, 21)


def test_find_duplicate_references():
    parsed = parse_transactions(
        csv_bytes(
            "TXN-1,,,1.00,USD,2026-10-21,COMPLETED,",
            "TXN-2,,,1.00,USD,2026-10-21,COMPLETED,",
            "txn-1,,,1.00,USD,2026-10-21,COMPLETED,",
        ),
        "d.csv",
    )
    assert find_duplicate_references(parsed.rows) == {"TXN-1": [2, 4]}
