"""Create the target SQL Server database if it does not exist (SQL Server containers start without it).

Reads RECON_DATABASE_URL, connects to ``master`` and issues CREATE DATABASE. No-op for non-mssql URLs.
"""

import re
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import get_settings


def main(retries: int = 30, delay: float = 2.0) -> None:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("mssql"):
        print(f"Skipping database creation for {url.drivername}")
        return
    database = url.database
    if not database or not re.fullmatch(r"[A-Za-z0-9_]+", database):
        sys.exit(f"Invalid database name: {database!r}")

    engine = create_engine(url.set(database="master"), isolation_level="AUTOCOMMIT")
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text(f"IF DB_ID(N'{database}') IS NULL CREATE DATABASE [{database}]"))
            print(f"Database '{database}' is ready")
            return
        except Exception as exc:  # SQL Server may still be starting up
            print(f"Waiting for SQL Server ({attempt}/{retries}): {exc.__class__.__name__}")
            time.sleep(delay)
    sys.exit("SQL Server did not become available in time")


if __name__ == "__main__":
    main()
