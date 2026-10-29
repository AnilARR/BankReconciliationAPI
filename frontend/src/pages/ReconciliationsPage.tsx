import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import { Alert, Card, EmptyState, PageHeader, Pagination, Spinner } from "../components/ui";
import { exceptionCount, formatDateTime, formatPercent, matchRate } from "../utils/format";
import { useAsync } from "../utils/useAsync";

const PAGE_SIZE = 20;

export function ReconciliationsPage() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading } = useAsync(() => api.listRuns({ limit: PAGE_SIZE, offset }), [offset]);

  return (
    <>
      <PageHeader title="Reconciliations" subtitle="Every reconciliation run, newest first." />
      <Card>
        {error && <Alert>{error}</Alert>}
        {loading && !data ? (
          <Spinner />
        ) : data && data.items.length === 0 ? (
          <EmptyState title="No reconciliation runs yet">
            Upload a file on <Link to="/imports">Daily imports</Link> and reconcile it.
          </EmptyState>
        ) : (
          data && (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Batch</th>
                      <th>Period</th>
                      <th className="num">File records</th>
                      <th className="num cat-text-matched">Matched</th>
                      <th className="num cat-text-mismatched">Mismatched</th>
                      <th className="num cat-text-missing_in_database">Missing in DB</th>
                      <th className="num cat-text-missing_in_file">Missing in file</th>
                      <th className="num cat-text-duplicate_in_file">Duplicates</th>
                      <th className="num">Match rate</th>
                      <th>Run</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((r) => (
                      <tr key={r.id}>
                        <td><Link to={`/reconciliations/${r.id}`}>#{r.id}</Link></td>
                        <td><Link to={`/imports/${r.batch_id}`}>#{r.batch_id}</Link></td>
                        <td className="nowrap small">{r.period_start} → {r.period_end}</td>
                        <td className="num">{r.file_records}</td>
                        <td className="num">{r.matched}</td>
                        <td className="num">{r.mismatched}</td>
                        <td className="num">{r.missing_in_database}</td>
                        <td className="num">{r.missing_in_file}</td>
                        <td className="num">{r.duplicates_in_file}</td>
                        <td className="num">
                          <strong>{formatPercent(matchRate(r))}</strong>
                          <span className="muted small"> · {exceptionCount(r)} exc.</span>
                        </td>
                        <td className="nowrap small">{r.run_by} · {formatDateTime(r.created_at)}</td>
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
    </>
  );
}
