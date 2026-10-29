import { Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Spinner } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▦", end: true },
  { to: "/transactions", label: "Transactions", icon: "⇄" },
  { to: "/imports", label: "Daily imports", icon: "⇪" },
  { to: "/reconciliations", label: "Reconciliations", icon: "✓" },
];

export function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const links = isAdmin ? [...NAV, { to: "/users", label: "Users", icon: "◎" }] : NAV;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">✓</span>
          <div>
            <strong>ReconDesk</strong>
            <span>Transaction reconciliation</span>
          </div>
        </div>
        <nav>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className={({ isActive }) => (isActive ? "active" : "")}>
              <span className="nav-icon" aria-hidden="true">{link.icon}</span>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-chip">
            <span className="avatar" aria-hidden="true">{user?.username.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{user?.username}</strong>
              <span className="role">{user?.role}</span>
            </div>
          </div>
          <button type="button" className="btn btn-sidebar" onClick={logout}>
            Sign out
          </button>
          <p className="synthetic-note">Synthetic data only</p>
        </div>
      </aside>
      <main className="content">
        {/* Keep the sidebar on screen while a lazily loaded page downloads. */}
        <Suspense fallback={<Spinner />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}
