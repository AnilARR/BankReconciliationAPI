import { useState, type FormEvent } from "react";

import { api } from "../api/endpoints";
import type { Role } from "../api/types";
import { Alert, Card, PageHeader, Spinner } from "../components/ui";
import { formatDateTime } from "../utils/format";
import { useAsync } from "../utils/useAsync";

const ROLE_HELP: Record<Role, string> = {
  viewer: "Read-only access to transactions, imports and reports",
  analyst: "Can upload files, run reconciliations and edit transactions",
  admin: "Full access, including user management",
};

export function UsersPage() {
  const users = useAsync(() => api.listUsers(), []);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const user = await api.createUser({ username, password, role });
      setMessage({ kind: "success", text: `User ${user.username} created with role ${user.role}.` });
      setUsername("");
      setPassword("");
      users.reload();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not create user" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Users" subtitle="Manage who can access the reconciliation system." />
      <div className="grid-2">
        <Card title="Create user">
          <form className="form" onSubmit={submit}>
            <label>Username<input value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3}
              maxLength={100} pattern="[A-Za-z0-9_.\-]+" /></label>
            <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              minLength={8} autoComplete="new-password" /></label>
            <label>
              Role
              <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                <option value="viewer">viewer</option>
                <option value="analyst">analyst</option>
                <option value="admin">admin</option>
              </select>
              <span className="muted small">{ROLE_HELP[role]}</span>
            </label>
            {message && <Alert kind={message.kind}>{message.text}</Alert>}
            <div className="form-actions start">
              <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Creating…" : "Create user"}</button>
            </div>
          </form>
        </Card>
        <Card title="Existing users">
          {users.loading ? <Spinner /> : users.error ? <Alert>{users.error}</Alert> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Username</th><th>Role</th><th>Status</th><th>Created</th></tr></thead>
                <tbody>
                  {users.data?.map((u) => (
                    <tr key={u.id}>
                      <td>{u.username}</td>
                      <td><span className={`badge role-${u.role}`}>{u.role}</span></td>
                      <td>{u.is_active ? "Active" : "Disabled"}</td>
                      <td className="nowrap">{formatDateTime(u.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
