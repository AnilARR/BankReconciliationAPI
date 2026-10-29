import type { Category } from "../api/types";

// Keep in sync with the --cat-* tokens in styles.css.
export const CATEGORY_COLORS: Record<Category, string> = {
  MATCHED: "#16a34a",
  MISMATCHED: "#d97706",
  MISSING_IN_DATABASE: "#dc2626",
  MISSING_IN_FILE: "#7c3aed",
  DUPLICATE_IN_FILE: "#0284c7",
};
