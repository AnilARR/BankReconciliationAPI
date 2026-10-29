import type { DuplicateReference, RowError } from "../api/types";

export function RowErrorsTable({ errors }: { errors: RowError[] }) {
  if (errors.length === 0) return null;
  return (
    <div className="table-wrap compact">
      <table>
        <thead>
          <tr>
            <th>Row</th>
            <th>Reference</th>
            <th>Problems</th>
          </tr>
        </thead>
        <tbody>
          {errors.map((e) => (
            <tr key={e.row_number}>
              <td className="num">{e.row_number}</td>
              <td className="mono">{e.reference ?? "—"}</td>
              <td>{e.errors.join("; ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DuplicatesTable({ duplicates }: { duplicates: DuplicateReference[] }) {
  if (duplicates.length === 0) return null;
  return (
    <div className="table-wrap compact">
      <table>
        <thead>
          <tr>
            <th>Reference</th>
            <th className="num">Occurrences</th>
            <th>File rows</th>
          </tr>
        </thead>
        <tbody>
          {duplicates.map((d) => (
            <tr key={d.reference}>
              <td className="mono">{d.reference}</td>
              <td className="num">{d.occurrences}</td>
              <td>{d.row_numbers.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
