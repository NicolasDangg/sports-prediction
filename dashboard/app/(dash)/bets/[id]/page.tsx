import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowSquareOut, CaretLeft, CheckCircle, Clock, MagnifyingGlass, XCircle } from "@phosphor-icons/react/ssr";
import CopyButton from "@/components/CopyButton";
import Reveal from "@/components/Reveal";
import { Card, CardHeader } from "@/components/ui";
import { money, pct, strategyOf, when } from "@/lib/format";
import { loadBetReview, reviewIds, type BetReview } from "@/lib/review";

export const dynamicParams = false;
export const generateStaticParams = reviewIds;

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const r = loadBetReview((await params).id);
  return { title: r ? `${r.match} · Bet review · Closing Line` : "Closing Line" };
}

function Name({ name, href }: { name: string; href: string | null }) {
  return href ? <Link href={href} className="underline-offset-4 hover:underline">{name}</Link> : <>{name}</>;
}

function Status({ bet }: { bet: BetReview["bets"][number] }) {
  if (bet.status === "won") return <span className="inline-flex items-center gap-1 font-semibold text-up tabular"><CheckCircle size={15} weight="fill" aria-hidden />{money(bet.pnl, { sign: true })}</span>;
  if (bet.status === "lost") return <span className="inline-flex items-center gap-1 font-semibold text-down tabular"><XCircle size={15} weight="fill" aria-hidden />{money(bet.pnl, { sign: true })}</span>;
  if (bet.status === "open") return <span className="inline-flex items-center gap-1 rounded-full bg-sunken px-2 py-0.5 text-[11px] font-medium text-ink-2"><Clock size={12} aria-hidden />Open</span>;
  return <span className="text-ink-3">{bet.status === "void" ? "Void" : "Unresolved"}</span>;
}

const odds = (v: number | null | undefined) => (typeof v === "number" && !Number.isNaN(v) ? v.toFixed(2) : "—");

