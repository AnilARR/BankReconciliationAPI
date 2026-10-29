import io
from datetime import date

import pandas as pd

from app.config import get_settings
from tests.conftest import csv_bytes, xlsx_bytes

LEDGER = csv_bytes(
    "TXN-001,ACC-1,Synthetic A,100.00,USD,2026-10-21,COMPLETED,",
    "TXN-002,ACC-2,Synthetic B,200.00,USD,2026-10-21,COMPLETED,",
    "TXN-003,ACC-3,Synthetic C,300.00,USD,2026-10-21,PENDING,",
    "TXN-004,ACC-4,Synthetic D,400.00,USD,2026-10-20,COMPLETED,",
    "TXN-005,ACC-5,Synthetic E,500.00,USD,2026-10-21,COMPLETED,",
    "TXN-OLD,ACC-6,Synthetic F,600.00,USD,2026-09-01,COMPLETED,",
)
BANK_FILE = csv_bytes(
    "TXN-001,ACC-1,Synthetic A,100.00,USD,2026-10-21,COMPLETED,",  # matched
    "TXN-002,ACC-2,Synthetic B,205.00,USD,2026-10-21,COMPLETED,",  # amount mismatch
    "TXN-003,ACC-3,Synthetic C,300.00,USD,2026-10-21,SETTLED,",  # status mismatch
    "TXN-004,ACC-4,Synthetic D,400.00,USD,2026-10-21,COMPLETED,",  # date mismatch
    "TXN-999,ACC-9,Synthetic Z,50.00,USD,2026-10-21,COMPLETED,",  # missing in database
    "TXN-001,ACC-1,Synthetic A,100.00,USD,2026-10-21,COMPLETED,",  # duplicate
    "TXN-BAD,ACC-1,Synthetic A,xyz,USD,2026-10-21,COMPLETED,",  # invalid row
)  # TXN-005 is missing from the file; TXN-OLD is outside the file's period


def upload(client, headers, content=BANK_FILE, name="bank_daily_file.csv"):
    return client.post("/api/v1/imports", files={"file": (name, content)}, headers=headers)


def seed_ledger(client, headers):
    response = client.post("/api/v1/transactions/import", files={"file": ("ledger.csv", LEDGER)}, headers=headers)
    assert response.json()["inserted"] == 6


