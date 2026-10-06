import Link from "next/link";
import { ArrowRight, CheckCircle, Clock, Lightning, XCircle } from "@phosphor-icons/react/ssr";
import BankrollChart from "@/components/BankrollChart";
import Reveal from "@/components/Reveal";
import Sparkline from "@/components/Sparkline";
import { Card, CardHeader, Delta, EmptyState, PageHeader, SportTag, Stat } from "@/components/ui";
import { loadDashboard, type Bet } from "@/lib/data";
import { SPORT_COLOR, SPORT_LABEL, money, pct, sportOf, strategyOf, when } from "@/lib/format";

export default function Overview() {
  const d = loadDashboard();
  const total = d.latest.reduce((s, r) => s + r.bankroll, 0);
  const start = d.latest.length * 1000;
  const openStakes = d.latest.reduce((s, r) => s + r.open_stakes, 0);
  const settled = d.bets.filter((b) => b.status === "won" || b.status === "lost");
  const winRate = settled.length ? settled.filter((b) => b.status === "won").length / settled.length : null;

  const placedToday = d.bets.filter((b) => b.placed_at.slice(0, 10) === d.latestDate);
  const biggestEdge = [...d.openBets].sort((a, b) => b.model_p * b.odds - a.model_p * a.odds)[0];
  const nextKickoff = d.openBets[0];

  const eplFirst = (a: { wallet: string }, b: { wallet: string }) =>
    (a.wallet.startsWith("epl") ? 0 : 1) - (b.wallet.startsWith("epl") ? 0 : 1) || a.wallet.localeCompare(b.wallet);
  const wallets = [...d.latest].sort(eplFirst);
  const series = [...d.liveCurves]
    .sort(eplFirst)
    .map((c) => ({ name: `${SPORT_LABEL[sportOf(c.wallet)]} · ${strategyOf(c.wallet)}`, color: SPORT_COLOR[sportOf(c.wallet)], points: c.points }));

  return (
    <>
      <PageHeader eyebrow={`Updated ${d.latestDate || "—"}`} title="Overview" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
        {/* Hero: total bankroll */}
        <Reveal i={0} className="lg:col-span-7">
          <Card className="flex h-full flex-col">
            <div className="mb-7 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-[13px] font-medium text-ink-3">Total virtual bankroll</p>
                <p className="mt-2 text-5xl font-semibold leading-none tracking-tighter text-ink tabular md:text-6xl">{money(total)}</p>
                <Delta value={total - start} className="mt-3 text-[13px]">
                  {money(total - start, { sign: true })} ({pct((total - start) / (start || 1), true)}) since start
                </Delta>
              </div>
              <Sparkline points={d.totalCurve} start={start} />
            </div>
            <div className="mt-auto grid grid-cols-3 gap-4 border-t border-line-soft pt-5">
              <Stat label="In open bets" value={money(openStakes, { cents: false })} sub={`${d.openBets.length} bets`} />
              <Stat label="Settled" value={settled.length} sub={settled.length ? `${money(settled.reduce((s, b) => s + b.pnl, 0), { sign: true })} P&L` : "none yet"} />
              <Stat label="Win rate" value={winRate === null ? "—" : pct(winRate, false, 0)} sub="settled bets" />
            </div>
          </Card>
        </Reveal>

        {/* Wallets */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:col-span-5 lg:grid-cols-1 lg:gap-5">
          {wallets.map((w, i) => {
            const sport = sportOf(w.wallet);
            return (
              <Reveal key={w.wallet} i={i + 1}>
                <Card as="article" className="h-full">
                  <div className="flex items-center justify-between">
                    <SportTag sport={sport} />
                    <span className="font-mono text-[11px] text-ink-3">{strategyOf(w.wallet)}</span>
                  </div>
                  <p className="mt-4 text-[28px] font-semibold leading-none tracking-tight text-ink tabular">{money(w.bankroll)}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-ink-3">
                    <Delta value={w.bankroll - 1000}>{money(w.bankroll - 1000, { sign: true })}</Delta>
                    <span>{w.bets_settled} settled</span>
                    <span>{w.bets_open} open</span>
                    {w.bets_settled > 0 && <span>ROI {pct(w.roi, true)}</span>}
                  </div>
                  <ExposureBar cash={w.cash} open={w.open_stakes} sport={sport} />
                </Card>
              </Reveal>
            );
          })}
        </div>

        {/* Live chart */}
        <Reveal i={3} className="lg:col-span-8">
          <Card className="h-full">
            <CardHeader title="Live bankroll" hint="One point per morning run. Bets use odds from before each match, so this line cannot be tuned after the fact." />
            <BankrollChart series={series} height={260} />
          </Card>
        </Reveal>

        {/* Today's slate */}
        <Reveal i={4} className="lg:col-span-4">
          <Card className="flex h-full flex-col">
            <CardHeader title="Today's slate" />
            <div className="grid grid-cols-2 gap-4">
              <Stat label="Bets placed" value={placedToday.length} />
              <Stat label="Staked" value={money(placedToday.reduce((s, b) => s + b.stake, 0), { cents: false })} />
            </div>
            {biggestEdge ? (
              <div className="mt-5 rounded-2xl bg-sunken/70 p-4 ring-1 ring-line/70">
                <p className="flex items-center gap-1.5 text-[12px] font-medium text-ink-3">
                  <Lightning size={14} weight="fill" aria-hidden /> Biggest claimed edge
                </p>
                <p className="mt-2 text-[14px] font-semibold text-ink">{biggestEdge.pick}</p>
                <p className="text-[12px] text-ink-3">{biggestEdge.match}</p>
                <p className="mt-2 text-[12px] text-ink-2 tabular">
                  @ {biggestEdge.odds.toFixed(2)} · Elo {pct(biggestEdge.model_p, false, 0)} vs market {pct(biggestEdge.market_p, false, 0)}
                </p>
              </div>
            ) : (
              <p className="mt-5 text-[13px] text-ink-3">No open bets.</p>
            )}
            {nextKickoff && (
              <p className="mt-auto flex items-center gap-2 pt-5 text-[12px] text-ink-3">
                <Clock size={14} aria-hidden /> Next start {when(nextKickoff.commence_time)}
              </p>
            )}
          </Card>
        </Reveal>

        {/* Recent activity */}
        <Reveal i={5} className="lg:col-span-7">
          <Card className="h-full">
            <CardHeader
              title="Recent activity"
              action={<Link href="/bets" className="inline-flex min-h-9 items-center gap-1 rounded-full px-3 text-[13px] font-medium text-ink-2 ring-1 ring-line transition-colors hover:bg-sunken active:scale-[0.98]">All bets <ArrowRight size={14} aria-hidden /></Link>}
            />
            {d.bets.length ? (
              <ul className="divide-y divide-line-soft">
                {d.bets.slice(0, 6).map((b) => <ActivityRow key={b.bet_id} bet={b} />)}
              </ul>
            ) : (
              <EmptyState icon={<Clock size={18} />} title="No bets yet">The morning agent places the first bets at 06:00.</EmptyState>
            )}
          </Card>
        </Reveal>

        {/* Model check */}
        <Reveal i={6} className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader title="Model check" hint="How the current strategy did in the backtest, against the bookmaker." />
            {d.backtest && (["epl", "atp"] as const).map((k) => {
              const b = d.backtest![k];
              const gap = b.log_loss.elo - b.log_loss.bookmaker;
              return (
                <div key={k} className="flex items-center justify-between gap-4 border-t border-line-soft py-3.5 first:border-t-0 first:pt-0">
                  <div className="min-w-0">
                    <SportTag sport={k} />
                    <p className="mt-1.5 text-[12px] text-ink-3">Log loss Elo {b.log_loss.elo.toFixed(3)} · bookmaker {b.log_loss.bookmaker.toFixed(3)}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-down-soft px-2.5 py-1 text-[11px] font-semibold text-down tabular">
                    {gap.toFixed(3)} behind
                  </span>
                </div>
              );
            })}
            <Link href="/model" className="mt-3 inline-flex min-h-9 items-center gap-1 text-[13px] font-medium text-ink-2 underline-offset-4 hover:text-ink hover:underline">
              How the model works <ArrowRight size={14} aria-hidden />
            </Link>
          </Card>
        </Reveal>
      </div>
    </>
  );
}

function ExposureBar({ cash, open, sport }: { cash: number; open: number; sport: "epl" | "atp" }) {
  const share = open / (cash + open || 1);
  return (
    <div className="mt-5">
      <div className="flex h-1.5 overflow-hidden rounded-full bg-sunken">
        <span className="h-full rounded-full" style={{ width: `${share * 100}%`, background: SPORT_COLOR[sport] }} />
      </div>
      <p className="mt-1.5 text-[11px] text-ink-3 tabular">{pct(share, false, 0)} of bankroll in open bets</p>
    </div>
  );
}

function ActivityRow({ bet }: { bet: Bet }) {
  const sport = sportOf(bet.wallet);
  const status = {
    open: { icon: <Clock size={16} aria-hidden />, text: "Open", tone: "text-ink-3" },
    won: { icon: <CheckCircle size={16} weight="fill" aria-hidden />, text: money(bet.pnl, { sign: true }), tone: "text-up" },
    lost: { icon: <XCircle size={16} weight="fill" aria-hidden />, text: money(bet.pnl, { sign: true }), tone: "text-down" },
    void: { icon: <Clock size={16} aria-hidden />, text: "Void", tone: "text-ink-3" },
  }[bet.status];
  return (
    <li className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
      <span className="size-2 shrink-0 rounded-full" style={{ background: SPORT_COLOR[sport] }} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium text-ink">{bet.pick} <span className="font-normal text-ink-3">@ {bet.odds.toFixed(2)}</span></p>
        <p className="truncate text-[12px] text-ink-3">{bet.match} · {when(bet.commence_time)}</p>
      </div>
      <span className={`inline-flex shrink-0 items-center gap-1 text-[12px] font-semibold tabular ${status.tone}`}>
        {status.icon}{status.text}
      </span>
    </li>
  );
}
