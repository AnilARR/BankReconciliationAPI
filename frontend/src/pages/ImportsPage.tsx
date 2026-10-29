import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import type { StatementImportResult } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { DuplicatesTable, RowErrorsTable } from "../components/ImportFeedback";
import { Alert, Card, EmptyState, FileDropzone, PageHeader, Pagination, Spinner } from "../components/ui";
import { formatDateTime } from "../utils/format";
import { useAsync } from "../utils/useAsync";
import { ReconcileForm } from "./ReconcileForm";

const PAGE_SIZE = 20;

export function ImportsPage() {
  const { canWrite } = useAuth();
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [result, setResult] = useState<StatementImportResult | null>(null);
  const { data, error, loading, reload } = useAsync(() => api.listImports(PAGE_SIZE, offset), [offset]);

  const upload = async (file: File) => {
    setBusy(true);
    setUploadError(null);
    setResult(null);
    try {
      setResult(await api.uploadStatement(file));
      setOffset(0);
      reload();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Daily imports" subtitle="Upload the bank's daily transaction file and reconcile it against the ledger." />

      {canWrite && (
        <Card title="Upload daily file">
          <FileDropzone onFile={upload} busy={busy} />
          {uploadError && <Alert>{uploadError}</Alert>}
          {result && <UploadResult result={result} />}
        </Card>
      )}

      <Card title="Import history">
        {error && <Alert>{error}</Alert>}
        {loading && !data ? (
          <Spinner />
        ) : data && data.items.length === 0 ? (
          <EmptyState title="No files imported yet" />
        ) : (
          data && (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Batch</th>
                      <th>File</th>
                      <th>Type</th>
                      <th className="num">Rows</th>
                      <th className="num">Valid</th>
                      <th className="num">Invalid</th>
                      <th className="num">Duplicates</th>
                      <th>Uploaded by</th>
                      <th>Uploaded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((b) => (
                      <tr key={b.id}>
                        <td><Link to={`/imports/${b.id}`}>#{b.id}</Link></td>
                        <td className="truncate">{b.filename}</td>
                        <td className="upper small">{b.file_type}</td>
                        <td className="num">{b.total_rows}</td>
                        <td className="num">{b.valid_rows}</td>
                        <td className={`num ${b.invalid_rows ? "text-danger" : ""}`}>{b.invalid_rows}</td>
                        <td className={`num ${b.duplicate_rows ? "text-warning" : ""}`}>{b.duplicate_rows}</td>
                        <td>{b.uploaded_by}</td>
                        <td className="nowrap">{formatDateTime(b.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
            </>
          )
        )}
      </Card>
    </>
  );
}

function UploadResult({ result }: { result: StatementImportResult }) {
  const { batch, errors, duplicates } = result;
  return (
    <div className="stack">
      <Alert kind={batch.invalid_rows || batch.duplicate_rows ? "warning" : "success"}>
        <strong>{batch.filename}</strong> imported as <Link to={`/imports/${batch.id}`}>batch #{batch.id}</Link>:{" "}
        {batch.valid_rows} valid of {batch.total_rows} rows · {batch.invalid_rows} invalid · {batch.duplicate_rows}{" "}
        duplicate rows
      </Alert>
      <ReconcileForm batchId={batch.id} compact />
      {errors.length > 0 && (<><h3>Invalid rows (not stored)</h3><RowErrorsTable errors={errors} /></>)}
      {duplicates.length > 0 && (<><h3>Duplicate references</h3><DuplicatesTable duplicates={duplicates} /></>)}
    </div>
  );
}
