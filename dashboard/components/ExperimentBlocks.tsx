import type { ReactNode } from "react";
import { CheckCircle, Circle, XCircle } from "@phosphor-icons/react/ssr";
import { STATUS_LABEL, type Metric, type Rule, type Status } from "@/lib/experiments";
import { pct } from "@/lib/format";

const STATUS_STYLE: Record<Status, string> = {
  live: "bg-up-soft text-up",
  collecting: "bg-epl-soft text-[#1c5cab]",
  running: "bg-epl-soft text-[#1c5cab]",
  planned: "bg-sunken text-ink-2 ring-1 ring-line",
  shipped: "bg-up-soft text-up",
  not_shipped: "bg-down-soft text-down",
  done: "bg-sunken text-ink-2 ring-1 ring-line",
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide ${STATUS_STYLE[status]}`}>
      {(status === "live" || status === "collecting" || status === "running") && (
        <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-current" />
      )}
      {STATUS_LABEL[status]}
    </span>
  );
}

/** ✓ / ✗ / pending, with the icon carrying the meaning (not colour alone). */
export function RuleList({ rules }: { rules: Rule[] }) {
  if (!rules.length) return <p className="text-[13px] text-ink-3">No pass/fail rules: exploration or infrastructure.</p>;
  return (
    <ul className="flex flex-col gap-2.5">
      {rules.map((r) => {
        const Icon = r.passed === true ? CheckCircle : r.passed === false ? XCircle : Circle;
        const tone = r.passed === true ? "text-up" : r.passed === false ? "text-down" : "text-ink-3";
        return (
          <li key={r.text} className="flex items-start gap-2.5 text-[13px] leading-relaxed text-ink-2">
            <Icon size={18} weight={r.passed === null ? "regular" : "fill"} className={`mt-px shrink-0 ${tone}`}
                  aria-label={r.passed === true ? "passed" : r.passed === false ? "failed" : "not decided yet"} />
            <span>{r.text}</span>
          </li>
        );
      })}
    </ul>
  );
}

export function RulesSummary({ passed, known, total }: { passed: number; known: number; total: number }) {
  if (!total) return null;
  return (
    <span className="inline-flex items-center gap-1 text-[12px] text-ink-3 tabular">
      <CheckCircle size={14} weight="fill" className={passed === total ? "text-up" : "text-ink-3"} aria-hidden />
      {passed}/{total} rules{known < total ? ` · ${total - known} pending` : ""}
    </span>
  );
}

/** Horizontal log-loss bars. Lower is better, so the bar length shows the distance below a coin flip. */
export function LogLossBars({ rows, reference }: { rows: { label: string; value: number; tone?: "model" | "best" | "book" | "base"; sub?: ReactNode }[]; reference?: number }) {
  const lo = Math.min(...rows.map((r) => r.value)) - 0.01;
  const hi = Math.max(...rows.map((r) => r.value)) + 0.005;
  const w = (v: number) => `${Math.max(4, ((hi - v) / (hi - lo)) * 100)}%`;
  const color = { model: "bg-ink-3/60", best: "bg-atp", book: "bg-ink", base: "bg-line" } as const;
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[minmax(0,10.5rem)_1fr_auto] items-center gap-3 text-[13px]">
          <span className={`truncate ${r.tone === "best" ? "font-semibold text-ink" : "text-ink-2"}`}>{r.label}</span>
          <span className="h-2.5 rounded-full bg-sunken">
            <span className={`block h-full rounded-full ${color[r.tone ?? "model"]}`} style={{ width: w(r.value) }} />
          </span>
          <span className="w-14 text-right font-mono text-[12px] text-ink tabular">{r.value.toFixed(4)}</span>
        </div>
      ))}
      {reference !== undefined && (
        <p className="mt-1 text-[12px] text-ink-3">Longer bar = lower log loss = better probabilities. The bookmaker sits at {reference.toFixed(4)}.</p>
      )}
    </div>
  );
}

export function MetricTable({ metrics, note }: { metrics: Metric[]; note?: string }) {
  const has = (k: keyof Metric) => metrics.some((m) => m[k] !== undefined);
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full min-w-[420px] text-[13px]">
        <thead>
          <tr className="border-b border-line text-left text-[12px] text-ink-3">
            <th className="px-1 py-2 font-medium">Model</th>
            {has("log_loss") && <th className="px-1 py-2 text-right font-medium">Log loss</th>}
            {has("accuracy") && <th className="px-1 py-2 text-right font-medium">Accuracy</th>}
            {has("roi") && <th className="px-1 py-2 text-right font-medium">Wallet ROI</th>}
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.model} className={`border-b border-line-soft last:border-0 ${m.highlight ? "bg-atp-soft/50 font-semibold text-ink" : "text-ink-2"}`}>
              <td className="px-1 py-2.5">{m.model}</td>
              {has("log_loss") && <td className="px-1 py-2.5 text-right font-mono tabular">{m.log_loss?.toFixed(4) ?? "—"}</td>}
              {has("accuracy") && <td className="px-1 py-2.5 text-right font-mono tabular">{m.accuracy !== undefined ? pct(m.accuracy) : "—"}</td>}
              {has("roi") && (
                <td className={`px-1 py-2.5 text-right font-mono tabular ${m.roi !== undefined ? (m.roi >= 0 ? "text-up" : "text-down") : ""}`}>
                  {m.roi !== undefined ? pct(m.roi, true) : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {note && <p className="mt-2 px-1 text-[12px] text-ink-3">{note}</p>}
    </div>
  );
}

export function ProgressBar({ value, target, label }: { value: number; target: number; label: string }) {
  const share = Math.min(1, value / target);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-[12px] text-ink-3">
        <span>{label}</span>
        <span className="font-mono text-ink tabular">{value} / {target}</span>
      </div>
      <div className="mt-1.5 h-2 rounded-full bg-sunken" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={target} aria-label={label}>
        <div className="h-full rounded-full bg-epl transition-[width]" style={{ width: `${Math.max(2, share * 100)}%` }} />
      </div>
    </div>
  );
}
