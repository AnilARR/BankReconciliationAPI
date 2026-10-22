#!/bin/sh
set -e
python scripts/create_database.py
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
