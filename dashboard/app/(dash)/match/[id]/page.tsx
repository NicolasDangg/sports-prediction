import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowSquareOut, CaretLeft, Receipt } from "@phosphor-icons/react/ssr";
import Reveal from "@/components/Reveal";
import { Card, CardHeader } from "@/components/ui";
import { money, pct, when } from "@/lib/format";
import { atpMatchIds, FEATURED_BOOKS, loadAtpMatch, type AtpMatchDetail } from "@/lib/match";

export const dynamicParams = false;
export const generateStaticParams = atpMatchIds;

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const m = loadAtpMatch((await params).id);
  return { title: m ? `${m.home.api} v ${m.away.api} · Closing Line` : "Closing Line" };
}

type Side = AtpMatchDetail["home"];

function PlayerName({ p, className = "" }: { p: Side; className?: string }) {
  return p.slug ? (
    <Link href={`/ratings/atp/${p.slug}`} className={`underline-offset-4 hover:underline ${className}`}>{p.api}</Link>
  ) : <span className={className}>{p.api}</span>;
}

/** One row of the "who wins" card: a split bar, home share from the left. */
function SplitBar({ label, hint, home, strong = false }: { label: string; hint: string; home: number; strong?: boolean }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-[13px]">
        <span className={`font-mono tabular ${strong ? "font-semibold text-ink" : "text-ink-2"}`}>{pct(home)}</span>
        <span className="text-center">
          <span className="font-medium text-ink">{label}</span>
          <span className="ml-1.5 text-ink-3">{hint}</span>
        </span>
        <span className={`font-mono tabular ${strong ? "font-semibold text-ink" : "text-ink-2"}`}>{pct(1 - home)}</span>
      </div>
      <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-sunken" aria-hidden>
        <span className={`h-full ${strong ? "bg-atp" : "bg-ink-3/60"}`} style={{ width: `${home * 100}%` }} />
        <span className="h-full flex-1 bg-line" />
      </div>
    </div>
  );
}

const fair = (p: number) => (p > 0 ? (1 / p).toFixed(2) : "—");
const date = (d: string) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "2-digit" });

