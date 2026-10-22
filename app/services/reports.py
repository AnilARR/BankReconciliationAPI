"""Render reconciliation items as CSV or Excel for download."""

import io

import pandas as pd

from app.models import ReconciliationItem, ReconciliationRun

REPORT_COLUMNS = [
    "category",
    "reference",
    "file_row_number",
    "file_amount",
    "db_amount",
    "file_date",
    "db_date",
    "file_status",
    "db_status",
    "mismatched_fields",
    "details",
    "statement_record_id",
    "transaction_id",
]


def items_dataframe(items: list[ReconciliationItem]) -> pd.DataFrame:
    rows = [{col: getattr(item, col) for col in REPORT_COLUMNS} for item in items]
    return pd.DataFrame(rows, columns=REPORT_COLUMNS)


def to_csv(items: list[ReconciliationItem]) -> bytes:
    return items_dataframe(items).to_csv(index=False).encode("utf-8")


def to_excel(run: ReconciliationRun, items: list[ReconciliationItem]) -> bytes:
    summary = pd.DataFrame(
        [
            ("Run ID", run.id),
            ("Import batch", run.batch_id),
            ("Run by", run.run_by),
            ("Run at (UTC)", run.created_at.strftime("%Y-%m-%d %H:%M:%S")),
            ("Period", f"{run.period_start} to {run.period_end}"),
            ("Amount tolerance", str(run.amount_tolerance)),
            ("Date tolerance (days)", run.date_tolerance_days),
            ("File records", run.file_records),
            ("Matched", run.matched),
            ("Mismatched", run.mismatched),
            ("Missing in database", run.missing_in_database),
            ("Missing in file", run.missing_in_file),
            ("Duplicates in file", run.duplicates_in_file),
        ],
        columns=["Metric", "Value"],
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        items_dataframe(items).to_excel(writer, sheet_name="Unmatched", index=False)
    return buffer.getvalue()
