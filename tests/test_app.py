from pathlib import Path

from alembic.config import Config

from alembic import command

ROOT = Path(__file__).resolve().parent.parent


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert response.headers["X-Request-ID"]


def test_request_id_is_propagated(client):
    assert client.get("/health", headers={"X-Request-ID": "abc123"}).headers["X-Request-ID"] == "abc123"


def test_openapi_documents_all_endpoints(client):
    spec = client.get("/openapi.json").json()
    assert "OAuth2PasswordBearer" in spec["components"]["securitySchemes"]
    for path in ("/api/v1/transactions", "/api/v1/imports", "/api/v1/reconciliations/{run_id}/report"):
        assert path in spec["paths"]
    assert client.get("/docs").status_code == 200


def test_alembic_migrations_match_models(tmp_path):
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'migrations.db'}")
    command.upgrade(config, "head")
    command.check(config)  # raises if the models and migrations have drifted apart
    command.downgrade(config, "base")