function Form({ p, form, surface }: { p: Side; form: AtpMatchDetail["form"]["home"]; surface: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[14px] font-semibold text-ink"><PlayerName p={p} /></p>
      {p.name ? (
        <p className="mt-0.5 text-[12px] text-ink-3">
          Elo <span className="font-mono text-ink-2 tabular">{p.elo !== null ? Math.round(p.elo) : "—"}</span>
          {" · "}{surface} <span className="font-mono text-ink-2 tabular">{p.surfaceElo !== null ? Math.round(p.surfaceElo) : "—"}</span>
        </p>
      ) : <p className="mt-0.5 text-[12px] text-ink-3">Not in our match history yet</p>}
      {form && form.last10.length > 0 && (
        <>
          <div className="mt-3 flex flex-wrap gap-1" aria-label={`Last ${form.last10.length}: ${form.wins10} wins`}>
            {[...form.last10].reverse().map((r, i) => (
              <span key={i} title={`${date(r.date)} · ${r.result === "W" ? "beat" : "lost to"} ${r.opponent} · ${r.tournament} ${r.round}`}
                className={`grid size-6 place-items-center rounded-md text-[11px] font-semibold ${r.result === "W" ? "bg-up-soft text-up" : "bg-down-soft text-down"}`}>
                {r.result}
              </span>
            ))}
          </div>
          <p className="mt-2 text-[12px] text-ink-3">
            Last {form.last10.length}: <span className="font-medium text-ink-2">{form.wins10}–{form.last10.length - form.wins10}</span>
            {" · "}on {surface} since 2025: <span className="font-medium text-ink-2">{form.surfaceW}–{form.surfaceP - form.surfaceW}</span>
          </p>
          <ul className="mt-3 flex flex-col divide-y divide-line-soft text-[12px]">
            {form.last10.slice(0, 5).map((r, i) => (
              <li key={i} className="flex items-center justify-between gap-3 py-1.5">
                <span className="shrink-0 text-ink-2">
                  <span className={r.result === "W" ? "text-up" : "text-down"}>{r.result === "W" ? "Beat" : "Lost to"}</span> {r.opponent}
                </span>
                <span className="min-w-0 truncate text-right text-ink-3">{r.tournament.replace(/ (Open|Masters|Championships)$/, "")} · {date(r.date)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default async function MatchPage({ params }: { params: Promise<{ id: string }> }) {
  const m = loadAtpMatch((await params).id);
  if (!m) notFound();
  const { home, away } = m;
  const valueHome = m.model ? m.model.home * m.best.home - 1 : null;
  const valueAway = m.model ? m.model.away * m.best.away - 1 : null;
  const h2hHome = m.h2h.filter((x) => x.winner === home.name).length;

  return (
    <>
      <Link href="/markets" className="mb-4 inline-flex min-h-9 items-center gap-1 text-[13px] font-medium text-ink-3 transition-colors hover:text-ink">
        <CaretLeft size={14} weight="bold" aria-hidden /> Markets
      </Link>
      <header className="mb-6 md:mb-8">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-3">
          {m.competition.replace(/^ATP /, "ATP · ")} · {m.surface} · {when(m.commence_time)}
        </p>
        <h1 className="mt-2 text-[28px] font-semibold leading-tight tracking-tighter text-ink md:text-[40px]">
          <PlayerName p={home} /> <span className="text-ink-3">v</span> <PlayerName p={away} />
        </h1>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
        <Reveal i={0} className="lg:col-span-7">
          <Card className="h-full">
            <CardHeader title="Who wins" hint="Our surface Elo against the bookmakers' consensus (median price, margin removed)." />
            <div className="mb-4 flex justify-between text-[13px] font-medium text-ink">
              <span className="truncate">{home.api}</span>
              <span className="truncate text-right">{away.api}</span>
            </div>
            <div className="flex flex-col gap-5">
              {m.model ? (
                <SplitBar label="Model" hint={m.model.source === "forecast" ? "this morning's forecast" : "from latest ratings"} home={m.model.home} strong />
              ) : (
                <p className="rounded-xl bg-sunken px-4 py-3 text-[13px] text-ink-3">No model price: one of the players isn&apos;t in our match history.</p>
              )}
              <SplitBar label="Market" hint={`${m.board.length} books`} home={m.market.home} />
            </div>
            <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-line-soft pt-5 text-[13px]">
              {(["home", "away"] as const).map((k) => {
                const value = k === "home" ? valueHome : valueAway;
                return (
                  <div key={k} className={k === "away" ? "text-right" : ""}>
                    <dt className="text-[12px] text-ink-3">Fair odds (model) · best price</dt>
                    <dd className="mt-0.5 font-mono text-ink tabular">
                      {m.model ? fair(m.model[k]) : "—"} · <span className="font-semibold">{m.best[k].toFixed(2)}</span>
                    </dd>
                    {value !== null && (
                      <dd className={`mt-0.5 text-[12px] font-medium tabular ${value > 0 ? "text-up" : "text-ink-3"}`}>
                        {value > 0 ? `+${pct(value)} edge at best price` : `no edge (${pct(value)})`}
                      </dd>
                    )}
                  </div>
                );
              })}
            </dl>
            {m.bet && (
              <p className="mt-5 flex items-center gap-2 rounded-xl bg-atp-soft px-4 py-3 text-[13px] text-ink-2">
                <Receipt size={16} className="shrink-0 text-atp" aria-hidden />
                <span>Paper bet placed: <span className="font-medium text-ink">{m.bet.pick}</span> @ {m.bet.odds} for {money(m.bet.stake)} ({m.bet.status})</span>
              </p>
            )}
          </Card>
        </Reveal>

        <Reveal i={1} className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader title="Head to head" hint="Every meeting in our data (2025 onward)." />
            {m.h2h.length === 0 ? (
              <p className="text-[13px] text-ink-3">They haven&apos;t met in our data.</p>
            ) : (
              <>
                <p className="font-mono text-[32px] font-semibold leading-none text-ink tabular">
                  {h2hHome}<span className="text-ink-3">–</span>{m.h2h.length - h2hHome}
                </p>
                <ul className="mt-4 flex flex-col divide-y divide-line-soft text-[13px]">
                  {m.h2h.map((x, i) => (
                    <li key={i} className="flex items-center justify-between gap-3 py-2">
                      <span className="min-w-0 truncate"><span className="font-medium text-ink">{x.winner}</span> <span className="text-ink-3">won {x.score}</span></span>
                      <span className="shrink-0 text-ink-3">{x.tournament} · {x.surface} · {date(x.date)}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>
        </Reveal>

        <Reveal i={2} className="lg:col-span-7">
          <Card className="h-full !px-0 md:!px-0">
            <div className="px-6 md:px-7">
              <CardHeader title="Odds board" hint={`Decimal prices from ${m.board.length} books, as of ${when(m.pricedAt)}. Best price per player in bold.`} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-line text-left text-[12px] text-ink-3">
                    <th className="py-2.5 pl-6 pr-3 font-medium md:pl-7">Book</th>
                    <th className="px-3 py-2.5 text-right font-medium">{home.api.split(" ").at(-1)}</th>
                    <th className="py-2.5 pl-3 pr-6 text-right font-medium sm:px-3">{away.api.split(" ").at(-1)}</th>
                    <th className="hidden py-2.5 pl-3 pr-6 text-right font-medium sm:table-cell md:pr-7" title="How much the book keeps: 1/home + 1/away − 1">Margin</th>
                  </tr>
                </thead>
                <tbody>
                  {m.board.map((r) => (
                    <tr key={r.book} className={`border-b border-line-soft last:border-0 ${FEATURED_BOOKS.has(r.book) ? "bg-sunken/60" : ""}`}>
                      <td className="py-2.5 pl-6 pr-3 font-medium text-ink md:pl-7">
                        {r.label}
                        {r.book === "pinnacle" && <span className="ml-2 text-[11px] font-normal text-ink-3">sharpest</span>}
                      </td>
                      <td className={`px-3 py-2.5 text-right font-mono tabular ${r.home === m.best.home ? "font-semibold text-ink" : "text-ink-2"}`}>{r.home.toFixed(2)}</td>
                      <td className={`py-2.5 pl-3 pr-6 text-right font-mono tabular sm:px-3 ${r.away === m.best.away ? "font-semibold text-ink" : "text-ink-2"}`}>{r.away.toFixed(2)}</td>
                      <td className="hidden py-2.5 pl-3 pr-6 text-right font-mono text-ink-3 tabular sm:table-cell md:pr-7">{pct(r.margin)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-line text-ink-3">
                    <td className="py-2.5 pl-6 pr-3 md:pl-7">Median</td>
                    <td className="px-3 py-2.5 text-right font-mono tabular">{m.market.medianHome.toFixed(2)}</td>
                    <td className="py-2.5 pl-3 pr-6 text-right font-mono tabular sm:px-3">{m.market.medianAway.toFixed(2)}</td>
                    <td className="hidden py-2.5 pl-3 pr-6 sm:table-cell md:pr-7" />
                  </tr>
                </tfoot>
              </table>
            </div>
          </Card>
        </Reveal>

        <Reveal i={3} className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader title="Form" hint="Most recent first in the list; chips run oldest to newest." />
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-1">
              <Form p={home} form={m.form.home} surface={m.surface} />
              <Form p={away} form={m.form.away} surface={m.surface} />
            </div>
          </Card>
        </Reveal>

        <Reveal i={4} className="lg:col-span-12">
          <Card>
            <CardHeader
              title="SofaScore"
              hint="Live score and in-match stats live on SofaScore."
              action={
                <a href={m.sofascore.search} target="_blank" rel="noopener noreferrer"
                  className="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl border border-line px-3 text-[13px] font-medium text-ink transition-colors hover:bg-sunken">
                  Find on SofaScore <ArrowSquareOut size={14} aria-hidden />
                </a>
              }
            />
            {m.sofascore.widget ? (
              <iframe
                src={m.sofascore.widget}
                title={`SofaScore: ${m.competition}`}
                loading="lazy"
                className="h-[640px] w-full rounded-xl border border-line-soft"
              />
            ) : (
              <p className="text-[13px] leading-relaxed text-ink-3">
                No SofaScore widget set up for {m.competition} yet. On SofaScore, open the tournament, use its embed option, and add the
                iframe&apos;s <code className="rounded bg-sunken px-1 font-mono text-[12px]">src</code> to{" "}
                <code className="rounded bg-sunken px-1 font-mono text-[12px]">state/sofascore.csv</code> next to{" "}
                <code className="rounded bg-sunken px-1 font-mono text-[12px]">{m.sport_key}</code>.
              </p>
            )}
          </Card>
        </Reveal>
      </div>
    </>
  );
}
