import Link from "next/link";
import { ArrowRight, GitFork } from "@phosphor-icons/react/ssr";
import BankrollChart from "@/components/BankrollChart";
import Reveal from "@/components/Reveal";
import { Card, CardHeader, Delta, EmptyState, PageHeader, SportTag } from "@/components/ui";
import { loadExperiments } from "@/lib/experiments";
import { SPORT_COLOR, SPORT_LABEL, STRATEGY_BLURB, money, pct, strategyDash, when } from "@/lib/format";
import { loadStrategies, type WalletStats } from "@/lib/strategies";

export const metadata = { title: "Strategies · Closing Line" };

const dash = "—";
type Row = { label: string; hint?: string; get: (s: WalletStats) => React.ReactNode; tone?: (s: WalletStats) => number | null };
const ROWS: Row[] = [
  { label: "Bankroll", get: (s) => money(s.bankroll) },
  { label: "Net profit", hint: "bankroll − deposits", get: (s) => money(s.net, { sign: true }), tone: (s) => s.net },
  { label: "Bets placed", get: (s) => s.placed },
  { label: "Settled (W–L)", get: (s) => (s.settled ? `${s.settled} (${s.won}–${s.lost})` : dash) },
  { label: "Win rate", get: (s) => (s.winRate === null ? dash : pct(s.winRate, false, 1)) },
  { label: "Model expected", hint: "average model probability of the settled picks", get: (s) => (s.settled ? pct(s.expectedWins / s.settled, false, 1) : dash) },
  { label: "ROI", hint: "P&L / staked, settled bets", get: (s) => (s.roi === null ? dash : pct(s.roi, true)), tone: (s) => s.roi },
  { label: "Avg odds", get: (s) => (s.avgOdds === null ? dash : s.avgOdds.toFixed(2)) },
  { label: "Avg claimed edge", hint: "what the model thought it had", get: (s) => (s.avgClaimedEdge === null ? dash : pct(s.avgClaimedEdge, true)) },
  { label: "CLV vs typical close", hint: "our price vs the closing median; positive = the price moved our way", get: (s) => (s.clv.mean === null ? dash : `${pct(s.clv.mean, true)} (${s.clv.n})`), tone: (s) => s.clv.mean },
  { label: "Beat Pinnacle's close", hint: "our odds × Pinnacle's fair closing chance − 1. The real test of an edge", get: (s) => (s.clvFair.mean === null ? dash : `${pct(s.clvFair.mean, true)} (${s.clvFair.n})`), tone: (s) => s.clvFair.mean },
  { label: "Max drawdown", get: (s) => (s.days > 1 ? pct(s.maxDrawdown, false, 1) : dash) },
  { label: "In open bets", get: (s) => (s.open ? `${money(s.openStakes, { cents: false })} (${s.open})` : dash) },
  { label: "Running since", get: (s) => s.firstDay ?? dash },
];

export default function StrategiesPage() {
  const { stats, disagreements, latestDate } = loadStrategies();
  const { list } = loadExperiments();
  const experimentOf = (strategy: string) => list.find((e) => e.strategy === strategy);
  const series = stats.map((s) => ({
    name: `${SPORT_LABEL[s.sport]} · ${s.strategy}`, color: SPORT_COLOR[s.sport], dash: strategyDash(s.strategy), points: s.curve,
  }));

  return (
    <>
      <PageHeader eyebrow={`Updated ${latestDate || dash}`} title="Strategies" />
      <div className="grid grid-cols-1 gap-4 lg:gap-5">
        <Reveal i={0}>
          <Card>
            <CardHeader title="Net profit, every version" hint="One line per wallet: colour = sport, solid = the elo_v0 control, dashed or dotted = a challenger. Each starts from its own deposit, so lines are comparable from day one." />
            {stats.length ? <BankrollChart series={series} height={280} start={0} startLabel="Break-even" signed />
              : <p className="text-[13px] text-ink-3">No wallets yet.</p>}
          </Card>
        </Reveal>

        <Reveal i={1}>
          <Card>
            <CardHeader title="Side by side" hint="Fewer than ~100 settled bets is anecdote: the numbers move a lot until then." />
            <div className="-mx-1 overflow-x-auto">
              <table className="w-full min-w-[760px] text-[13px]">
                <thead>
                  <tr className="border-b border-line text-left">
                    <th className="px-1 py-2.5 text-[12px] font-medium text-ink-3">&nbsp;</th>
                    {stats.map((s) => {
                      const ex = experimentOf(s.strategy);
                      return (
                        <th key={s.wallet} className="px-2 py-2.5 text-right align-bottom font-medium">
                          <div className="flex flex-col items-end gap-1">
                            <SportTag sport={s.sport} />
                            <span className="font-mono text-[13px] text-ink">{s.strategy}</span>
                            {STRATEGY_BLURB[s.strategy] && <span className="max-w-[150px] text-[11px] font-normal leading-snug text-ink-3">{STRATEGY_BLURB[s.strategy]}</span>}
                            {ex && <Link href={`/experiments/${ex.id.toLowerCase()}`} className="text-[11px] text-ink-3 underline-offset-2 hover:text-ink hover:underline">{ex.id}</Link>}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((r) => (
                    <tr key={r.label} className="border-b border-line-soft last:border-0">
                      <th scope="row" className="px-1 py-2.5 text-left font-normal">
                        <span className="text-ink-2">{r.label}</span>
                        {r.hint && <span className="block text-[11px] text-ink-3">{r.hint}</span>}
                      </th>
                      {stats.map((s) => {
                        const t = r.tone?.(s);
                        return (
                          <td key={s.wallet} className={`px-2 py-2.5 text-right font-mono tabular ${t === null || t === undefined || t === 0 ? "text-ink" : t > 0 ? "text-up" : "text-down"}`}>
                            {r.get(s)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </Reveal>

        <Reveal i={2}>
          <Card>
            <CardHeader title="Where they disagreed" hint="Matches where strategies in the same sport made different calls, e.g. news_v1 refusing a player elo_v0 backed, or sharp_v1 betting a match the models passed on. This is where versions actually differ." />
            {disagreements.length ? (
              <ul className="flex flex-col divide-y divide-line-soft">
                {disagreements.slice(0, 30).map((d) => (
                  <li key={d.match + d.commence} className="flex flex-col gap-2 py-3 first:pt-0 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <p className="truncate text-[14px] font-medium text-ink">{d.match}</p>
                      <p className="text-[12px] text-ink-3">{when(d.commence)}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {d.picks.map(({ strategy, bet }) => (
                        <span key={strategy} className="inline-flex items-center gap-2 rounded-full bg-sunken/70 px-3 py-1 text-[12px] ring-1 ring-line/70">
                          <span className="font-mono text-ink-3">{strategy}</span>
                          {bet ? (
                            <>
                              <span className="text-ink">{bet.pick}</span>
                              {bet.status === "won" || bet.status === "lost"
                                ? <Delta value={bet.pnl}>{money(bet.pnl, { sign: true })}</Delta>
                                : <span className="text-ink-3">{bet.status}</span>}
                            </>
                          ) : <span className="text-ink-3">no bet</span>}
                        </span>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={<GitFork size={18} />} title="No disagreements yet">
                Strategies in the same sport have made identical calls so far. news_v1 diverges from elo_v0 only when a backed player has injury news.
              </EmptyState>
            )}
            <Link href="/experiments" className="mt-4 inline-flex items-center gap-1 text-[13px] font-medium text-ink-2 hover:text-ink">
              How each version came about <ArrowRight size={14} aria-hidden />
            </Link>
          </Card>
        </Reveal>
      </div>
    </>
  );
}
