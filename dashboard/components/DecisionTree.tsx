/** Top-down decision tree diagram. Each question splits the matches into "yes" (left) and
 *  "no" (right); leaves show how often Player 1 won in that group. Server-rendered. */

export type TreeNode = {
  samples: number; p1_win: number; gini: number; leaf: boolean;
  feature?: string; label?: string; threshold?: number; left?: TreeNode; right?: TreeNode;
};

const NODE_W = 124;
const GAP = 8;
const LEVEL_H = 150;
const NODE_H = 96; // approx. height of a question box

type Placed = { node: TreeNode; x: number; y: number; depth: number; id: string; parent?: Placed; side?: "yes" | "no" };

function place(root: TreeNode): { nodes: Placed[]; width: number; height: number } {
  const nodes: Placed[] = [];
  let leafIndex = 0;
  function walk(n: TreeNode, depth: number, id: string, parent?: Placed, side?: "yes" | "no"): Placed {
    const p: Placed = { node: n, x: 0, y: depth * LEVEL_H, depth, id, parent, side };
    nodes.push(p);
    if (n.leaf || !n.left || !n.right) {
      p.x = leafIndex++ * (NODE_W + GAP) + NODE_W / 2;
    } else {
      const l = walk(n.left, depth + 1, id + "L", p, "yes");
      const r = walk(n.right, depth + 1, id + "R", p, "no");
      p.x = (l.x + r.x) / 2;
    }
    return p;
  }
  walk(root, 0, "n");
  const depth = Math.max(...nodes.map((n) => n.depth));
  return { nodes, width: leafIndex * (NODE_W + GAP) - GAP, height: depth * LEVEL_H + NODE_H };
}

const fmtThreshold = (feature: string | undefined, t: number) =>
  feature?.includes("elo") ? `${t > 0 ? "+" : ""}${Math.round(t)} pts` : t.toFixed(2);

export default function DecisionTree({ tree }: { tree: TreeNode }) {
  const { nodes, width, height } = place(tree);
  return (
    <div className="overflow-x-auto pb-2">
      <div className="relative mx-auto" style={{ width, height }}>
        <svg className="absolute inset-0" width={width} height={height} aria-hidden>
          {nodes.filter((n) => n.parent).map((n) => {
            const p = n.parent!;
            const y1 = p.y + NODE_H, y2 = n.y, mid = (y1 + y2) / 2;
            return (
              <g key={n.id}>
                <path d={`M${p.x},${y1} V${mid} H${n.x} V${y2}`} fill="none" stroke="#c7ccd4" strokeWidth={1.5} />
                <text x={(p.x + n.x) / 2} y={mid - 5} textAnchor="middle" className="fill-ink-3 text-[11px] font-medium">
                  {n.side}
                </text>
              </g>
            );
          })}
        </svg>
        {nodes.map(({ node, x, y, id }) => (
          <div
            key={id}
            className={`absolute rounded-xl border px-3 py-2 text-center shadow-sm ${node.leaf ? "border-line bg-sunken/70" : "border-line bg-surface"}`}
            style={{ left: x - NODE_W / 2, top: y, width: NODE_W }}
          >
            {node.leaf ? (
              <>
                <p className="text-[18px] font-semibold leading-tight text-ink tabular">{Math.round(node.p1_win * 100)}%</p>
                <p className="text-[10px] text-ink-3 tabular">P1 wins · {node.samples.toLocaleString()}</p>
              </>
            ) : (
              <>
                <p className="text-[12px] font-semibold leading-snug text-ink">
                  {shortLabel(node.label)} ≤ {fmtThreshold(node.feature, node.threshold ?? 0)}?
                </p>
                <p className="mt-0.5 text-[11px] text-ink-3 tabular">P1 {Math.round(node.p1_win * 100)}% · gini {node.gini.toFixed(2)}</p>
                <p className="text-[10px] text-ink-3 tabular">{node.samples.toLocaleString()} matches</p>
              </>
            )}
            {/* purity bar: share of Player 1 wins in this group */}
            <span className="mt-1.5 block h-1 overflow-hidden rounded-full bg-[#f3d6d6]">
              <span className="block h-full rounded-full bg-epl" style={{ width: `${node.p1_win * 100}%` }} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const shortLabel = (l?: string) => (l ?? "").replace(/\s*\(P1 − P2\)/, "").replace(", log(rank P2 / rank P1)", "");
