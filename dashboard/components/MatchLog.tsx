import Link from "next/link";
import { Lightning } from "@phosphor-icons/react/ssr";
import type { Row } from "@/lib/entities";

const tone = { W: "bg-up-soft text-up", D: "bg-sunken text-ink-3", L: "bg-down-soft text-down" };
const pct = (v: number) => `${Math.round(v * 100)}%`;
const date = (d: string) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "2-digit" });

/** Every match from one team's/player's side: what the model expected, what happened, how Elo moved. */
export default function MatchLog({ rows, sport }: { rows: Row[]; sport: "epl" | "atp" }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-[13px]">
        <thead>
          <tr className="border-b border-line text-left text-[12px] text-ink-3">
            <th className="py-3 pl-6 pr-3 font-medium">Date</th>
            <th className="px-3 py-3 font-medium">Opponent</th>
            <th className="px-3 py-3 font-medium">{sport === "epl" ? "Venue" : "Event"}</th>
            <th className="px-3 py-3 font-medium">Result</th>
            <th className="px-3 py-3 text-right font-medium" title="Model's pre-match win probability">Model win</th>
            {sport === "atp" && <th className="px-3 py-3 text-right font-medium" title="Bookmaker's win probability, margin removed">Market</th>}
            <th className="py-3 pl-3 pr-6 text-right font-medium">Elo before → after</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const delta = Math.round(r.eloAfter - r.eloBefore);
            return (
              <tr key={i} className="border-b border-line-soft last:border-0 hover:bg-sunken/50">
                <td className="py-3 pl-6 pr-3 text-ink-3 tabular">{date(r.date)}</td>
                <td className="px-3 py-3 font-medium text-ink">
                  {r.opponentSlug ? (
                    <Link href={`/ratings/${sport}/${r.opponentSlug}`} className="underline-offset-4 hover:underline">{r.opponent}</Link>
                  ) : r.opponent}
                </td>
                <td className="max-w-[260px] truncate px-3 py-3 text-ink-3" title={r.detail}>
                  {sport === "epl" ? (r.venue === "H" ? "Home" : "Away") : `${r.detail} · ${r.venue}`}
                </td>
                <td className="px-3 py-3">
                  <span className="inline-flex items-center gap-2">
                    <span className={`grid size-6 place-items-center rounded-md font-mono text-[11px] font-semibold ${tone[r.result]}`}>{r.result}</span>
                    <span className="font-mono text-ink-2 tabular">{r.score}</span>
                    {r.upset && (
                      <span className="inline-flex items-center gap-0.5 rounded-full bg-[#fff4dc] px-1.5 py-0.5 text-[10px] font-semibold text-[#8a5a00]"
                            title="The model gave this result less than a 25–30% chance">
                        <Lightning size={10} weight="fill" aria-hidden />Upset
                      </span>
                    )}
                  </span>
                </td>
                <td className="px-3 py-3 text-right text-ink-2 tabular">
                  {pct(r.modelWin)}{r.modelDraw !== undefined && <span className="text-ink-3"> · D {pct(r.modelDraw)}</span>}
                </td>
                {sport === "atp" && <td className="px-3 py-3 text-right text-ink-3 tabular">{r.marketWin !== undefined ? pct(r.marketWin) : "—"}</td>}
                <td className="py-3 pl-3 pr-6 text-right font-mono tabular">
                  <span className="text-ink-3">{Math.round(r.eloBefore)} → </span>
                  <span className="text-ink">{Math.round(r.eloAfter)}</span>
                  <span className={`ml-2 inline-block w-10 text-right ${delta > 0 ? "text-up" : delta < 0 ? "text-down" : "text-ink-3"}`}>
                    {delta > 0 ? "+" : delta < 0 ? "−" : ""}{Math.abs(delta)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
