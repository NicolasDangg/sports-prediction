/** Tiny trend line for a stat tile: de-emphasised line, accent end dot. Server-rendered SVG. */
export default function Sparkline({ points, start = 1000, width = 220, height = 56 }: {
  points: { x: string; y: number }[]; start?: number; width?: number; height?: number;
}) {
  const ys = points.map((p) => p.y);
  const span = Math.max(Math.max(start, ...ys) - Math.min(start, ...ys), 50);
  const lo = Math.min(start, ...ys) - span * 0.1;
  const hi = Math.max(start, ...ys) + span * 0.1;
  const px = (i: number) => (points.length === 1 ? width - 6 : 4 + (i / (points.length - 1)) * (width - 10));
  const py = (v: number) => height - 4 - ((v - lo) / (hi - lo || 1)) * (height - 8);
  const last = points.at(-1);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} aria-hidden className="overflow-visible">
      <line x1={0} x2={width} y1={py(start)} y2={py(start)} stroke="var(--color-line)" strokeDasharray="0" />
      {points.length > 1 && (
        <polyline fill="none" stroke="var(--color-ink-3)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
                  points={points.map((p, i) => `${px(i)},${py(p.y)}`).join(" ")} />
      )}
      {last && <circle cx={px(points.length - 1)} cy={py(last.y)} r={4} fill="var(--color-ink)" stroke="var(--color-surface)" strokeWidth={2} />}
    </svg>
  );
}
