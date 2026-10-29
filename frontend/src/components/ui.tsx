import { useEffect, useRef, useState, type ReactNode } from "react";

import type { Category, TransactionStatus } from "../api/types";
import { CATEGORY_LABELS } from "../utils/format";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Card({ title, actions, children, className = "" }: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-header">
          {title && <h2>{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint, color, active, onClick }: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  color?: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const content = (
    <>
      <span className="stat-label">
        {color && <span className="dot" style={{ background: color }} />}
        {label}
      </span>
      <span className="stat-value">{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </>
  );
  if (onClick) {
    return (
      <button type="button" className={`stat-card clickable ${active ? "active" : ""}`} onClick={onClick}
        aria-pressed={active}>
        {content}
      </button>
    );
  }
  return <div className="stat-card">{content}</div>;
}

export function CategoryBadge({ category }: { category: Category }) {
  return <span className={`badge cat-${category.toLowerCase()}`}>{CATEGORY_LABELS[category]}</span>;
}

export function StatusBadge({ status }: { status: TransactionStatus | string }) {
  return <span className={`badge status-${status.toLowerCase()}`}>{status}</span>;
}

export function Alert({ kind = "error", children }: { kind?: "error" | "success" | "info" | "warning"; children: ReactNode }) {
  return (
    <div className={`alert alert-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="spinner-wrap" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

export function Pagination({ total, limit, offset, onChange }: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="muted">
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <button type="button" className="btn btn-ghost" disabled={page === 1} onClick={() => onChange(offset - limit)}>
        ‹ Prev
      </button>
      <span>
        Page {page} / {pages}
      </span>
      <button type="button" className="btn btn-ghost" disabled={page === pages} onClick={() => onChange(offset + limit)}>
        Next ›
      </button>
    </nav>
  );
}

export function Modal({ title, open, onClose, children, wide }: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button type="button" className="btn btn-ghost icon" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function FileDropzone({ onFile, busy, hint = "CSV or Excel (.xlsx), up to 10 MB" }: {
  onFile: (file: File) => void;
  busy?: boolean;
  hint?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onFile(file);
  };

  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""} ${busy ? "busy" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!busy) pick(e.dataTransfer.files);
      }}
    >
      <div className="dropzone-icon" aria-hidden="true">⇪</div>
      {busy ? (
        <Spinner label="Uploading and validating…" />
      ) : (
        <>
          <p>
            <strong>Drag &amp; drop a file here</strong> or{" "}
            <button type="button" className="link-button" onClick={() => input.current?.click()}>
              browse
            </button>
          </p>
          <p className="muted small">{hint}</p>
        </>
      )}
      <input
        ref={input}
        type="file"
        accept=".csv,.xlsx"
        hidden
        data-testid="file-input"
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
