import { download, request } from "./client";
import type {
  Category,
  DashboardSummary,
  DuplicateReference,
  ImportBatch,
  LedgerImportResult,
  Page,
  ReconciliationItem,
  ReconciliationRequest,
  ReconciliationRun,
  Role,
  StatementImportResult,
  StatementRecord,
  Transaction,
  TransactionInput,
  TransactionStatus,
  User,
} from "./types";

const V1 = "/api/v1";

function fileForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

export interface TransactionSearch {
  reference?: string;
  account_number?: string;
  customer_name?: string;
  status?: TransactionStatus | "";
  currency?: string;
  min_amount?: string;
  max_amount?: string;
  date_from?: string;
  date_to?: string;
  sort_by?: "transaction_date" | "amount" | "reference" | "created_at";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; expires_in: number }>(`${V1}/auth/token`, {
      form: new URLSearchParams({ username, password }),
      auth: false,
    }),
  me: () => request<User>(`${V1}/auth/me`),
  listUsers: () => request<User[]>(`${V1}/auth/users`),
  createUser: (body: { username: string; password: string; role: Role }) =>
    request<User>(`${V1}/auth/users`, { json: body }),

  dashboard: (recent = 10) => request<DashboardSummary>(`${V1}/dashboard/summary`, { query: { recent } }),

  searchTransactions: (q: TransactionSearch) =>
    request<Page<Transaction>>(`${V1}/transactions`, { query: { ...q } }),
  createTransaction: (body: TransactionInput) => request<Transaction>(`${V1}/transactions`, { json: body }),
  updateTransaction: (id: number, body: Partial<TransactionInput>) =>
    request<Transaction>(`${V1}/transactions/${id}`, { method: "PATCH", json: body }),
  importLedger: (file: File) =>
    request<LedgerImportResult>(`${V1}/transactions/import`, { form: fileForm(file) }),

  uploadStatement: (file: File) => request<StatementImportResult>(`${V1}/imports`, { form: fileForm(file) }),
  listImports: (limit: number, offset: number) =>
    request<Page<ImportBatch>>(`${V1}/imports`, { query: { limit, offset } }),
  getImport: (id: number) => request<ImportBatch>(`${V1}/imports/${id}`),
  listRecords: (id: number, q: { duplicates_only?: boolean; limit: number; offset: number }) =>
    request<Page<StatementRecord>>(`${V1}/imports/${id}/records`, { query: q }),
  listDuplicates: (id: number) => request<DuplicateReference[]>(`${V1}/imports/${id}/duplicates`),

  reconcile: (body: ReconciliationRequest) => request<ReconciliationRun>(`${V1}/reconciliations`, { json: body }),
  listRuns: (q: { batch_id?: number; limit: number; offset: number }) =>
    request<Page<ReconciliationRun>>(`${V1}/reconciliations`, { query: q }),
  getRun: (id: number) => request<ReconciliationRun>(`${V1}/reconciliations/${id}`),
  listItems: (
    id: number,
    q: { category?: Category; exceptions_only?: boolean; reference?: string; limit: number; offset: number },
  ) =>
    request<Page<ReconciliationItem>>(`${V1}/reconciliations/${id}/items`, { query: q }),
  downloadReport: (id: number, format: "csv" | "xlsx", includeMatched = false) =>
    download(
      `${V1}/reconciliations/${id}/report`,
      { format, include_matched: includeMatched },
      `unmatched_report_run_${id}.${format}`,
    ),
};
