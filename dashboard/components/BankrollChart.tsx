"use client";

import { useMemo, useRef, useState } from "react";

export type Series = { name: string; color: string; points: { x: string; y: number }[] };

const W = 760;
const PAD = { top: 18, right: 70, bottom: 30, left: 58 };

const money = (v: number) => `$${Math.round(v).toLocaleString("en-US")}`;
const day = (t: number) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** Bankroll over time: 2px lines, hairline grid, $1,000 start line, crosshair + tooltip on hover/touch. */
export default function BankrollChart({ series, start = 1000, height = 280 }: { series: Series[]; start?: number; height?: number }) {
  const H = height;
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverT, setHoverT] = useState<number | null>(null);

  const parsed = useMemo(
    () => series.map((s) => ({ ...s, pts: s.points.map((p) => ({ t: Date.parse(p.x), y: p.y })) })),
    [series],
  );
  const all = parsed.flatMap((s) => s.pts);
  if (all.length === 0) {
    return <div className="grid h-48 place-items-center rounded-2xl bg-sunken/60 text-[13px] text-ink-3">No data yet.</div>;
  }

  let t0 = Math.min(...all.map((p) => p.t));
  let t1 = Math.max(...all.map((p) => p.t));
  if (t0 === t1) { t0 -= 86400000 * 3; t1 += 86400000 * 3; }
  const yMax = niceCeil(Math.max(start * 1.15, ...all.map((p) => p.y)));
  const yTicks = ticks(yMax);
  const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - v / yMax) * (H - PAD.top - PAD.bottom);

  const nearest = (pts: { t: number; y: number }[], t: number) =>
    pts.reduce((best, p) => (Math.abs(p.t - t) < Math.abs(best.t - t) ? p : best), pts[0]);

  function onMove(e: React.PointerEvent) {
    const r = svgRef.current!.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const t = t0 + ((px - PAD.left) / (W - PAD.left - PAD.right)) * (t1 - t0);
    setHoverT(Math.min(t1, Math.max(t0, t)));
  }

  const hover = hoverT === null ? null : parsed.filter((s) => s.pts.length).map((s) => ({ s, p: nearest(s.pts, hoverT) }));
  const hoverX = hover?.length ? x(hover[0].p.t) : 0;

  // End labels: stack them apart when two lines finish close together.
  const ends = parsed.filter((s) => s.pts.length).map((s) => ({ s, last: s.pts[s.pts.length - 1] }))
    .sort((a, b) => y(a.last.y) - y(b.last.y));
  const labelY: number[] = [];
  ends.forEach((e, i) => { labelY.push(Math.max(y(e.last.y), i ? labelY[i - 1] + 15 : -Infinity)); });

  return (
    <div>
      {series.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-4 text-[12px] text-ink-2">
          {series.map((s) => (
            <span key={s.name} className="inline-flex items-center gap-2">
              <i className="h-0.5 w-3.5 rounded-full" style={{ background: s.color }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="block h-auto w-full touch-none select-none overflow-visible"
          role="img"
          aria-label={`Bankroll over time. ${series.map((s) => `${s.name}: ${money(s.points.at(-1)?.y ?? start)}`).join(", ")}`}
          onPointerMove={onMove}
          onPointerDown={onMove}
          onPointerLeave={() => setHoverT(null)}
        >
          {yTicks.map((v) => (
            <g key={v}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke="var(--color-line-soft)" />
              <text x={PAD.left - 10} y={y(v)} textAnchor="end" dominantBaseline="middle" className="fill-ink-3 text-[11px] tabular">{money(v)}</text>
            </g>
          ))}
          <line x1={PAD.left} x2={W - PAD.right} y1={y(start)} y2={y(start)} stroke="#c7ccd4" />
          <text x={W - PAD.right} y={y(start) - 7} textAnchor="end" className="fill-ink-3 text-[11px]">$1,000 start</text>
          <text x={PAD.left} y={H - 8} className="fill-ink-3 text-[11px]">{day(t0)}</text>
          <text x={W - PAD.right} y={H - 8} textAnchor="end" className="fill-ink-3 text-[11px]">{day(t1)}</text>

          {parsed.map((s) => s.pts.length > 1 && (
            <polyline key={s.name} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
                      points={s.pts.map((p) => `${x(p.t)},${y(p.y)}`).join(" ")} />
          ))}
          {ends.map(({ s, last }, i) => (
            <g key={s.name}>
              <circle cx={x(last.t)} cy={y(last.y)} r={4} fill={s.color} stroke="var(--color-surface)" strokeWidth={2} />
              <text x={x(last.t) + 9} y={labelY[i]} dominantBaseline="middle" className="fill-ink text-[12px] font-semibold tabular">{money(last.y)}</text>
            </g>
          ))}

          {hover && (
            <g pointerEvents="none">
              <line x1={hoverX} x2={hoverX} y1={PAD.top} y2={H - PAD.bottom} stroke="#b4bac4" />
              {hover.map(({ s, p }) => (
                <circle key={s.name} cx={x(p.t)} cy={y(p.y)} r={4.5} fill={s.color} stroke="var(--color-surface)" strokeWidth={2} />
              ))}
            </g>
          )}
          <rect x={PAD.left} y={PAD.top} width={W - PAD.left - PAD.right} height={H - PAD.top - PAD.bottom} fill="transparent" />
        </svg>
        {hover && hover.length > 0 && (
          <div
            className="pointer-events-none absolute top-0 -translate-x-1/2 whitespace-nowrap rounded-xl border border-line bg-surface px-3 py-2 text-[12px] shadow-diffuse"
            style={{ left: `${(hoverX / W) * 100}%` }}
          >
            <div className="mb-1 text-ink-3">{day(hover[0].p.t)}</div>
            {hover.map(({ s, p }) => (
              <div key={s.name} className="flex items-center gap-2">
                <i className="size-2 rounded-full" style={{ background: s.color }} />
                <span className="text-ink-2">{s.name}</span>
                <b className="ml-auto pl-4 font-semibold text-ink tabular">{money(p.y)}</b>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function niceCeil(v: number) {
  const step = 10 ** Math.floor(Math.log10(v)) / 2;
  return Math.ceil(v / step) * step;
}

function ticks(hi: number) {
  const step = niceCeil(hi / 4);
  const out = [];
  for (let v = 0; v <= hi + 1e-9; v += step) out.push(v);
  return out;
}
