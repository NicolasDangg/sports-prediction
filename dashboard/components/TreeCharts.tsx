"use client";

import { Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ReferenceDot, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";

const shorten = (l: string) => l.replace(/\s*\(P1 − P2\)/, "").replace(", log(rank P2 / rank P1)", "").replace(", log", "");

/** Horizontal bars: how much purer each variable's best single split makes the groups. */
export function SplitRankingChart({ ranking }: { ranking: { label: string; gain: number }[] }) {
  const data = ranking.map((r) => ({ name: shorten(r.label), gain: Number(r.gain.toFixed(4)) }));
  const max = Math.max(...data.map((d) => d.gain));
  const config: ChartConfig = { gain: { label: "Gini gain", color: "#2a78d6" } };
  return (
    <ChartContainer config={config} className="aspect-auto h-[330px] w-full">
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 48, top: 4, bottom: 4 }}>
        <CartesianGrid horizontal={false} stroke="var(--color-line-soft)" />
        <XAxis type="number" dataKey="gain" hide domain={[0, max * 1.18]} />
        <YAxis type="category" dataKey="name" width={150} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
        <ChartTooltip cursor={{ fill: "var(--color-sunken)" }} content={<ChartTooltipContent hideIndicator />} />
        <Bar dataKey="gain" radius={[0, 4, 4, 0]} barSize={16}>
          {data.map((d, i) => <Cell key={d.name} fill={i === 0 ? "#2a78d6" : "#9ec5f4"} />)}
          <LabelList dataKey="gain" position="right" className="fill-ink-2" fontSize={11} formatter={(v: unknown) => Number(v).toFixed(3)} />
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}

/** Validation log loss as the tree grows deeper: too shallow underfits, too deep memorises. */
export function DepthChart({ rows, chosen }: { rows: { depth: number; val_log_loss: number }[]; chosen: number }) {
  const config: ChartConfig = { val_log_loss: { label: "Validation log loss", color: "#2a78d6" } };
  const best = rows.find((r) => r.depth === chosen);
  const lo = Math.min(...rows.map((r) => r.val_log_loss)), hi = Math.max(...rows.map((r) => r.val_log_loss));
  return (
    <ChartContainer config={config} className="aspect-auto h-[220px] w-full">
      <LineChart data={rows} margin={{ left: 0, right: 16, top: 12, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--color-line-soft)" />
        <XAxis dataKey="depth" tickLine={false} axisLine={false} tickFormatter={(d) => `d${d}`} tickMargin={6} />
        <YAxis domain={[Math.floor(lo * 100) / 100, Math.ceil(hi * 100) / 100]} tickLine={false} axisLine={false} width={44}
               tickFormatter={(v) => Number(v).toFixed(2)} />
        <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => `Depth ${p?.[0]?.payload?.depth}`} />} />
        <Line dataKey="val_log_loss" type="monotone" stroke="var(--color-val_log_loss)" strokeWidth={2}
              dot={{ r: 3, strokeWidth: 2, stroke: "var(--color-surface)", fill: "var(--color-val_log_loss)" }} isAnimationActive={false} />
        {best && <ReferenceDot x={best.depth} y={best.val_log_loss} r={6} fill="var(--color-ink)" stroke="var(--color-surface)" strokeWidth={2}
                               label={{ value: "chosen", position: "top", fontSize: 11, fill: "var(--color-ink-2)" }} />}
      </LineChart>
    </ChartContainer>
  );
}
