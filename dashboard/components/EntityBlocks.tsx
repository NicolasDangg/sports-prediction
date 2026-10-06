import Link from "next/link";
import { CaretLeft, CheckCircle, Clock, XCircle } from "@phosphor-icons/react/ssr";
import type { Bet, Dashboard } from "@/lib/data";
import { money, pct, when } from "@/lib/format";

export function Breadcrumb({ label }: { label: string }) {
  return (
    <Link href="/ratings" className="mb-4 inline-flex min-h-9 items-center gap-1 text-[13px] font-medium text-ink-3 transition-colors hover:text-ink">
      <CaretLeft size={14} weight="bold" aria-hidden /> Ratings · {label}
    </Link>
  );
}

export function Tile({ label, value, sub, className = "" }: { label: string; value: React.ReactNode; sub?: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-line/80 bg-surface p-5 shadow-diffuse ${className}`}>
      <p className="text-[12px] font-medium text-ink-3">{label}</p>
      <p className="mt-1.5 text-[26px] font-semibold leading-none tracking-tight text-ink tabular">{value}</p>
      {sub && <div className="mt-2 text-[12px] leading-relaxed text-ink-3">{sub}</div>}
    </div>
  );
}

/** "The model expected 2.6 wins; they got 1." The plainest check of whether a rating is too high or low. */
export function ExpectedVsActual({ expected, actual, n, market }: { expected: number; actual: number; n: number; market?: { expected: number; actual: number; n: number } }) {
  const diff = actual - expected;
  return (
    <div>
      <p className="text-[12px] font-medium text-ink-3">Wins: expected vs actual</p>
      <p className="mt-1.5 text-[26px] font-semibold leading-none tracking-tight text-ink tabular">
        {actual} <span className="text-[16px] font-medium text-ink-3">vs {expected.toFixed(1)} expected</span>
      </p>
      <p className={`mt-2 text-[12px] ${diff > 0.5 ? "text-up" : diff < -0.5 ? "text-down" : "text-ink-3"}`}>
        {diff > 0.5 ? `${diff.toFixed(1)} more than Elo expected: rating may be too low` :
         diff < -0.5 ? `${Math.abs(diff).toFixed(1)} fewer than Elo expected: rating may be too high` : "In line with Elo"} · {n} matches
      </p>
      {market && market.n > 0 && (
        <p className="mt-1 text-[12px] text-ink-3">Bookmakers expected {market.expected.toFixed(1)} of {market.actual} wins in {market.n} priced matches</p>
      )}
    </div>
  );
}

type Upcoming = Dashboard["upcoming"][number];

export function UpcomingAndBets({ upcoming, bets, apiNames }: { upcoming: Upcoming[]; bets: Bet[]; apiNames: string[] }) {
  return (
    <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
      <div>
        <p className="mb-3 text-[13px] font-semibold text-ink">Next priced matches</p>
        {upcoming.length === 0 ? (
          <p className="text-[13px] text-ink-3">Nothing priced right now. The morning run prices matches in the next few days.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {upcoming.map((u) => {
              const mine = u.outcomes.find((o) => apiNames.includes(o.outcome));
              return (
                <li key={u.event_id} className="rounded-xl bg-sunken/60 p-3 ring-1 ring-line/70">
                  <p className="text-[13px] font-medium text-ink">{u.match}</p>
                  <p className="text-[12px] text-ink-3">{u.competition} · {when(u.commence_time)}</p>
                  {mine && typeof mine.elo_p === "number" && (
                    <p className="mt-1.5 text-[12px] text-ink-2 tabular">
                      Win: Elo {pct(mine.elo_p, false, 0)} · market {pct(mine.market_p, false, 0)} · odds {mine.odds.toFixed(2)}
                      {u.pick && <span className="ml-1 font-semibold text-ink"> · bet on {u.pick}</span>}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div>
        <p className="mb-3 text-[13px] font-semibold text-ink">Paper bets involving them</p>
        {bets.length === 0 ? (
          <p className="text-[13px] text-ink-3">No bets yet.</p>
        ) : (
          <ul className="divide-y divide-line-soft">
            {bets.map((b) => (
              <li key={b.bet_id} className="flex items-center gap-3 py-2.5 first:pt-0">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-ink">{b.pick} <span className="font-normal text-ink-3">@ {b.odds.toFixed(2)}</span></span>
                  <span className="block truncate text-[12px] text-ink-3">{b.match}</span>
                </span>
                <span className={`inline-flex shrink-0 items-center gap-1 text-[12px] font-semibold tabular ${b.status === "won" ? "text-up" : b.status === "lost" ? "text-down" : "text-ink-3"}`}>
                  {b.status === "won" ? <CheckCircle size={14} weight="fill" aria-hidden /> : b.status === "lost" ? <XCircle size={14} weight="fill" aria-hidden /> : <Clock size={14} aria-hidden />}
                  {b.status === "open" ? money(b.stake) : b.status === "won" || b.status === "lost" ? money(b.pnl, { sign: true }) : b.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
