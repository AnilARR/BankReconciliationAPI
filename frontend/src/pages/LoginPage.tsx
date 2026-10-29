import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Alert } from "../components/ui";

export function LoginPage() {
  const { user, login } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-panel">
        <div className="brand brand-dark">
          <span className="brand-mark" aria-hidden="true">✓</span>
          <div>
            <strong>ReconDesk</strong>
            <span>Banking transaction reconciliation</span>
          </div>
        </div>
        <h1>Sign in</h1>
        <p className="muted">Use the account created by your administrator.</p>
        <form onSubmit={submit} className="form">
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required
              autoFocus />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password" required />
          </label>
          {error && <Alert>{error}</Alert>}
          <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="muted small login-note">Learning project — synthetic customer and transaction data only.</p>
      </div>
      <div className="login-aside" aria-hidden="true">
        <h2>Daily reconciliation, at a glance</h2>
        <ul>
          <li>Import the bank's daily CSV or Excel file</li>
          <li>Match every payment against the ledger</li>
          <li>Investigate mismatched, missing and duplicate items</li>
          <li>Export unmatched reports to CSV or Excel</li>
        </ul>
      </div>
    </div>
  );
}
