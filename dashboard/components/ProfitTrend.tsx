/** Net profit per day, stretched to fill whatever space its container gives it. Server-rendered SVG.
 *  Fewer than two days can't make a line, so it says when the line will appear instead. */
export default function ProfitTrend({ points }: { points: { x: string; y: number }[] }) {
  if (points.length < 2) {
    return (
      <div className="grid h-full min-h-28 place-items-center rounded-2xl border border-dashed border-line bg-sunken/40 px-5 text-center">
        <p className="max-w-[40ch] text-[13px] leading-relaxed text-ink-3">
          The profit trend draws itself from the second daily run.
          <span className="block text-ink-2">{points.length} day recorded so far.</span>
        </p>
      </div>
    );
  }
  const W = 100;
  const H = 100;
  const ys = points.map((p) => p.y);
  const lo = Math.min(0, ...ys);
  const hi = Math.max(0, ...ys);
  const pad = Math.max(hi - lo, 50) * 0.12;
  const px = (i: number) => (i / (points.length - 1)) * W;
  const py = (v: number) => H - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * H;
  const line = points.map((p, i) => `${px(i)},${py(p.y)}`).join(" ");
  const last = points.at(-1)!;
  const up = last.y >= 0;
  const first = new Date(points[0].x).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return (
    <div className="flex h-full min-h-28 flex-col">
      <div className="relative flex-1">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible" aria-hidden>
          <line x1={0} x2={W} y1={py(0)} y2={py(0)} stroke="var(--color-line)" strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
          <polygon points={`0,${py(0)} ${line} ${W},${py(0)}`} fill={up ? "var(--color-up-soft)" : "var(--color-down-soft)"} opacity={0.7} />
          <polyline points={line} fill="none" stroke={up ? "var(--color-up)" : "var(--color-down)"} strokeWidth={2}
            strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        </svg>
        {/* End dot as HTML so it stays round when the SVG stretches. */}
        <span className={`absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface ${up ? "bg-up" : "bg-down"}`}
          style={{ left: "100%", top: `${py(last.y)}%` }} aria-hidden />
      </div>
      <p className="mt-2 flex justify-between text-[11px] text-ink-3">
        <span>{first}</span><span>Net profit, one point per morning</span><span>Today</span>
      </p>
    </div>
  );
}
