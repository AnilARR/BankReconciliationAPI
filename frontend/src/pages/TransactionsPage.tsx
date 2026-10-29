import { useState, type FormEvent } from "react";

import { api, type TransactionSearch } from "../api/endpoints";
import { TRANSACTION_STATUSES, type LedgerImportResult, type Transaction, type TransactionInput } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { DuplicatesTable, RowErrorsTable } from "../components/ImportFeedback";
import { Alert, Card, EmptyState, FileDropzone, Modal, PageHeader, Pagination, Spinner, StatusBadge } from "../components/ui";
import { formatMoney } from "../utils/format";
import { useAsync } from "../utils/useAsync";

const PAGE_SIZE = 25;
type SortKey = NonNullable<TransactionSearch["sort_by"]>;

const EMPTY_FILTERS: TransactionSearch = {
  reference: "",
  customer_name: "",
  account_number: "",
  status: "",
  date_from: "",
  date_to: "",
  min_amount: "",
  max_amount: "",
};

export function TransactionsPage() {
  const { canWrite } = useAuth();
  const [draft, setDraft] = useState<TransactionSearch>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<TransactionSearch>(EMPTY_FILTERS);
  const [sort, setSort] = useState<{ by: SortKey; order: "asc" | "desc" }>({ by: "transaction_date", order: "desc" });
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<Transaction | "new" | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const { data, error, loading, reload } = useAsync(
    () => api.searchTransactions({ ...filters, sort_by: sort.by, sort_order: sort.order, limit: PAGE_SIZE, offset }),
    [filters, sort, offset],
  );

  const applyFilters = (e: FormEvent) => {
    e.preventDefault();
    setOffset(0);
    setFilters(draft);
  };

  const toggleSort = (by: SortKey) => {
    setOffset(0);
    setSort((s) => ({ by, order: s.by === by && s.order === "desc" ? "asc" : "desc" }));
  };

  const sortHeader = (by: SortKey, label: string, className = "") => (
    <th className={className} aria-sort={sort.by === by ? (sort.order === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" className="sort-button" onClick={() => toggleSort(by)}>
        {label} {sort.by === by ? (sort.order === "asc" ? "▲" : "▼") : ""}
      </button>
    </th>
  );

  const set = (key: keyof TransactionSearch) => (e: { target: { value: string } }) =>
    setDraft((d) => ({ ...d, [key]: e.target.value }));

  return (
    <>
      <PageHeader
        title="Transactions"
        subtitle="The bank's ledger — the database side of reconciliation."
        actions={
          canWrite && (
            <>
              <button type="button" className="btn btn-secondary" onClick={() => setImportOpen(true)}>
                Import ledger file
              </button>
              <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>
                New transaction
              </button>
            </>
          )
        }
      />

      <Card>
        <form className="filters" onSubmit={applyFilters} aria-label="Search transactions">
          <label>Reference<input value={draft.reference} onChange={set("reference")} placeholder="e.g. TXN-2026" /></label>
          <label>Customer<input value={draft.customer_name} onChange={set("customer_name")} placeholder="Name contains" /></label>
          <label>Account<input value={draft.account_number} onChange={set("account_number")} placeholder="Exact account" /></label>
          <label>
            Status
            <select value={draft.status} onChange={set("status")}>
              <option value="">Any</option>
              {TRANSACTION_STATUSES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label>From<input type="date" value={draft.date_from} onChange={set("date_from")} /></label>
          <label>To<input type="date" value={draft.date_to} onChange={set("date_to")} /></label>
          <label>Min amount<input type="number" step="0.01" value={draft.min_amount} onChange={set("min_amount")} /></label>
          <label>Max amount<input type="number" step="0.01" value={draft.max_amount} onChange={set("max_amount")} /></label>
          <div className="filter-actions">
            <button type="submit" className="btn btn-primary">Search</button>
            <button type="button" className="btn btn-ghost" onClick={() => { setDraft(EMPTY_FILTERS); setFilters(EMPTY_FILTERS); setOffset(0); }}>
              Reset
            </button>
          </div>
        </form>
      </Card>

      <Card title={data ? `${data.total} transactions` : "Transactions"}>
        {error && <Alert>{error}</Alert>}
        {loading && !data ? (
          <Spinner />
        ) : data && data.items.length === 0 ? (
          <EmptyState title="No transactions match these filters" />
        ) : (
          data && (
            <>
              <div className={`table-wrap ${loading ? "loading" : ""}`}>
                <table>
                  <thead>
                    <tr>
                      {sortHeader("reference", "Reference")}
                      <th>Customer</th>
                      <th>Account</th>
                      {sortHeader("transaction_date", "Date")}
                      {sortHeader("amount", "Amount", "num")}
                      <th>Status</th>
                      <th>Description</th>
                      {canWrite && <th aria-label="Actions" />}
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((t) => (
                      <tr key={t.id}>
                        <td className="mono">{t.reference}</td>
                        <td>{t.customer_name ?? "—"}</td>
                        <td className="mono small">{t.account_number ?? "—"}</td>
                        <td className="nowrap">{t.transaction_date}</td>
                        <td className="num">{formatMoney(t.amount, t.currency)}</td>
                        <td><StatusBadge status={t.status} /></td>
                        <td className="truncate muted">{t.description ?? ""}</td>
                        {canWrite && (
                          <td className="row-actions">
                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(t)}>Edit</button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
            </>
          )
        )}
      </Card>

      {editing && (
        <TransactionFormModal
          transaction={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
      <LedgerImportModal open={importOpen} onClose={() => setImportOpen(false)} onImported={reload} />
    </>
  );
}

function toInput(t: Transaction | null): TransactionInput {
  return {
    reference: t?.reference ?? "",
    account_number: t?.account_number ?? "",
    customer_name: t?.customer_name ?? "",
    amount: t?.amount ?? "",
    currency: t?.currency ?? "USD",
    transaction_date: t?.transaction_date ?? new Date().toISOString().slice(0, 10),
    status: t?.status ?? "PENDING",
    description: t?.description ?? "",
  };
}

export function TransactionFormModal({ transaction, onClose, onSaved }: {
  transaction: Transaction | null;
  onClose: () => void;
  onSaved: (t: Transaction) => void;
}) {
  const [form, setForm] = useState<TransactionInput>(() => toInput(transaction));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (key: keyof TransactionInput) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: TransactionInput = {
      ...form,
      account_number: form.account_number || null,
      customer_name: form.customer_name || null,
      description: form.description || null,
    };
    try {
      const saved = transaction ? await api.updateTransaction(transaction.id, body) : await api.createTransaction(body);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={transaction ? `Edit ${transaction.reference}` : "New transaction"} open onClose={onClose}>
      <form className="form form-grid" onSubmit={submit}>
        <label>Reference *<input value={form.reference} onChange={set("reference")} required maxLength={64} /></label>
        <label>Amount *<input type="number" step="0.01" value={form.amount} onChange={set("amount")} required /></label>
        <label>Date *<input type="date" value={form.transaction_date} onChange={set("transaction_date")} required /></label>
        <label>
          Status *
          <select value={form.status} onChange={set("status")}>
            {TRANSACTION_STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label>Currency *<input value={form.currency} onChange={set("currency")} required maxLength={3} pattern="[A-Za-z]{3}" /></label>
        <label>Account number<input value={form.account_number ?? ""} onChange={set("account_number")} maxLength={34} /></label>
        <label className="span-2">Customer name<input value={form.customer_name ?? ""} onChange={set("customer_name")} maxLength={200} /></label>
        <label className="span-2">Description<input value={form.description ?? ""} onChange={set("description")} maxLength={500} /></label>
        {error && <div className="span-2"><Alert>{error}</Alert></div>}
        <div className="span-2 form-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </Modal>
  );
}

function LedgerImportModal({ open, onClose, onImported }: { open: boolean; onClose: () => void; onImported: () => void }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<LedgerImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.importLedger(file));
      onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    setResult(null);
    setError(null);
    onClose();
  };

  return (
    <Modal title="Import ledger transactions" open={open} onClose={close} wide>
      <p className="muted">
        Loads transactions into the ledger. Existing references and repeated rows are skipped and reported.
      </p>
      <FileDropzone onFile={upload} busy={busy} />
      {error && <Alert>{error}</Alert>}
      {result && (
        <div className="stack">
          <Alert kind={result.invalid_rows ? "warning" : "success"}>
            <strong>{result.filename}</strong>: {result.inserted} inserted of {result.total_rows} rows ·{" "}
            {result.skipped_existing.length} already in ledger · {result.duplicates.length} duplicated references ·{" "}
            {result.invalid_rows} invalid
          </Alert>
          {result.errors.length > 0 && (<><h3>Invalid rows</h3><RowErrorsTable errors={result.errors} /></>)}
          {result.duplicates.length > 0 && (<><h3>Duplicate references in file</h3><DuplicatesTable duplicates={result.duplicates} /></>)}
        </div>
      )}
    </Modal>
  );
}
