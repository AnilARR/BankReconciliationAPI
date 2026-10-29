import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { emptyPage, mockApi, renderApp, RUN, USERS } from "../test/helpers";

const summary = {
  transaction_count: 200,
  transaction_volume: "512345.67",
  transactions_by_status: [
    { status: "COMPLETED", count: 160, amount: "400000.00" },
    { status: "PENDING", count: 40, amount: "112345.67" },
  ],
  import_count: 1,
  run_count: 1,
  latest_run: RUN,
  recent_runs: [RUN],
  recent_imports: [
    { id: 3, filename: "bank_daily_file.csv", file_type: "csv", uploaded_by: "analyst",
      created_at: "2026-10-21T09:00:00Z", total_rows: 204, valid_rows: 204, invalid_rows: 0, duplicate_rows: 4 },
  ],
};

describe("authentication", () => {
  it("redirects to login, signs in and shows the dashboard", async () => {
    const calls = mockApi({
      "POST /api/v1/auth/token": { access_token: "jwt", expires_in: 3600 },
      "GET /api/v1/auth/me": USERS.analyst,
      "GET /api/v1/dashboard/summary": summary,
    });
    renderApp("/", null);

    await userEvent.type(await screen.findByLabelText("Username"), "analyst");
    await userEvent.type(screen.getByLabelText("Password"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    const login = calls.find((c) => c.path === "/api/v1/auth/token")!;
    expect(String(login.body)).toBe("username=analyst&password=secret-pass");
    expect(sessionStorage.getItem("recon.token")).toBe("jwt");
  });

  it("shows the API error on bad credentials", async () => {
    mockApi({
      "POST /api/v1/auth/token": () =>
        new Response(JSON.stringify({ detail: "Incorrect username or password" }), { status: 401 }),
    });
    renderApp("/login", null);
    await userEvent.type(screen.getByLabelText("Username"), "x");
    await userEvent.type(screen.getByLabelText("Password"), "y");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect username or password");
  });

  it("signs out when the token expires", async () => {
    mockApi({
      "GET /api/v1/auth/me": USERS.analyst,
      "GET /api/v1/dashboard/summary": () => new Response(JSON.stringify({ detail: "expired" }), { status: 401 }),
    });
    renderApp("/");
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(sessionStorage.getItem("recon.token")).toBeNull();
  });
});

describe("dashboard", () => {
  it("shows KPIs from the summary endpoint", async () => {
    mockApi({ "GET /api/v1/auth/me": USERS.viewer, "GET /api/v1/dashboard/summary": summary });
    renderApp("/", "viewer");
    expect(await screen.findByText("90.2%", { selector: ".stat-value" })).toBeInTheDocument();
    expect(screen.getByText("24", { selector: ".stat-value" })).toBeInTheDocument();
    expect(screen.getByText("bank_daily_file.csv")).toBeInTheDocument();
    // Viewers cannot upload.
    expect(screen.queryByRole("link", { name: "Upload daily file" })).not.toBeInTheDocument();
    // No admin-only navigation.
    expect(screen.queryByRole("link", { name: /Users/ })).not.toBeInTheDocument();
  });
});

describe("reconciliation detail", () => {
  it("lists exceptions and filters by category", async () => {
    const calls = mockApi({
      "GET /api/v1/auth/me": USERS.analyst,
      "GET /api/v1/reconciliations/7": RUN,
      "GET /api/v1/reconciliations/7/items": {
        total: 1, limit: 50, offset: 0,
        items: [{ id: 1, category: "MISMATCHED", reference: "TXN-2", statement_record_id: 1, transaction_id: 2,
          file_row_number: 3, file_amount: "205.00", db_amount: "200.00", file_date: "2026-10-21",
          db_date: "2026-10-21", file_status: "COMPLETED", db_status: "COMPLETED", mismatched_fields: "amount",
          details: "amount: file=205.00 db=200.00 (diff 5.00)" }],
      },
    });
    renderApp("/reconciliations/7");

    expect(await screen.findByRole("heading", { name: "Reconciliation run #7" })).toBeInTheDocument();
    const row = (await screen.findByText("TXN-2")).closest("tr")!;
    expect(within(row).getByText("$205.00").closest("td")).toHaveClass("diff");

    const itemCalls = () => calls.filter((c) => c.path === "/api/v1/reconciliations/7/items");
    expect(itemCalls()[0].query.get("exceptions_only")).toBe("true");

    await userEvent.click(screen.getByRole("button", { name: /Missing in file/ }));
    await waitFor(() => expect(itemCalls().at(-1)!.query.get("category")).toBe("MISSING_IN_FILE"));
    expect(itemCalls().at(-1)!.query.get("exceptions_only")).toBe("false");
  });
});

describe("daily imports", () => {
  it("uploads a file and offers to reconcile it", async () => {
    const calls = mockApi({
      "GET /api/v1/auth/me": USERS.analyst,
      "GET /api/v1/imports": emptyPage,
      "POST /api/v1/imports": {
        batch: { id: 9, filename: "daily.csv", file_type: "csv", uploaded_by: "analyst",
          created_at: "2026-10-21T09:00:00Z", total_rows: 3, valid_rows: 2, invalid_rows: 1, duplicate_rows: 0 },
        duplicates: [],
        errors: [{ row_number: 4, reference: "TXN-BAD", errors: ["amount: Input should be a valid decimal"] }],
      },
    });
    renderApp("/imports");

    const file = new File(["reference,amount\n"], "daily.csv", { type: "text/csv" });
    await userEvent.upload(await screen.findByTestId("file-input"), file);

    expect(await screen.findByText(/2 valid of 3 rows/)).toBeInTheDocument();
    expect(screen.getByText("TXN-BAD")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconcile batch #9" })).toBeInTheDocument();
    const upload = calls.find((c) => c.method === "POST" && c.path === "/api/v1/imports")!;
    expect((upload.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("hides upload for viewers", async () => {
    mockApi({ "GET /api/v1/auth/me": USERS.viewer, "GET /api/v1/imports": emptyPage });
    renderApp("/imports", "viewer");
    expect(await screen.findByText("No files imported yet")).toBeInTheDocument();
    expect(screen.queryByTestId("file-input")).not.toBeInTheDocument();
  });
});

describe("transactions", () => {
  it("sends search filters and sort to the API", async () => {
    const calls = mockApi({ "GET /api/v1/auth/me": USERS.analyst, "GET /api/v1/transactions": emptyPage });
    renderApp("/transactions");
    await screen.findByText("No transactions match these filters");

    await userEvent.type(screen.getByLabelText("Reference"), "TXN-2026");
    await userEvent.selectOptions(screen.getByLabelText("Status"), "PENDING");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      const last = calls.filter((c) => c.path === "/api/v1/transactions").at(-1)!;
      expect(last.query.get("reference")).toBe("TXN-2026");
      expect(last.query.get("status")).toBe("PENDING");
      expect(last.query.get("sort_by")).toBe("transaction_date");
      expect(last.query.has("customer_name")).toBe(false);
    });
  });

  it("creates a transaction and shows API validation errors", async () => {
    mockApi({
      "GET /api/v1/auth/me": USERS.analyst,
      "GET /api/v1/transactions": emptyPage,
      "POST /api/v1/transactions": () =>
        new Response(JSON.stringify({ detail: "Duplicate transaction reference" }), { status: 409 }),
    });
    renderApp("/transactions");
    await userEvent.click(await screen.findByRole("button", { name: "New transaction" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Reference *"), "TXN-1");
    await userEvent.type(within(dialog).getByLabelText("Amount *"), "10.50");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Duplicate transaction reference");
  });
});

describe("admin", () => {
  it("only admins can open the users page", async () => {
    mockApi({
      "GET /api/v1/auth/me": USERS.admin,
      "GET /api/v1/auth/users": Object.values(USERS),
    });
    renderApp("/users", "admin");
    expect(await screen.findByRole("heading", { name: "Users" })).toBeInTheDocument();
    expect(await screen.findByText("viewer", { selector: "td" })).toBeInTheDocument();
  });

  it("redirects non-admins away from users", async () => {
    mockApi({ "GET /api/v1/auth/me": USERS.analyst, "GET /api/v1/dashboard/summary": summary });
    renderApp("/users");
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });
});
