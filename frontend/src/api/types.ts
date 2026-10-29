// Mirrors the Pydantic response models in app/schemas.py. Money values arrive as decimal strings.

export type Role = "viewer" | "analyst" | "admin";
export type TransactionStatus = "PENDING" | "COMPLETED" | "FAILED" | "REVERSED";
export type Category =
  | "MATCHED"
  | "MISMATCHED"
  | "MISSING_IN_DATABASE"
  | "MISSING_IN_FILE"
  | "DUPLICATE_IN_FILE";

export const TRANSACTION_STATUSES: TransactionStatus[] = ["PENDING", "COMPLETED", "FAILED", "REVERSED"];
export const CATEGORIES: Category[] = [
  "MATCHED",
  "MISMATCHED",
  "MISSING_IN_DATABASE",
  "MISSING_IN_FILE",
  "DUPLICATE_IN_FILE",
];

export interface Page<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface User {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface Transaction {
  id: number;
  reference: string;
  account_number: string | null;
  customer_name: string | null;
  amount: string;
  currency: string;
  transaction_date: string;
  status: TransactionStatus;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransactionInput {
  reference: string;
  account_number: string | null;
  customer_name: string | null;
  amount: string;
  currency: string;
  transaction_date: string;
  status: TransactionStatus;
  description: string | null;
}

export interface RowError {
  row_number: number;
  reference: string | null;
  errors: string[];
}

export interface DuplicateReference {
  reference: string;
  row_numbers: number[];
  occurrences: number;
}

export interface LedgerImportResult {
  filename: string;
  total_rows: number;
  inserted: number;
  invalid_rows: number;
  skipped_existing: string[];
  duplicates: DuplicateReference[];
  errors: RowError[];
}

export interface ImportBatch {
  id: number;
  filename: string;
  file_type: string;
  uploaded_by: string;
  created_at: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
}

export interface StatementImportResult {
  batch: ImportBatch;
  duplicates: DuplicateReference[];
  errors: RowError[];
}

export interface StatementRecord {
  id: number;
  batch_id: number;
  row_number: number;
  reference: string;
  account_number: string | null;
  customer_name: string | null;
  amount: string;
  currency: string;
  transaction_date: string;
  status: string;
  description: string | null;
  is_duplicate: boolean;
}

export interface ReconciliationRun {
  id: number;
  batch_id: number;
  run_by: string;
  created_at: string;
  amount_tolerance: string;
  date_tolerance_days: number;
  period_start: string | null;
  period_end: string | null;
  file_records: number;
  matched: number;
  mismatched: number;
  missing_in_database: number;
  missing_in_file: number;
  duplicates_in_file: number;
}

export interface ReconciliationRequest {
  batch_id: number;
  amount_tolerance?: string;
  date_tolerance_days?: number;
  period_start?: string;
  period_end?: string;
}

export interface ReconciliationItem {
  id: number;
  category: Category;
  reference: string;
  statement_record_id: number | null;
  transaction_id: number | null;
  file_row_number: number | null;
  file_amount: string | null;
  db_amount: string | null;
  file_date: string | null;
  db_date: string | null;
  file_status: string | null;
  db_status: string | null;
  mismatched_fields: string | null;
  details: string | null;
}

export interface StatusTotal {
  status: string;
  count: number;
  amount: string;
}

export interface DashboardSummary {
  transaction_count: number;
  transaction_volume: string;
  transactions_by_status: StatusTotal[];
  import_count: number;
  run_count: number;
  latest_run: ReconciliationRun | null;
  recent_runs: ReconciliationRun[];
  recent_imports: ImportBatch[];
}