def test_upload_statement(client, analyst_headers):
    response = upload(client, analyst_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["batch"] | {"id": 0, "created_at": None} == {
        "id": 0,
        "created_at": None,
        "filename": "bank_daily_file.csv",
        "file_type": "csv",
        "uploaded_by": "analyst",
        "total_rows": 7,
        "valid_rows": 6,
        "invalid_rows": 1,
        "duplicate_rows": 1,
    }
    assert body["duplicates"][0]["reference"] == "TXN-001"
    assert body["errors"][0]["reference"] == "TXN-BAD"

    batch_id = body["batch"]["id"]
    dups = client.get(f"/api/v1/imports/{batch_id}/duplicates", headers=analyst_headers).json()
    assert dups == [{"reference": "TXN-001", "row_numbers": [2, 7], "occurrences": 2}]
    records = client.get(
        f"/api/v1/imports/{batch_id}/records", params={"duplicates_only": True}, headers=analyst_headers
    ).json()
    assert records["total"] == 1 and records["items"][0]["row_number"] == 7
    assert client.get("/api/v1/imports", headers=analyst_headers).json()["total"] == 1
    assert client.get("/api/v1/imports/12345", headers=analyst_headers).status_code == 404


def test_upload_rejections(client, analyst_headers, viewer_headers):
    assert upload(client, viewer_headers).status_code == 403
    assert upload(client, analyst_headers, b"", "empty.csv").status_code == 400
    assert upload(client, analyst_headers, b"a,b\n1,2\n", "bad.csv").status_code == 422
    assert upload(client, analyst_headers, b"x", "file.txt").status_code == 422
    only_invalid = upload(client, analyst_headers, csv_bytes("TXN-1,,,oops,USD,2026-10-21,COMPLETED,"))
    assert only_invalid.status_code == 422
    assert only_invalid.json()["detail"]["errors"][0]["row_number"] == 2


def test_upload_size_limit(client, analyst_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 0)
    assert upload(client, analyst_headers).status_code == 413


def test_upload_excel(client, analyst_headers):
    content = xlsx_bytes(
        [
            {"Reference": "TXN-X1", "Amount": 10.5, "Date": date(2026, 10, 21), "Status": "completed"},
            {"Reference": "TXN-X2", "Amount": 20, "Date": date(2026, 10, 21), "Status": "failed"},
        ]
    )
    response = upload(client, analyst_headers, content, "daily.xlsx")
    assert response.status_code == 201, response.text
    assert response.json()["batch"]["file_type"] == "xlsx"
    assert response.json()["batch"]["valid_rows"] == 2


def test_end_to_end_reconciliation(client, analyst_headers, viewer_headers):
    seed_ledger(client, analyst_headers)
    batch_id = upload(client, analyst_headers).json()["batch"]["id"]

    response = client.post("/api/v1/reconciliations", json={"batch_id": batch_id}, headers=analyst_headers)
    assert response.status_code == 201, response.text
    run = response.json()
    assert {
        k: run[k]
        for k in (
            "file_records",
            "matched",
            "mismatched",
            "missing_in_database",
            "missing_in_file",
            "duplicates_in_file",
            "period_start",
            "period_end",
        )
    } == {
        "file_records": 6,
        "matched": 1,
        "mismatched": 3,
        "missing_in_database": 1,
        "missing_in_file": 1,
        "duplicates_in_file": 1,
        "period_start": "2026-10-21",
        "period_end": "2026-10-21",
    }

    items = client.get(
        f"/api/v1/reconciliations/{run['id']}/items", params={"category": "MISMATCHED"}, headers=viewer_headers
    ).json()["items"]
    fields = {i["reference"]: i["mismatched_fields"] for i in items}
    assert fields == {"TXN-002": "amount", "TXN-003": "status", "TXN-004": "transaction_date"}

    exceptions = client.get(
        f"/api/v1/reconciliations/{run['id']}/items", params={"exceptions_only": True}, headers=viewer_headers
    ).json()
    assert exceptions["total"] == 6 and all(i["category"] != "MATCHED" for i in exceptions["items"])

    report = client.get(f"/api/v1/reconciliations/{run['id']}/report", headers=viewer_headers).json()
    assert {i["category"] for i in report["items"]} == {
        "MISMATCHED",
        "MISSING_IN_DATABASE",
        "MISSING_IN_FILE",
        "DUPLICATE_IN_FILE",
    }
    assert len(report["items"]) == 6
    missing_file = next(i for i in report["items"] if i["category"] == "MISSING_IN_FILE")
    assert missing_file["reference"] == "TXN-005"

    csv_resp = client.get(
        f"/api/v1/reconciliations/{run['id']}/report", params={"format": "csv"}, headers=viewer_headers
    )
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv_resp.headers["content-disposition"]
    assert len(pd.read_csv(io.StringIO(csv_resp.text))) == 6

    xlsx_resp = client.get(
        f"/api/v1/reconciliations/{run['id']}/report",
        params={"format": "xlsx", "include_matched": True},
        headers=viewer_headers,
    )
    sheets = pd.read_excel(io.BytesIO(xlsx_resp.content), sheet_name=None)
    assert set(sheets) == {"Summary", "Unmatched"} and len(sheets["Unmatched"]) == 7

    runs = client.get("/api/v1/reconciliations", params={"batch_id": batch_id}, headers=viewer_headers).json()
    assert runs["total"] == 1


def test_reconciliation_with_tolerances(client, analyst_headers):
    seed_ledger(client, analyst_headers)
    batch_id = upload(client, analyst_headers).json()["batch"]["id"]
    run = client.post(
        "/api/v1/reconciliations",
        json={"batch_id": batch_id, "amount_tolerance": "5.00", "date_tolerance_days": 1},
        headers=analyst_headers,
    ).json()
    assert (run["matched"], run["mismatched"]) == (3, 1)  # only the status mismatch remains


def test_reconciliation_custom_period(client, analyst_headers):
    seed_ledger(client, analyst_headers)
    batch_id = upload(client, analyst_headers).json()["batch"]["id"]
    run = client.post(
        "/api/v1/reconciliations",
        json={"batch_id": batch_id, "period_start": "2026-09-01", "period_end": "2026-10-31"},
        headers=analyst_headers,
    ).json()
    assert run["missing_in_file"] == 2  # TXN-005 and TXN-OLD


def test_reconciliation_errors(client, analyst_headers, viewer_headers):
    assert client.post("/api/v1/reconciliations", json={"batch_id": 999}, headers=analyst_headers).status_code == 404
    batch_id = upload(client, analyst_headers).json()["batch"]["id"]
    assert (
        client.post("/api/v1/reconciliations", json={"batch_id": batch_id}, headers=viewer_headers).status_code == 403
    )
    bad_period = {"batch_id": batch_id, "period_start": "2026-10-22", "period_end": "2026-10-01"}
    assert client.post("/api/v1/reconciliations", json=bad_period, headers=analyst_headers).status_code == 422
    assert client.get("/api/v1/reconciliations/999", headers=viewer_headers).status_code == 404
