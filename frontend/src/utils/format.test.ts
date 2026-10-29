import { buildUrl, formatErrorDetail } from "../api/client";
import { RUN } from "../test/helpers";
import { exceptionCount, formatMoney, formatPercent, matchRate } from "./format";

describe("format helpers", () => {
  it("computes match rate excluding duplicates", () => {
    expect(matchRate(RUN)).toBeCloseTo(184 / 204);
    expect(formatPercent(matchRate(RUN))).toBe("90.2%");
    expect(exceptionCount(RUN)).toBe(24);
  });

  it("returns null match rate for an empty run", () => {
    expect(matchRate({ ...RUN, matched: 0, mismatched: 0, missing_in_database: 0, missing_in_file: 0 })).toBeNull();
    expect(formatPercent(null)).toBe("—");
  });

  it("formats money from decimal strings", () => {
    expect(formatMoney("1250.5")).toBe("$1,250.50");
    expect(formatMoney("-45.1", "EUR")).toBe("-€45.10");
    expect(formatMoney(null)).toBe("—");
  });
});

describe("api client helpers", () => {
  it("builds query strings and drops empty values", () => {
    expect(buildUrl("/api/v1/transactions", { reference: "TXN", status: "", limit: 25, x: undefined })).toBe(
      "/api/v1/transactions?reference=TXN&limit=25",
    );
  });

  it("formats FastAPI error bodies", () => {
    expect(formatErrorDetail("Duplicate transaction reference", "x")).toBe("Duplicate transaction reference");
    expect(formatErrorDetail([{ loc: ["body", "amount"], msg: "Input should be a valid decimal" }], "x")).toBe(
      "amount: Input should be a valid decimal",
    );
    expect(formatErrorDetail({ message: "File contains no valid rows", errors: [] }, "x")).toBe(
      "File contains no valid rows",
    );
    expect(formatErrorDetail(null, "fallback")).toBe("fallback");
  });
});