export default async function BetReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const r = loadBetReview((await params).id);
  if (!r) notFound();
  const { played } = r;
  const settled = r.bets.filter((b) => b.status === "won" || b.status === "lost");
  const pnl = settled.reduce((s, b) => s + b.pnl, 0);
  const isOpen = r.bets.every((b) => b.status === "open");

  return (
    <>
      <Link href="/bets" className="mb-4 inline-flex min-h-9 items-center gap-1 text-[13px] font-medium text-ink-3 transition-colors hover:text-ink">
        <CaretLeft size={14} weight="bold" aria-hidden /> Bets
      </Link>
      <header className="mb-6 md:mb-8">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-3">
          {r.competition} · {when(r.commence_time)}
        </p>
        <h1 className="mt-2 text-[28px] font-semibold leading-tight tracking-tighter text-ink md:text-[40px]">
          <Name name={r.home} href={r.homeHref} /> <span className="text-ink-3">v</span> <Name name={r.away} href={r.awayHref} />
        </h1>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
        <Reveal i={0} className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader
              title="How it played out"
              hint={isOpen ? "Not played yet. Results arrive the morning after, when the agent settles at 06:00." : r.resultSource ? `Result from ${r.resultSource === "odds_api" ? "The Odds API" : r.resultSource}.` : undefined}
            />
            {r.winner ? (
              <>
                <p className="text-[12px] text-ink-3">Winner</p>
                <p className="mt-0.5 text-[22px] font-semibold tracking-tight text-ink">{r.winner}</p>
                {played?.score && (
                  <p className="mt-3 font-mono text-[28px] font-semibold leading-none text-ink tabular">{played.score}</p>
                )}
                {played?.detail && <p className="mt-2 text-[12px] text-ink-3">{played.detail}</p>}
                {!played?.score && <p className="mt-3 text-[13px] text-ink-3">No score in our match file yet. SofaScore has the full story.</p>}
              </>
            ) : (
              <p className="text-[13px] text-ink-3">{isOpen ? "Waiting for the match." : "No result recorded."}</p>
            )}
            {settled.length > 0 && (
              <div className="mt-6 border-t border-line-soft pt-5">
                <p className="text-[12px] text-ink-3">Our P&amp;L on this match</p>
                <p className={`mt-0.5 text-lg font-semibold tracking-tight tabular ${pnl > 0 ? "text-up" : pnl < 0 ? "text-down" : "text-ink"}`}>
                  {money(pnl, { sign: true })}
                </p>
              </div>
            )}
          </Card>
        </Reveal>

        <Reveal i={1} className="lg:col-span-7">
          <Card className="h-full !px-0 md:!px-0">
            <div className="px-6 md:px-7">
              <CardHeader title="Our bets" hint="Every wallet that bet on this match. Closing value: our price against the last price before the start." />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-line text-left text-[12px] text-ink-3">
                    <th className="py-2.5 pl-6 pr-3 font-medium md:pl-7">Wallet · pick</th>
                    <th className="px-3 py-2.5 text-right font-medium">Odds</th>
                    <th className="px-3 py-2.5 text-right font-medium">Model / mkt</th>
                    <th className="px-3 py-2.5 text-right font-medium" title="Our odds ÷ closing odds − 1">Closing value</th>
                    <th className="py-2.5 pl-3 pr-6 text-right font-medium md:pr-7">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {r.bets.map((b) => (
                    <tr key={b.bet_id} className="border-b border-line-soft last:border-0">
                      <td className="py-3 pl-6 pr-3 md:pl-7">
                        <p className="font-medium text-ink">{b.pick}</p>
                        <p className="text-[12px] text-ink-3">{strategyOf(b.wallet)} · {money(b.stake)}</p>
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-ink tabular">
                        {b.odds.toFixed(2)}
                        {b.exec_book && <span className="block font-sans text-[11px] text-ink-3">{b.exec_book}</span>}
                      </td>
                      <td className="px-3 py-3 text-right text-ink-2 tabular">{pct(b.model_p, false, 0)} / {pct(b.market_p, false, 0)}</td>
                      <td className={`px-3 py-3 text-right tabular ${b.clv === null ? "text-ink-3" : b.clv > 0 ? "text-up" : "text-down"}`}>
                        {b.clv === null ? "—" : pct(b.clv, true)}
                        {b.closing !== null && <span className="block text-[11px] text-ink-3">closed {odds(b.closing)}</span>}
                      </td>
                      <td className="py-3 pl-3 pr-6 text-right md:pr-7"><Status bet={b} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </Reveal>

        {played && (
          <Reveal i={2} className="lg:col-span-5">
            <Card className="h-full">
              <CardHeader title="Rating moves" hint="Elo before and after this match, from our match file." />
              <dl className="flex flex-col gap-4 text-[13px]">
                {([[r.home, played.homeBefore, played.homeAfter], [r.away, played.awayBefore, played.awayAfter]] as const).map(([name, before, after]) => (
                  <div key={name} className="flex items-baseline justify-between gap-3">
                    <dt className="min-w-0 truncate font-medium text-ink">{name}</dt>
                    <dd className="shrink-0 font-mono text-ink-2 tabular">
                      {Math.round(before)} → {Math.round(after)}{" "}
                      <span className={after > before ? "text-up" : after < before ? "text-down" : "text-ink-3"}>
                        ({after >= before ? "+" : "−"}{Math.abs(after - before).toFixed(1)})
                      </span>
                    </dd>
                  </div>
                ))}
              </dl>
              {played.homeProb !== null && (
                <p className="mt-5 border-t border-line-soft pt-4 text-[12px] text-ink-3">
                  Elo gave {r.home} <span className="font-medium text-ink-2">{pct(played.homeProb, false, 0)}</span> going in.
                </p>
              )}
            </Card>
          </Reveal>
        )}

        <Reveal i={3} className={played ? "lg:col-span-7" : "lg:col-span-12"}>
          <Card className="h-full !px-0 md:!px-0">
            <div className="px-6 md:px-7">
              <CardHeader title="Price movement" hint="Median, Pinnacle and best price each time we checked the market." />
            </div>
            {r.history.length === 0 ? (
              <p className="px-6 text-[13px] text-ink-3 md:px-7">No snapshots saved for this match.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-line text-left text-[12px] text-ink-3">
                      <th className="py-2.5 pl-6 pr-3 font-medium md:pl-7">Checked</th>
                      {r.outcomes.map((o, i) => (
                        <th key={o} className={`py-2.5 text-right font-medium ${i === r.outcomes.length - 1 ? "pl-3 pr-6 md:pr-7" : "px-3"}`}>
                          {r.sport === "atp" ? o.split(" ").at(-1) : o}
                          <span className="block text-[11px] font-normal">med · pin · best</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {r.history.map(({ at, row }) => (
                      <tr key={at} className="border-b border-line-soft last:border-0">
                        <td className="whitespace-nowrap py-2.5 pl-6 pr-3 text-ink-2 md:pl-7">{when(at)}</td>
                        {r.outcomes.map((o, i) => (
                          <td key={o} className={`whitespace-nowrap py-2.5 text-right font-mono text-ink-2 tabular ${i === r.outcomes.length - 1 ? "pl-3 pr-6 md:pr-7" : "px-3"}`}>
                            {row[o] ? <>{odds(row[o].median_odds)} · {odds(row[o].pinnacle_odds)} · <span className="font-semibold text-ink">{odds(row[o].best_odds)}</span></> : "—"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </Reveal>

        <Reveal i={4} className="lg:col-span-12">
          <Card>
            <CardHeader
              title="SofaScore"
              hint="Scores, stats and the point-by-point (or minute-by-minute) story live on SofaScore."
              action={
                <a href={r.sofascore.search} target="_blank" rel="noopener noreferrer"
                  className="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl border border-line px-3 text-[13px] font-medium text-ink transition-colors hover:bg-sunken">
                  Find on SofaScore <ArrowSquareOut size={14} aria-hidden />
                </a>
              }
            />
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-sunken px-3 text-[13px] text-ink-2">
                <MagnifyingGlass size={14} aria-hidden />
                <span className="font-mono">{r.sofascore.term}</span>
              </span>
              <CopyButton text={r.sofascore.term} label="Copy search term" />
              {r.hasMatchPage && (
                <Link href={`/match/${r.id}`} className="inline-flex min-h-10 items-center text-[13px] font-medium text-ink-2 underline-offset-4 hover:text-ink hover:underline">
                  Pre-match odds board
                </Link>
              )}
            </div>
          </Card>
        </Reveal>
      </div>
    </>
  );
}
