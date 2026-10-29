import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { CategoryDonut, CategoryLegend, RunTrendChart } from "../components/charts";
import { Alert, Card, EmptyState, PageHeader, Spinner, StatCard, StatusBadge } from "../components/ui";
import {
  exceptionCount,
  formatCompactMoney,
  formatDateTime,
  formatMoney,
  formatNumber,
  formatPercent,
  matchRate,
} from "../utils/format";
import { useAsync } from "../utils/useAsync";

export function DashboardPage() {
  const { canWrite } = useAuth();
  const { data, error, loading } = useAsync(() => api.dashboard(10), []);

  if (loading) return <Spinner />;
  if (error || !data) return <Alert>{error ?? "Could not load dashboard"}</Alert>;

  const latest = data.latest_run;
  const maxStatus = Math.max(1, ...data.transactions_by_status.map((s) => s.count));

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Overview of the ledger, daily imports and the latest reconciliation."
        actions={canWrite && <Link to="/imports" className="btn btn-primary">Upload daily file</Link>}
      />

      <div className="stat-grid">
        <StatCard label="Ledger transactions" value={formatNumber(data.transaction_count)}
          hint={`${formatCompactMoney(data.transaction_volume)} total volume`} />
        <StatCard label="Daily files imported" value={formatNumber(data.import_count)}
          hint={`${formatNumber(data.run_count)} reconciliation runs`} />
        <StatCard label="Match rate (latest run)" value={latest ? formatPercent(matchRate(latest)) : "—"}
          hint={latest ? `${formatNumber(latest.matched)} of ${formatNumber(latest.file_records)} file records` : "No runs yet"}
          color="var(--cat-matched)" />
        <StatCard label="Open exceptions (latest run)" value={latest ? formatNumber(exceptionCount(latest)) : "—"}
          hint={latest ? <Link to={`/reconciliations/${latest.id}`}>Review run #{latest.id} →</Link> : "Run a reconciliation"}
          color="var(--cat-missing_in_database)" />
      </div>

      {latest ? (
        <div className="grid-2">
          <Card title={`Latest reconciliation · run #${latest.id}`}
            actions={<Link to={`/reconciliations/${latest.id}`} className="btn btn-ghost">Open</Link>}>
            <div className="donut-row">
              <CategoryDonut run={latest} />
              <div>
                <CategoryLegend run={latest} />
                <p className="muted small">
                  Batch #{latest.batch_id} · {latest.period_start} → {latest.period_end}
                  <br />
                  Run by {latest.run_by} · {formatDateTime(latest.created_at)}
                </p>
              </div>
            </div>
          </Card>
          <Card title="Reconciliation trend" actions={<span className="muted small">last {data.recent_runs.length} runs</span>}>
            <RunTrendChart runs={data.recent_runs} />
          </Card>
        </div>
      ) : (
        <Card>
          <EmptyState title="No reconciliations yet">
            Upload the bank's daily file on <Link to="/imports">Daily imports</Link>, then reconcile it against the
            ledger.
          </EmptyState>
        </Card>
      )}

      <div className="grid-2">
        <Card title="Recent daily files" actions={<Link to="/imports" className="btn btn-ghost">All imports</Link>}>
          {data.recent_imports.length === 0 ? (
            <EmptyState title="No files imported" />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Batch</th>
                    <th>File</th>
                    <th className="num">Valid</th>
                    <th className="num">Invalid</th>
                    <th className="num">Duplicates</th>
                    <th>Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_imports.map((b) => (
                    <tr key={b.id}>
                      <td><Link to={`/imports/${b.id}`}>#{b.id}</Link></td>
                      <td className="truncate">{b.filename}</td>
                      <td className="num">{b.valid_rows}</td>
                      <td className={`num ${b.invalid_rows ? "text-danger" : ""}`}>{b.invalid_rows}</td>
                      <td className={`num ${b.duplicate_rows ? "text-warning" : ""}`}>{b.duplicate_rows}</td>
                      <td className="nowrap">{formatDateTime(b.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Ledger by status" actions={<Link to="/transactions" className="btn btn-ghost">Transactions</Link>}>
          {data.transactions_by_status.length === 0 ? (
            <EmptyState title="Ledger is empty">Load transactions from the Transactions page.</EmptyState>
          ) : (
            <ul className="status-bars">
              {data.transactions_by_status.map((s) => (
                <li key={s.status}>
                  <StatusBadge status={s.status} />
                  <div className="bar-track">
                    <div className={`bar-fill status-fill-${s.status.toLowerCase()}`}
                      style={{ width: `${(s.count / maxStatus) * 100}%` }} />
                  </div>
                  <span className="num">{formatNumber(s.count)}</span>
                  <span className="num muted">{formatMoney(s.amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
