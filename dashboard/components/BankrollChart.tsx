"use client";

import { useMemo, useRef, useState } from "react";

export type Series = { name: string; color: string; points: { x: string; y: number }[] };

const W = 720;
const H = 260;
const PAD = { top: 16, right: 64, bottom: 28, left: 56 };

const money = (v: number) => `$${Math.round(v).toLocaleString("en-US")}`;
const day = (t: number) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export default function BankrollChart({ series, start = 1000 }: { series: Series[]; start?: number }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverT, setHoverT] = useState<number | null>(null);

  const parsed = useMemo(
    () => series.map((s) => ({ ...s, pts: s.points.map((p) => ({ t: Date.parse(p.x), y: p.y })) })),
    [series],
  );
  const all = parsed.flatMap((s) => s.pts);
  if (all.length === 0) return <p className="empty">No data yet.</p>;

  let t0 = Math.min(...all.map((p) => p.t));
  let t1 = Math.max(...all.map((p) => p.t));
  if (t0 === t1) { t0 -= 86400000 * 3; t1 += 86400000 * 3; }  // a single day: give it some width
  const yMax = niceCeil(Math.max(start * 1.1, ...all.map((p) => p.y)));
  const yTicks = ticks(0, yMax);

  const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - v / yMax) * (H - PAD.top - PAD.bottom);

  const nearest = (pts: { t: number; y: number }[], t: number) => {
    let best = pts[0];
    for (const p of pts) if (Math.abs(p.t - t) < Math.abs(best.t - t)) best = p;
    return best;
  };

  function onMove(e: React.PointerEvent) {
    const r = svgRef.current!.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const t = t0 + ((px - PAD.left) / (W - PAD.left - PAD.right)) * (t1 - t0);
    setHoverT(Math.min(t1, Math.max(t0, t)));
  }

  const hover = hoverT === null ? null : parsed.map((s) => ({ s, p: nearest(s.pts, hoverT) }));
  const hoverX = hover ? x(hover[0].p.t) : 0;

  return (
    <div className="chart">
      {series.length > 1 && (
        <div className="legend">
          {series.map((s) => (
            <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>
          ))}
        </div>
      )}
      <div className="chart-plot">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} role="img"
             aria-label={`Bankroll over time: ${series.map((s) => `${s.name} ${money(s.points.at(-1)?.y ?? start)}`).join(", ")}`}
             onPointerMove={onMove} onPointerLeave={() => setHoverT(null)}>
          {yTicks.map((v) => (
            <g key={v}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className="grid" />
              <text x={PAD.left - 8} y={y(v)} className="axis" textAnchor="end" dominantBaseline="middle">{money(v)}</text>
            </g>
          ))}
          <line x1={PAD.left} x2={W - PAD.right} y1={y(start)} y2={y(start)} className="baseline" />
          <text x={PAD.left + 4} y={y(start) - 6} className="axis">start</text>
          <text x={PAD.left} y={H - 6} className="axis">{day(t0)}</text>
          <text x={W - PAD.right} y={H - 6} className="axis" textAnchor="end">{day(t1)}</text>

          {parsed.map((s) => (
            <g key={s.name}>
              {s.pts.length > 1 && (
                <polyline fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
                          points={s.pts.map((p) => `${x(p.t)},${y(p.y)}`).join(" ")} />
              )}
              {s.pts.length > 0 && (() => {
                const last = s.pts[s.pts.length - 1];
                return (
                  <>
                    <circle cx={x(last.t)} cy={y(last.y)} r={4} fill={s.color} stroke="var(--surface)" strokeWidth={2} />
                    <text x={x(last.t) + 8} y={y(last.y)} className="end-label" dominantBaseline="middle">{money(last.y)}</text>
                  </>
                );
              })()}
            </g>
          ))}

          {hover && (
            <g pointerEvents="none">
              <line x1={hoverX} x2={hoverX} y1={PAD.top} y2={H - PAD.bottom} className="crosshair" />
              {hover.map(({ s, p }) => (
                <circle key={s.name} cx={x(p.t)} cy={y(p.y)} r={4.5} fill={s.color} stroke="var(--surface)" strokeWidth={2} />
              ))}
            </g>
          )}
          <rect x={PAD.left} y={PAD.top} width={W - PAD.left - PAD.right} height={H - PAD.top - PAD.bottom} fill="transparent" />
        </svg>
        {hover && (
          <div className="tooltip" style={{ left: `${(hoverX / W) * 100}%` }}>
            <div className="tooltip-date">{day(hover[0].p.t)}</div>
            {hover.map(({ s, p }) => (
              <div key={s.name} className="tooltip-row">
                <i style={{ background: s.color }} />{s.name}<b>{money(p.y)}</b>
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

function ticks(lo: number, hi: number) {
  const step = niceCeil(hi / 4);
  const out = [];
  for (let v = lo; v <= hi + 1e-9; v += step) out.push(v);
  return out;
}
