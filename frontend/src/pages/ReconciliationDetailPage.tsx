import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/endpoints";
import { CATEGORIES, type Category } from "../api/types";
import { CategoryDonut } from "../components/charts";
import { Alert, Card, CategoryBadge, EmptyState, PageHeader, Pagination, Spinner, StatCard } from "../components/ui";
import { CATEGORY_COLORS } from "../utils/colors";
import { CATEGORY_DESCRIPTIONS, CATEGORY_LABELS, exceptionCount, formatDateTime, formatMoney, runCounts } from "../utils/format";
import { useAsync } from "../utils/useAsync";

const PAGE_SIZE = 50;
const EXCEPTIONS = "EXCEPTIONS";
type Filter = Category | typeof EXCEPTIONS | "ALL";

export function ReconciliationDetailPage() {
  const runId = Number(useParams().runId);
  const [filter, setFilter] = useState<Filter>(EXCEPTIONS);
  const [referenceDraft, setReferenceDraft] = useState("");
  const [reference, setReference] = useState("");
  const [offset, setOffset] = useState(0);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"csv" | "xlsx" | null>(null);

  const run = useAsync(() => api.getRun(runId), [runId]);
  const items = useAsync(
    () =>
      api.listItems(runId, {
        category: filter === "ALL" || filter === EXCEPTIONS ? undefined : filter,
        exceptions_only: filter === EXCEPTIONS,
        reference: reference || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [runId, filter, reference, offset],
  );

  if (run.loading) return <Spinner />;
  if (run.error || !run.data) return <Alert>{run.error ?? "Run not found"}</Alert>;
  const r = run.data;
  const counts = runCounts(r);

  const choose = (f: Filter) => {
    setFilter(f);
    setOffset(0);
  };

  const searchReference = (e: FormEvent) => {
    e.preventDefault();
    setOffset(0);
    setReference(referenceDraft.trim());
  };

  const downloadReport = async (format: "csv" | "xlsx") => {
    setDownloading(format);
    setDownloadError(null);
    try {
      await api.downloadReport(r.id, format);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(null);
    }
  };

  return (
    <>
      <PageHeader
        title={`Reconciliation run #${r.id}`}
        subtitle={
          <>
            <Link to={`/imports/${r.batch_id}`}>Batch #{r.batch_id}</Link> · period {r.period_start} → {r.period_end} ·
            tolerance ±{formatMoney(r.amount_tolerance)} / ±{r.date_tolerance_days} day(s) · run by {r.run_by},{" "}
            {formatDateTime(r.created_at)}
          </>
        }
        actions={
          <>
            <button type="button" className="btn btn-secondary" disabled={downloading !== null} onClick={() => downloadReport("csv")}>
              {downloading === "csv" ? "Preparing…" : "Download CSV"}
            </button>
            <button type="button" className="btn btn-primary" disabled={downloading !== null} onClick={() => downloadReport("xlsx")}>
              {downloading === "xlsx" ? "Preparing…" : "Download Excel"}
            </button>
          </>
        }
      />
      {downloadError && <Alert>{downloadError}</Alert>}

      <div className="run-summary">
        <Card className="donut-card">
          <CategoryDonut run={r} height={220} />
          <p className="muted small center">
            {r.file_records} file records · {exceptionCount(r)} exceptions
          </p>
        </Card>
        <div className="stat-grid stat-grid-5">
          {CATEGORIES.map((c) => (
            <StatCard key={c} label={CATEGORY_LABELS[c]} value={counts[c]} hint={CATEGORY_DESCRIPTIONS[c]}
              color={CATEGORY_COLORS[c]} active={filter === c} onClick={() => choose(filter === c ? EXCEPTIONS : c)} />
          ))}
        </div>
      </div>

      <Card>
        <div className="toolbar">
          <div className="tabs" role="tablist">
            {([EXCEPTIONS, "ALL", ...CATEGORIES] as Filter[]).map((f) => (
              <button key={f} type="button" role="tab" aria-selected={filter === f} className={filter === f ? "active" : ""}
                onClick={() => choose(f)}>
                {f === EXCEPTIONS ? "All exceptions" : f === "ALL" ? "Everything" : CATEGORY_LABELS[f]}
              </button>
            ))}
          </div>
          <form onSubmit={searchReference} className="inline-search">
            <input placeholder="Exact reference" value={referenceDraft} onChange={(e) => setReferenceDraft(e.target.value)}
              aria-label="Filter by reference" />
            <button type="submit" className="btn btn-ghost">Find</button>
          </form>
        </div>

        {items.error && <Alert>{items.error}</Alert>}
        {items.loading && !items.data ? (
          <Spinner />
        ) : items.data && items.data.items.length === 0 ? (
          <EmptyState title="Nothing in this view" />
        ) : (
          items.data && (
            <>
              <div className={`table-wrap ${items.loading ? "loading" : ""}`}>
                <table>
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Reference</th>
                      <th className="num">File row</th>
                      <th className="num">Amount <span className="sub">file / ledger</span></th>
                      <th>Date <span className="sub">file / ledger</span></th>
                      <th>Status <span className="sub">file / ledger</span></th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.data.items.map((i) => {
                      const fields = new Set(i.mismatched_fields?.split(",") ?? []);
                      const diff = (field: string) => (fields.has(field) ? "diff" : "");
                      return (
                        <tr key={i.id}>
                          <td><CategoryBadge category={i.category} /></td>
                          <td className="mono">{i.reference}</td>
                          <td className="num">{i.file_row_number ?? "—"}</td>
                          <td className={`num ${diff("amount")}`}>
                            <Pair file={formatMoney(i.file_amount)} ledger={formatMoney(i.db_amount)} />
                          </td>
                          <td className={`nowrap ${diff("transaction_date")}`}>
                            <Pair file={i.file_date ?? "—"} ledger={i.db_date ?? "—"} />
                          </td>
                          <td className={diff("status")}>
                            <Pair file={i.file_status ?? "—"} ledger={i.db_status ?? "—"} />
                          </td>
                          <td className="details">{i.details ?? ""}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination total={items.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
            </>
          )
        )}
      </Card>
    </>
  );
}

/** File value above ledger value, so differences line up vertically. */
function Pair({ file, ledger }: { file: string; ledger: string }) {
  return (
    <span className="pair">
      <span title="Bank file">{file}</span>
      <span title="Ledger" className="ledger">{ledger}</span>
    </span>
  );
}
