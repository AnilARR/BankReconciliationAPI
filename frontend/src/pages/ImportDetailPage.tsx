import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { DuplicatesTable } from "../components/ImportFeedback";
import { Alert, Card, EmptyState, PageHeader, Pagination, Spinner, StatCard, StatusBadge } from "../components/ui";
import { exceptionCount, formatDateTime, formatMoney, formatPercent, matchRate } from "../utils/format";
import { useAsync } from "../utils/useAsync";
import { ReconcileForm } from "./ReconcileForm";

const PAGE_SIZE = 50;

export function ImportDetailPage() {
  const batchId = Number(useParams().batchId);
  const { canWrite } = useAuth();
  const [tab, setTab] = useState<"records" | "duplicates">("records");
  const [duplicatesOnly, setDuplicatesOnly] = useState(false);
  const [offset, setOffset] = useState(0);

  const batch = useAsync(() => api.getImport(batchId), [batchId]);
  const runs = useAsync(() => api.listRuns({ batch_id: batchId, limit: 50, offset: 0 }), [batchId]);
  const records = useAsync(
    () => api.listRecords(batchId, { duplicates_only: duplicatesOnly, limit: PAGE_SIZE, offset }),
    [batchId, duplicatesOnly, offset],
  );
  const duplicates = useAsync(() => api.listDuplicates(batchId), [batchId]);

  if (batch.loading) return <Spinner />;
  if (batch.error || !batch.data) return <Alert>{batch.error ?? "Batch not found"}</Alert>;
  const b = batch.data;

  return (
    <>
      <PageHeader
        title={`Import batch #${b.id}`}
        subtitle={<>{b.filename} · uploaded by {b.uploaded_by} · {formatDateTime(b.created_at)}</>}
        actions={<Link to="/imports" className="btn btn-ghost">← All imports</Link>}
      />

      <div className="stat-grid">
        <StatCard label="Rows in file" value={b.total_rows} />
        <StatCard label="Valid rows stored" value={b.valid_rows} color="var(--cat-matched)" />
        <StatCard label="Invalid rows rejected" value={b.invalid_rows} color="var(--cat-missing_in_database)" />
        <StatCard label="Duplicate rows" value={b.duplicate_rows} color="var(--cat-duplicate_in_file)" />
      </div>

      {canWrite && (
        <Card title="Reconcile against the ledger">
          <ReconcileForm batchId={b.id} />
        </Card>
      )}

      <Card title="Reconciliation runs for this batch">
        {runs.data && runs.data.items.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Run</th><th>Run at</th><th>By</th><th className="num">Matched</th>
                  <th className="num">Exceptions</th><th className="num">Match rate</th><th>Tolerances</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.items.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/reconciliations/${r.id}`}>#{r.id}</Link></td>
                    <td className="nowrap">{formatDateTime(r.created_at)}</td>
                    <td>{r.run_by}</td>
                    <td className="num">{r.matched}</td>
                    <td className="num">{exceptionCount(r)}</td>
                    <td className="num">{formatPercent(matchRate(r))}</td>
                    <td className="small muted">±{r.amount_tolerance} · ±{r.date_tolerance_days}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="Not reconciled yet" />
        )}
      </Card>

      <Card>
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === "records"} className={tab === "records" ? "active" : ""}
            onClick={() => setTab("records")}>
            File records
          </button>
          <button type="button" role="tab" aria-selected={tab === "duplicates"}
            className={tab === "duplicates" ? "active" : ""} onClick={() => setTab("duplicates")}>
            Duplicate references {duplicates.data ? `(${duplicates.data.length})` : ""}
          </button>
        </div>

        {tab === "records" && (
          <>
            <label className="checkbox">
              <input type="checkbox" checked={duplicatesOnly}
                onChange={(e) => { setDuplicatesOnly(e.target.checked); setOffset(0); }} />
              Show repeated rows only
            </label>
            {records.error && <Alert>{records.error}</Alert>}
            {records.data && (
              <>
                <div className={`table-wrap ${records.loading ? "loading" : ""}`}>
                  <table>
                    <thead>
                      <tr>
                        <th className="num">Row</th><th>Reference</th><th>Customer</th><th>Account</th>
                        <th>Date</th><th className="num">Amount</th><th>Status</th><th />
                      </tr>
                    </thead>
                    <tbody>
                      {records.data.items.map((r) => (
                        <tr key={r.id} className={r.is_duplicate ? "row-flag" : ""}>
                          <td className="num">{r.row_number}</td>
                          <td className="mono">{r.reference}</td>
                          <td>{r.customer_name ?? "—"}</td>
                          <td className="mono small">{r.account_number ?? "—"}</td>
                          <td className="nowrap">{r.transaction_date}</td>
                          <td className="num">{formatMoney(r.amount, r.currency)}</td>
                          <td><StatusBadge status={r.status} /></td>
                          <td>{r.is_duplicate && <span className="badge cat-duplicate_in_file">Repeat</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination total={records.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
              </>
            )}
          </>
        )}

        {tab === "duplicates" &&
          (duplicates.data && duplicates.data.length > 0 ? (
            <DuplicatesTable duplicates={duplicates.data} />
          ) : (
            <EmptyState title="No duplicate references in this file" />
          ))}
      </Card>
    </>
  );
}
