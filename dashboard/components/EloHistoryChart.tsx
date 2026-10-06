"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import Segmented from "./Segmented";
import type { Entity, SeriesRow } from "@/lib/ratings";

// Validated categorical palette, fixed order. A colour slot belongs to an entity while it is
// selected (colour follows the entity, never its rank), and at most 6 lines show at once.
const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const MAX = 6;
const slug = (s: string) => "k_" + s.replace(/[^a-zA-Z0-9]/g, "_");
const RANGES = { "3m": 92, "6m": 183, "1y": 365, all: Infinity } as const;
type Range = keyof typeof RANGES;
const fmtDate = (t: number, long = false) =>
  new Date(t).toLocaleDateString("en-GB", long ? { day: "numeric", month: "short", year: "numeric" } : { month: "short", year: "2-digit" });

export default function EloHistoryChart({ entities, rows, seasonStarts, defaults, chipLimit = 24 }: {
  entities: Entity[]; rows: SeriesRow[]; seasonStarts: number[]; defaults: string[]; chipLimit?: number;
}) {
  const [slots, setSlots] = useState<Record<string, number>>(() => Object.fromEntries(defaults.slice(0, MAX).map((n, i) => [n, i])));
  const [range, setRange] = useState<Range>("1y");
  const selected = Object.keys(slots);

  function toggle(name: string) {
    setSlots((prev) => {
      if (name in prev) {
        const { [name]: _, ...rest } = prev;
        return rest;
      }
      if (Object.keys(prev).length >= MAX) return prev;
      const used = new Set(Object.values(prev));
      const free = PALETTE.findIndex((_, i) => !used.has(i));
      return { ...prev, [name]: free };
    });
  }

  const { data, yDomain, yTicks } = useMemo(() => {
    const lastT = rows.at(-1)?.t ?? 0;
    const from = lastT - RANGES[range] * 86400000;
    const data = rows
      .filter((r) => r.t >= from)
      .map((r) => {
        const out: Record<string, number> = { t: r.t };
        for (const n of selected) if (r[n] !== undefined) out[slug(n)] = r[n];
        return out;
      });
    const vals = data.flatMap((r) => selected.map((n) => r[slug(n)]).filter((v) => v !== undefined));
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = Math.max(15, (hi - lo) * 0.08);
    const step = [25, 50, 100, 200].find((s) => (hi - lo + 2 * pad) / s <= 6) ?? 250;
    const yDomain: [number, number] = vals.length
      ? [Math.floor((lo - pad) / step) * step, Math.ceil((hi + pad) / step) * step]
      : [1300, 1800];
    const yTicks: number[] = [];
    for (let v = yDomain[0]; v <= yDomain[1]; v += step) yTicks.push(v);
    return { data, yDomain, yTicks };
  }, [rows, range, selected.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps

  const config: ChartConfig = Object.fromEntries(selected.map((n) => [slug(n), { label: n, color: PALETTE[slots[n]] }]));
  const firstT = data[0]?.t ?? 0;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[12px] text-ink-3">
          Pick up to {MAX}. Each step is one match: up after a win, down after a loss, more for upsets.
        </p>
        <Segmented label="Time range" value={range} onChange={setRange}
          options={[{ value: "3m", label: "3M" }, { value: "6m", label: "6M" }, { value: "1y", label: "1Y" }, { value: "all", label: "All" }]} />
      </div>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {entities.slice(0, chipLimit).map((e) => {
          const on = e.name in slots;
          const disabled = !on && selected.length >= MAX;
          return (
            <button
              key={e.name}
              onClick={() => toggle(e.name)}
              disabled={disabled}
              aria-pressed={on}
              className={`inline-flex min-h-8 cursor-pointer items-center gap-1.5 rounded-full px-3 text-[12px] font-medium ring-1 transition-colors duration-200 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 ${on ? "bg-surface text-ink ring-ink/20 shadow-sm" : "bg-sunken/60 text-ink-3 ring-line hover:text-ink-2"}`}
            >
              <span className="size-2 rounded-full" style={{ background: on ? PALETTE[slots[e.name]] : "var(--color-line)" }} aria-hidden />
              {e.name}
            </button>
          );
        })}
      </div>

      {selected.length === 0 ? (
        <div className="grid h-[320px] place-items-center rounded-2xl bg-sunken/60 text-[13px] text-ink-3">Pick a team or player above.</div>
      ) : (
        <ChartContainer config={config} className="aspect-auto h-[340px] w-full">
          <LineChart data={data} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--color-line-soft)" />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickLine={false} axisLine={false}
                   minTickGap={48} tickMargin={8} tickFormatter={(t) => fmtDate(t)} />
            <YAxis domain={yDomain} ticks={yTicks} tickLine={false} axisLine={false} width={44} allowDecimals={false} />
            {seasonStarts.filter((t) => t >= firstT).map((t) => (
              <ReferenceLine key={t} x={t} stroke="#c7ccd4" strokeDasharray="0"
                label={{ value: "New season", position: "insideTopLeft", fontSize: 11, fill: "var(--color-ink-3)" }} />
            ))}
            <ChartTooltip
              cursor={{ stroke: "#b4bac4", strokeWidth: 1 }}
              content={<ChartTooltipContent indicator="line" labelFormatter={(_, p) => fmtDate(Number(p?.[0]?.payload?.t), true)} />}
            />
            {selected.map((n) => (
              <Line key={n} dataKey={slug(n)} name={slug(n)} type="stepAfter" stroke={`var(--color-${slug(n)})`} strokeWidth={2}
                    dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--color-surface)" }} connectNulls isAnimationActive={false} />
            ))}
          </LineChart>
        </ChartContainer>
      )}
    </div>
  );
}
