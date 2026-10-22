from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models import ReconciliationCategory as C
from app.services.reconciliation import ReconciliationConfig, compare_records, reconcile_records

DAY = date(2026, 10, 21)


def rec(id_, ref, amount="100.00", day=DAY, status="COMPLETED", row=None, currency="USD", account=None):
    return SimpleNamespace(
        id=id_,
        reference=ref,
        amount=Decimal(amount),
        transaction_date=day,
        status=status,
        currency=currency,
        account_number=account,
        row_number=row if row is not None else id_ + 1,
    )


def categories(results):
    return {(r.reference, r.category) for r in results}


def test_full_classification():
    file_records = [
        rec(1, "MATCH"),
        rec(2, "AMOUNT", amount="110.00"),
        rec(3, "STATUS", status="PENDING"),
        rec(4, "NEW"),
        rec(5, "MATCH"),
    ]
    ledger = {r.reference: r for r in [rec(10, "MATCH"), rec(11, "AMOUNT"), rec(12, "STATUS"), rec(13, "GONE")]}
    results = reconcile_records(file_records, ledger, ledger.values(), ReconciliationConfig())
    assert categories(results) == {
        ("MATCH", C.MATCHED),
        ("AMOUNT", C.MISMATCHED),
        ("STATUS", C.MISMATCHED),
        ("NEW", C.MISSING_IN_DATABASE),
        ("MATCH", C.DUPLICATE_IN_FILE),
        ("GONE", C.MISSING_IN_FILE),
    }
    amount_item = next(r for r in results if r.reference == "AMOUNT")
    assert amount_item.mismatched_fields == ["amount"]
    assert "diff 10.00" in amount_item.details
    duplicate = next(r for r in results if r.category is C.DUPLICATE_IN_FILE)
    assert duplicate.file_row_number == 6 and "row 2" in duplicate.details


def test_first_occurrence_is_reconciled_even_if_listed_later():
    file_records = [rec(2, "A", amount="5.00", row=9), rec(1, "A", row=3)]
    results = reconcile_records(file_records, {"A": rec(10, "A")}, [], ReconciliationConfig())
    by_cat = {r.category: r for r in results}
    assert by_cat[C.MATCHED].file_row_number == 3
    assert by_cat[C.DUPLICATE_IN_FILE].file_row_number == 9


def test_tolerances():
    config = ReconciliationConfig(amount_tolerance=Decimal("0.05"), date_tolerance_days=1)
    assert compare_records(rec(1, "A", "100.04", date(2026, 10, 20)), rec(2, "A"), config) == {}
    diffs = compare_records(rec(1, "A", "100.06", date(2026, 10, 19)), rec(2, "A"), config)
    assert set(diffs) == {"amount", "transaction_date"}


def test_currency_and_account_compared_only_when_present():
    config = ReconciliationConfig()
    assert set(compare_records(rec(1, "A", currency="EUR", account="X"), rec(2, "A", account="Y"), config)) == {
        "currency",
        "account_number",
    }
    assert compare_records(rec(1, "A", account=None), rec(2, "A", account="Y"), config) == {}


def test_empty_file():
    assert reconcile_records([], {}, [rec(1, "A")], ReconciliationConfig())[0].category is C.MISSING_IN_FILE
