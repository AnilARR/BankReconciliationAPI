import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/endpoints";
import type { ReconciliationRequest } from "../api/types";
import { Alert } from "../components/ui";

/** Starts a reconciliation run for a batch and opens the result. */
export function ReconcileForm({ batchId, compact }: { batchId: number; compact?: boolean }) {
  const navigate = useNavigate();
  const [amountTolerance, setAmountTolerance] = useState("");
  const [dateTolerance, setDateTolerance] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [showOptions, setShowOptions] = useState(!compact);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: ReconciliationRequest = { batch_id: batchId };
    if (amountTolerance) body.amount_tolerance = amountTolerance;
    if (dateTolerance) body.date_tolerance_days = Number(dateTolerance);
    if (periodStart) body.period_start = periodStart;
    if (periodEnd) body.period_end = periodEnd;
    try {
      const run = await api.reconcile(body);
      navigate(`/reconciliations/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reconciliation failed");
      setBusy(false);
    }
  };

  return (
    <form className="reconcile-form" onSubmit={submit} aria-label="Run reconciliation">
      {showOptions && (
        <div className="filters">
          <label>
            Amount tolerance
            <input type="number" step="0.01" min="0" placeholder="0.00 (default)" value={amountTolerance}
              onChange={(e) => setAmountTolerance(e.target.value)} />
          </label>
          <label>
            Date tolerance (days)
            <input type="number" min="0" max="31" placeholder="0 (default)" value={dateTolerance}
              onChange={(e) => setDateTolerance(e.target.value)} />
          </label>
          <label>
            Period start
            <input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          </label>
          <label>
            Period end
            <input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
          </label>
        </div>
      )}
      <div className="form-actions start">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Reconciling…" : `Reconcile batch #${batchId}`}
        </button>
        {!showOptions && (
          <button type="button" className="btn btn-ghost" onClick={() => setShowOptions(true)}>
            Tolerances &amp; period…
          </button>
        )}
        {showOptions && (
          <span className="muted small">Leave blank to use the defaults and the file's own date range.</span>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
    </form>
  );
}
