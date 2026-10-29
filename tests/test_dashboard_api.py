from tests.conftest import csv_bytes


def test_empty_summary(client, viewer_headers):
    body = client.get("/api/v1/dashboard/summary", headers=viewer_headers).json()
    assert body["transaction_count"] == 0
    assert body["transaction_volume"] == "0"
    assert body["latest_run"] is None and body["recent_runs"] == [] and body["recent_imports"] == []


def test_summary_after_reconciliation(client, analyst_headers, viewer_headers):
    ledger = csv_bytes(
        "TXN-1,,,100.00,USD,2026-10-21,COMPLETED,",
        "TXN-2,,,50.50,USD,2026-10-21,COMPLETED,",
        "TXN-3,,,10.00,USD,2026-10-21,PENDING,",
    )
    client.post("/api/v1/transactions/import", files={"file": ("l.csv", ledger)}, headers=analyst_headers)
    bank = csv_bytes("TXN-1,,,100.00,USD,2026-10-21,COMPLETED,", "TXN-9,,,1.00,USD,2026-10-21,COMPLETED,")
    batch_id = client.post("/api/v1/imports", files={"file": ("b.csv", bank)}, headers=analyst_headers).json()["batch"][
        "id"
    ]
    client.post("/api/v1/reconciliations", json={"batch_id": batch_id}, headers=analyst_headers)

    body = client.get("/api/v1/dashboard/summary", params={"recent": 5}, headers=viewer_headers).json()
    assert body["transaction_count"] == 3
    assert float(body["transaction_volume"]) == 160.50
    assert {(s["status"], s["count"]) for s in body["transactions_by_status"]} == {("COMPLETED", 2), ("PENDING", 1)}
    assert (body["import_count"], body["run_count"]) == (1, 1)
    assert body["latest_run"]["matched"] == 1
    assert body["latest_run"]["missing_in_database"] == 1
    assert body["latest_run"]["missing_in_file"] == 2


def test_summary_requires_auth(client):
    assert client.get("/api/v1/dashboard/summary").status_code == 401
