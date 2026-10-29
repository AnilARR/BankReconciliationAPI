import type { Category, ReconciliationRun } from "../api/types";

const moneyFormatters = new Map<string, Intl.NumberFormat>();

export function formatMoney(value: string | number | null | undefined, currency = "USD"): string {
  if (value === null || value === undefined || value === "") return "—";
  let formatter = moneyFormatters.get(currency);
  if (!formatter) {
    formatter = new Intl.NumberFormat("en-US", { style: "currency", currency });
    moneyFormatters.set(currency, formatter);
  }
  return formatter.format(Number(value));
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatCompactMoney(value: string | number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value));
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const CATEGORY_LABELS: Record<Category, string> = {
  MATCHED: "Matched",
  MISMATCHED: "Mismatched",
  MISSING_IN_DATABASE: "Missing in database",
  MISSING_IN_FILE: "Missing in file",
  DUPLICATE_IN_FILE: "Duplicate in file",
};

export const CATEGORY_DESCRIPTIONS: Record<Category, string> = {
  MATCHED: "Reference found and every compared field agrees",
  MISMATCHED: "Reference found but amount, date, status, currency or account differs",
  MISSING_IN_DATABASE: "In the bank file but not in the ledger",
  MISSING_IN_FILE: "In the ledger for this period but not in the bank file",
  DUPLICATE_IN_FILE: "Reference repeated in the bank file",
};

/** Run counts keyed by category. */
export function runCounts(run: ReconciliationRun): Record<Category, number> {
  return {
    MATCHED: run.matched,
    MISMATCHED: run.mismatched,
    MISSING_IN_DATABASE: run.missing_in_database,
    MISSING_IN_FILE: run.missing_in_file,
    DUPLICATE_IN_FILE: run.duplicates_in_file,
  };
}

export function exceptionCount(run: ReconciliationRun): number {
  return run.mismatched + run.missing_in_database + run.missing_in_file + run.duplicates_in_file;
}

/**
 * Share of reconciled items that matched. Duplicates are excluded from the denominator because the first
 * occurrence of each reference is already counted in another category.
 */
export function matchRate(run: ReconciliationRun): number | null {
  const reconciled = run.matched + run.mismatched + run.missing_in_database + run.missing_in_file;
  return reconciled === 0 ? null : run.matched / reconciled;
}

export function formatPercent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}
