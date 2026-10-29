import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { EmptyState, Spinner } from "./components/ui";
import { LoginPage } from "./pages/LoginPage";

// Route-level code splitting keeps the charting library out of the login bundle.
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const TransactionsPage = lazy(() => import("./pages/TransactionsPage").then((m) => ({ default: m.TransactionsPage })));
const ImportsPage = lazy(() => import("./pages/ImportsPage").then((m) => ({ default: m.ImportsPage })));
const ImportDetailPage = lazy(() => import("./pages/ImportDetailPage").then((m) => ({ default: m.ImportDetailPage })));
const ReconciliationsPage = lazy(() =>
  import("./pages/ReconciliationsPage").then((m) => ({ default: m.ReconciliationsPage })),
);
const ReconciliationDetailPage = lazy(() =>
  import("./pages/ReconciliationDetailPage").then((m) => ({ default: m.ReconciliationDetailPage })),
);
const UsersPage = lazy(() => import("./pages/UsersPage").then((m) => ({ default: m.UsersPage })));

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner label="Restoring session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  const { isAdmin } = useAuth();
  return isAdmin ? <>{children}</> : <Navigate to="/" replace />;
}

export function AppRoutes() {
  return (
    <Suspense fallback={<Spinner />}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<DashboardPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="imports" element={<ImportsPage />} />
        <Route path="imports/:batchId" element={<ImportDetailPage />} />
        <Route path="reconciliations" element={<ReconciliationsPage />} />
        <Route path="reconciliations/:runId" element={<ReconciliationDetailPage />} />
        <Route path="users" element={<AdminOnly><UsersPage /></AdminOnly>} />
        <Route path="*" element={<EmptyState title="Page not found"><Link to="/">Back to dashboard</Link></EmptyState>} />
      </Route>
    </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
