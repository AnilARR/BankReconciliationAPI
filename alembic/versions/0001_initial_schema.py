"""Initial schema: users, ledger transactions, import batches, statement records, reconciliation.

Revision ID: 0001
Revises:
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("account_number", sa.String(34), nullable=True),
        sa.Column("customer_name", sa.Unicode(200), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("description", sa.Unicode(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transactions_reference", "transactions", ["reference"], unique=True)
    op.create_index("ix_transactions_account_number", "transactions", ["account_number"])
    op.create_index("ix_transactions_transaction_date", "transactions", ["transaction_date"])
    op.create_index("ix_transactions_status", "transactions", ["status"])

    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.Unicode(255), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("uploaded_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False),
    )

    op.create_table(
        "statement_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("account_number", sa.String(34), nullable=True),
        sa.Column("customer_name", sa.Unicode(200), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("description", sa.Unicode(500), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_statement_records_batch_id", "statement_records", ["batch_id"])
    op.create_index("ix_statement_records_reference", "statement_records", ["reference"])

    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_tolerance", sa.Numeric(18, 2), nullable=False),
        sa.Column("date_tolerance_days", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("file_records", sa.Integer(), nullable=False),
        sa.Column("matched", sa.Integer(), nullable=False),
        sa.Column("mismatched", sa.Integer(), nullable=False),
        sa.Column("missing_in_database", sa.Integer(), nullable=False),
        sa.Column("missing_in_file", sa.Integer(), nullable=False),
        sa.Column("duplicates_in_file", sa.Integer(), nullable=False),
    )
    op.create_index("ix_reconciliation_runs_batch_id", "reconciliation_runs", ["batch_id"])

    op.create_table(
        "reconciliation_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("statement_record_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("file_row_number", sa.Integer(), nullable=True),
        sa.Column("file_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("db_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("file_date", sa.Date(), nullable=True),
        sa.Column("db_date", sa.Date(), nullable=True),
        sa.Column("file_status", sa.String(20), nullable=True),
        sa.Column("db_status", sa.String(20), nullable=True),
        sa.Column("mismatched_fields", sa.String(200), nullable=True),
        sa.Column("details", sa.Unicode(1000), nullable=True),
    )
    op.create_index("ix_reconciliation_items_run_id", "reconciliation_items", ["run_id"])
    op.create_index("ix_reconciliation_items_category", "reconciliation_items", ["category"])
    op.create_index("ix_reconciliation_items_reference", "reconciliation_items", ["reference"])


def downgrade() -> None:
    op.drop_table("reconciliation_items")
    op.drop_table("reconciliation_runs")
    op.drop_table("statement_records")
    op.drop_table("import_batches")
    op.drop_table("transactions")
    op.drop_table("users")
