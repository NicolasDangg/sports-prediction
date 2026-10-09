"use client";

import { useMemo, useRef, useState } from "react";

// `dash` (an SVG dash pattern) tells apart strategies in the same sport (same colour): the control is solid.
export type Series = { name: string; color: string; dash?: string; points: { x: string; y: number }[] };

const W = 760;
const PAD = { top: 18, right: 70, bottom: 30, left: 58 };

const money = (v: number, sign = false) =>
  `${v < 0 ? "−" : sign && v > 0 ? "+" : ""}$${Math.abs(Math.round(v)).toLocaleString("en-US")}`;
const day = (t: number) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** Money over time: 2px lines, hairline grid, a labelled reference line (starting bankroll, or
 *  break-even for profit charts), crosshair + tooltip on hover/touch. Handles negative values. */
export default function BankrollChart({ series, start = 1000, startLabel = "$1,000 start", signed = false, height = 280 }: {
  series: Series[]; start?: number; startLabel?: string; signed?: boolean; height?: number;
}) {
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
  const ys = all.map((p) => p.y);
  const rawLo = Math.min(0, start, ...ys);
  const rawHi = Math.max(start, ...ys);
  const pad = Math.max((rawHi - rawLo) * 0.15, Math.abs(start) * 0.15, 100);
  const step = niceStep((rawHi - rawLo + 2 * pad) / 4);
  const yMin = rawLo < 0 ? Math.floor((rawLo - pad) / step) * step : 0;
  const yMax = Math.ceil((rawHi + pad) / step) * step;
  const yTicks: number[] = [];
  for (let v = yMin; v <= yMax + 1e-9; v += step) yTicks.push(v);
  const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - (v - yMin) / (yMax - yMin)) * (H - PAD.top - PAD.bottom);

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

  // End labels: lines finishing on the same value share one label ("$0 ×8"); the rest are spread
  // apart around their true positions (overlapping runs merge and re-centre) instead of only pushed down.
  const ends = parsed.filter((s) => s.pts.length).map((s) => ({ s, last: s.pts[s.pts.length - 1] }))
    .sort((a, b) => y(a.last.y) - y(b.last.y));
  const groups: { text: string; target: number; n: number }[] = [];
  for (const { last } of ends) {
    const text = money(last.y, signed);
    const g = groups.find((g) => g.text === text);
    if (g) g.n++; else groups.push({ text, target: y(last.y), n: 1 });
  }
  groups.sort((a, b) => a.target - b.target);
  const GAP = 15;
  let runs = groups.map((g) => ({ items: [g], top: g.target }));
  for (let merged = true; merged;) {
    merged = false;
    for (let i = 1; i < runs.length; i++) {
      const prev = runs[i - 1], cur = runs[i];
      if (prev.top + prev.items.length * GAP > cur.top) {
        const items = [...prev.items, ...cur.items];
        const mean = items.reduce((s, g) => s + g.target, 0) / items.length;
        runs.splice(i - 1, 2, { items, top: mean - ((items.length - 1) * GAP) / 2 });
        merged = true;
        break;
      }
    }
  }
  const labels = runs.flatMap((r) => r.items.map((g, j) => ({ ...g, y: r.top + j * GAP })));

  return (
    <div>
      {series.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-4 text-[12px] text-ink-2">
          {series.map((s) => (
            <span key={s.name} className="inline-flex items-center gap-2">
              <svg width="22" height="6" aria-hidden className="overflow-visible">
                <line x1="2" x2="20" y1="3" y2="3" stroke={s.color} strokeWidth={2} strokeLinecap="round" strokeDasharray={s.dash} />
              </svg>
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
          aria-label={`Over time. ${series.map((s) => `${s.name}: ${money(s.points.at(-1)?.y ?? start, signed)}`).join(", ")}`}
          onPointerMove={onMove}
          onPointerDown={onMove}
          onPointerLeave={() => setHoverT(null)}
        >
          {yTicks.map((v) => (
            <g key={v}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke="var(--color-line-soft)" />
              <text x={PAD.left - 10} y={y(v)} textAnchor="end" dominantBaseline="middle" className="fill-ink-3 text-[11px] tabular">{money(v, signed)}</text>
            </g>
          ))}
          <line x1={PAD.left} x2={W - PAD.right} y1={y(start)} y2={y(start)} stroke="#c7ccd4" />
          <text x={W - PAD.right} y={y(start) - 7} textAnchor="end" className="fill-ink-3 text-[11px]">{startLabel}</text>
          <text x={PAD.left} y={H - 8} className="fill-ink-3 text-[11px]">{day(t0)}</text>
          <text x={W - PAD.right} y={H - 8} textAnchor="end" className="fill-ink-3 text-[11px]">{day(t1)}</text>

          {parsed.map((s) => s.pts.length > 1 && (
            <polyline key={s.name} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
                      strokeDasharray={s.dash}
                      points={s.pts.map((p) => `${x(p.t)},${y(p.y)}`).join(" ")} />
          ))}
          {ends.map(({ s, last }) => (
            <circle key={s.name} cx={x(last.t)} cy={y(last.y)} r={4} fill={s.color} stroke="var(--color-surface)" strokeWidth={2} />
          ))}
          {labels.map((l) => (
            <text key={l.text} x={W - PAD.right + 9} y={l.y} dominantBaseline="middle" className="fill-ink text-[12px] font-semibold tabular">
              {l.text}{l.n > 1 && <tspan className="fill-ink-3 font-normal"> ×{l.n}</tspan>}
            </text>
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
                <b className="ml-auto pl-4 font-semibold text-ink tabular">{money(p.y, signed)}</b>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function niceStep(raw: number) {
  const mag = 10 ** Math.floor(Math.log10(raw));
  return ([1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
}
