"use client";

import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import Segmented from "./Segmented";

const RANGES = { "3m": 92, "6m": 183, "1y": 365, all: Infinity } as const;
type Range = keyof typeof RANGES;
const fmt = (t: number, long = false) =>
  new Date(t).toLocaleDateString("en-GB", long ? { day: "numeric", month: "short", year: "numeric" } : { month: "short", year: "2-digit" });

/** One team's/player's Elo after every match: step line over a 10% wash. */
export default function EntityChart({ points, color, seasonStarts = [] }: {
  points: { t: number; elo: number }[]; color: string; seasonStarts?: number[];
}) {
  const [range, setRange] = useState<Range>("all");
  const { data, domain, ticks } = useMemo(() => {
    const last = points.at(-1)?.t ?? 0;
    const data = points.filter((p) => p.t >= last - RANGES[range] * 86400000);
    const ys = data.map((d) => d.elo);
    const lo = Math.min(...ys), hi = Math.max(...ys);
    const step = [10, 25, 50, 100].find((s) => (hi - lo + 40) / s <= 6) ?? 200;
    const domain: [number, number] = [Math.floor((lo - 15) / step) * step, Math.ceil((hi + 15) / step) * step];
    const ticks: number[] = [];
    for (let v = domain[0]; v <= domain[1]; v += step) ticks.push(v);
    return { data, domain, ticks };
  }, [points, range]);
  const config: ChartConfig = { elo: { label: "Elo", color } };
  const first = data[0]?.t ?? 0;

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Segmented label="Time range" value={range} onChange={setRange}
          options={[{ value: "3m", label: "3M" }, { value: "6m", label: "6M" }, { value: "1y", label: "1Y" }, { value: "all", label: "All" }]} />
      </div>
      <ChartContainer config={config} className="aspect-auto h-[280px] w-full">
        <AreaChart data={data} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="eloWash" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-elo)" stopOpacity={0.14} />
              <stop offset="100%" stopColor="var(--color-elo)" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--color-line-soft)" />
          <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickLine={false} axisLine={false}
                 minTickGap={48} tickMargin={8} tickFormatter={(t) => fmt(t)} />
          <YAxis domain={domain} ticks={ticks} tickLine={false} axisLine={false} width={44} />
          {seasonStarts.filter((t) => t > first).map((t) => (
            <ReferenceLine key={t} x={t} stroke="#c7ccd4" label={{ value: "New season", position: "insideTopLeft", fontSize: 11, fill: "var(--color-ink-3)" }} />
          ))}
          <ChartTooltip cursor={{ stroke: "#b4bac4" }}
            content={<ChartTooltipContent indicator="line" labelFormatter={(_, p) => fmt(Number(p?.[0]?.payload?.t), true)} />} />
          <Area dataKey="elo" type="stepAfter" stroke="var(--color-elo)" strokeWidth={2} fill="url(#eloWash)"
                activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--color-surface)" }} isAnimationActive={false} />
        </AreaChart>
      </ChartContainer>
    </div>
  );
}
