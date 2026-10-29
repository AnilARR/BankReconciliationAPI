import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { CATEGORIES, type ReconciliationRun } from "../api/types";
import { CATEGORY_COLORS } from "../utils/colors";
import { CATEGORY_LABELS, formatPercent, matchRate, runCounts } from "../utils/format";

export function CategoryDonut({ run, height = 260 }: { run: ReconciliationRun; height?: number }) {
  const counts = runCounts(run);
  const data = CATEGORIES.map((c) => ({ key: c, name: CATEGORY_LABELS[c], value: counts[c] })).filter((d) => d.value > 0);
  const rate = matchRate(run);

  return (
    <div className="donut" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="88%" paddingAngle={2}
            stroke="var(--surface)" strokeWidth={2} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.key} fill={CATEGORY_COLORS[d.key]} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => [value, "Items"]} />
        </PieChart>
      </ResponsiveContainer>
      <div className="donut-center">
        <span className="donut-value">{formatPercent(rate)}</span>
        <span className="muted small">match rate</span>
      </div>
    </div>
  );
}

export function CategoryLegend({ run }: { run: ReconciliationRun }) {
  const counts = runCounts(run);
  return (
    <ul className="legend">
      {CATEGORIES.map((c) => (
        <li key={c}>
          <span className="dot" style={{ background: CATEGORY_COLORS[c] }} />
          <span>{CATEGORY_LABELS[c]}</span>
          <strong>{counts[c]}</strong>
        </li>
      ))}
    </ul>
  );
}

export function RunTrendChart({ runs, height = 260 }: { runs: ReconciliationRun[]; height?: number }) {
  const data = [...runs]
    .sort((a, b) => a.id - b.id)
    .map((r) => ({
      name: `Run #${r.id}`,
      [CATEGORY_LABELS.MATCHED]: r.matched,
      [CATEGORY_LABELS.MISMATCHED]: r.mismatched,
      [CATEGORY_LABELS.MISSING_IN_DATABASE]: r.missing_in_database,
      [CATEGORY_LABELS.MISSING_IN_FILE]: r.missing_in_file,
      [CATEGORY_LABELS.DUPLICATE_IN_FILE]: r.duplicates_in_file,
    }));

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="var(--muted)" />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} stroke="var(--muted)" />
          <Tooltip cursor={{ fill: "var(--hover)" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {CATEGORIES.map((c, i) => (
            <Bar key={c} dataKey={CATEGORY_LABELS[c]} stackId="run" fill={CATEGORY_COLORS[c]}
              radius={i === CATEGORIES.length - 1 ? [4, 4, 0, 0] : 0} isAnimationActive={false} maxBarSize={48} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
