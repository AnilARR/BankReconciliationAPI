import os

# Configure before the app is imported. Set TEST_DATABASE_URL to run the suite against SQL Server.
os.environ["RECON_DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["RECON_JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["RECON_PASSWORD_HASH_ITERATIONS"] = "1000"
os.environ["RECON_LOG_LEVEL"] = "WARNING"
os.environ.pop("RECON_ADMIN_USERNAME", None)
os.environ.pop("RECON_ADMIN_PASSWORD", None)

import io  # noqa: E402

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402

PASSWORD = "S3cure-test-pass"
CSV_HEADER = "reference,account_number,customer_name,amount,currency,transaction_date,status,description\n"


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for role in UserRole:
            db.add(User(username=role.value, hashed_password=hash_password(PASSWORD), role=role.value))
        db.add(User(username="disabled", hashed_password=hash_password(PASSWORD), role="admin", is_active=False))
        db.commit()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/token", data={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return _login(client, "admin")


@pytest.fixture
def analyst_headers(client):
    return _login(client, "analyst")


@pytest.fixture
def viewer_headers(client):
    return _login(client, "viewer")


def csv_bytes(*rows: str) -> bytes:
    return (CSV_HEADER + "\n".join(rows) + "\n").encode()


def xlsx_bytes(records: list[dict]) -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame(records).to_excel(buffer, index=False)
    return buffer.getvalue()
