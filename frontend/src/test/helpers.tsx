import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { AppRoutes } from "../App";
import type { ReconciliationRun, User } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";

export interface Call {
  method: string;
  path: string;
  query: URLSearchParams;
  body: BodyInit | null | undefined;
}

type Handler = (call: Call) => unknown;

/** Route fetch calls to handlers keyed by "METHOD /path". Returns the list of calls made. */
export function mockApi(routes: Record<string, Handler | unknown>): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init: RequestInit = {}) => {
      const url = new URL(input, "http://localhost");
      const call: Call = { method: init.method ?? "GET", path: url.pathname, query: url.searchParams, body: init.body };
      calls.push(call);
      const key = `${call.method} ${call.path}`;
      if (!(key in routes)) return new Response(JSON.stringify({ detail: `No mock for ${key}` }), { status: 404 });
      const route = routes[key];
      const result = typeof route === "function" ? (route as Handler)(call) : route;
      if (result instanceof Response) return result;
      return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json" } });
    }),
  );
  return calls;
}

export const USERS: Record<string, User> = {
  admin: { id: 1, username: "admin", role: "admin", is_active: true, created_at: "2026-10-21T08:00:00Z" },
  analyst: { id: 2, username: "analyst", role: "analyst", is_active: true, created_at: "2026-10-21T08:00:00Z" },
  viewer: { id: 3, username: "viewer", role: "viewer", is_active: true, created_at: "2026-10-21T08:00:00Z" },
};

export const RUN: ReconciliationRun = {
  id: 7,
  batch_id: 3,
  run_by: "analyst",
  created_at: "2026-10-21T09:30:00Z",
  amount_tolerance: "0.00",
  date_tolerance_days: 0,
  period_start: "2026-10-21",
  period_end: "2026-10-21",
  file_records: 204,
  matched: 184,
  mismatched: 12,
  missing_in_database: 4,
  missing_in_file: 4,
  duplicates_in_file: 4,
};

/** Render the app signed in as `role` at `path`. */
export function renderApp(path: string, role: keyof typeof USERS | null = "analyst") {
  if (role) sessionStorage.setItem("recon.token", "test-token");
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

export const emptyPage = { total: 0, limit: 50, offset: 0, items: [] };
