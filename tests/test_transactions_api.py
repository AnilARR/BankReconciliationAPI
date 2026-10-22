from tests.conftest import csv_bytes

URL = "/api/v1/transactions"


def payload(**overrides):
    data = {
        "reference": "TXN-20261021-000001",
        "account_number": "GB00SYNT00000000000001",
        "customer_name": "Synthetic Customer 001",
        "amount": "150.25",
        "currency": "USD",
        "transaction_date": "2026-10-21",
        "status": "COMPLETED",
    }
    data.update(overrides)
    return data


def create(client, headers, **overrides):
    response = client.post(URL, json=payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_get(client, analyst_headers, viewer_headers):
    created = create(client, analyst_headers, reference=" txn-abc ")
    assert created["reference"] == "TXN-ABC"
    assert client.get(f"{URL}/{created['id']}", headers=viewer_headers).json()["amount"] == "150.25"
    assert client.get(f"{URL}/by-reference/txn-abc", headers=viewer_headers).status_code == 200
    assert client.get(f"{URL}/999999", headers=viewer_headers).status_code == 404


def test_duplicate_reference_rejected(client, analyst_headers):
    create(client, analyst_headers)
    response = client.post(URL, json=payload(), headers=analyst_headers)
    assert response.status_code == 409


def test_validation_errors(client, analyst_headers):
    for bad in ({"amount": "1.234"}, {"currency": "US"}, {"status": "MAYBE"}, {"reference": "bad ref!"}):
        assert client.post(URL, json=payload(**bad), headers=analyst_headers).status_code == 422, bad


def test_viewer_cannot_write(client, viewer_headers):
    assert client.post(URL, json=payload(), headers=viewer_headers).status_code == 403


def test_patch_and_put(client, analyst_headers):
    txn = create(client, analyst_headers)
    other = create(client, analyst_headers, reference="TXN-OTHER")

    response = client.patch(
        f"{URL}/{txn['id']}", json={"status": "reversed", "amount": "10.00"}, headers=analyst_headers
    )
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["amount"]) == ("REVERSED", "10.00")

    conflict = client.patch(f"{URL}/{txn['id']}", json={"reference": "TXN-OTHER"}, headers=analyst_headers)
    assert conflict.status_code == 409
    assert client.patch(f"{URL}/{txn['id']}", json={"amount": None}, headers=analyst_headers).status_code == 422

    replaced = client.put(
        f"{URL}/{other['id']}", json=payload(reference="TXN-OTHER", amount="1.00"), headers=analyst_headers
    )
    assert replaced.status_code == 200 and replaced.json()["amount"] == "1.00"


def test_search_filters_and_paging(client, analyst_headers, viewer_headers):
    create(client, analyst_headers, reference="TXN-A", amount="10.00", status="PENDING", transaction_date="2026-10-01")
    create(client, analyst_headers, reference="TXN-B", amount="20.00", customer_name="Synthetic Jane")
    create(client, analyst_headers, reference="PAY-C", amount="30.00", transaction_date="2026-10-25")

    def search(**params):
        response = client.get(URL, params=params, headers=viewer_headers)
        assert response.status_code == 200, response.text
        return response.json()

    assert search()["total"] == 3
    assert {i["reference"] for i in search(reference="txn")["items"]} == {"TXN-A", "TXN-B"}
    assert search(status="PENDING")["items"][0]["reference"] == "TXN-A"
    assert search(customer_name="jane")["items"][0]["reference"] == "TXN-B"
    assert search(min_amount="15", max_amount="25")["total"] == 1
    assert search(date_from="2026-10-22", date_to="2026-10-31")["total"] == 1
    page = search(sort_by="amount", sort_order="asc", limit=2, offset=1)
    assert page["total"] == 3 and [i["reference"] for i in page["items"]] == ["TXN-B", "PAY-C"]
    assert search(reference="%")["total"] == 0  # wildcards are escaped


def test_bulk_import_into_ledger(client, analyst_headers):
    create(client, analyst_headers, reference="TXN-EXISTING")
    content = csv_bytes(
        "TXN-1,,,1.00,USD,2026-10-21,COMPLETED,",
        "TXN-2,,,2.00,USD,2026-10-21,PENDING,",
        "TXN-1,,,1.00,USD,2026-10-21,COMPLETED,",
        "TXN-EXISTING,,,9.00,USD,2026-10-21,COMPLETED,",
        "TXN-BAD,,,abc,USD,2026-10-21,COMPLETED,",
    )
    response = client.post(
        f"{URL}/import", files={"file": ("ledger.csv", content, "text/csv")}, headers=analyst_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["inserted"] == 2
    assert body["skipped_existing"] == ["TXN-EXISTING"]
    assert body["duplicates"] == [{"reference": "TXN-1", "row_numbers": [2, 4], "occurrences": 2}]
    assert body["invalid_rows"] == 1 and body["errors"][0]["row_number"] == 6
    assert client.get(URL, headers=analyst_headers).json()["total"] == 3
