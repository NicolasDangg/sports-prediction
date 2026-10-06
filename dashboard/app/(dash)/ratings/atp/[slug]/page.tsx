import { notFound } from "next/navigation";
import EntityChart from "@/components/EntityChart";
import { Breadcrumb, ExpectedVsActual, Tile, UpcomingAndBets } from "@/components/EntityBlocks";
import MatchLog from "@/components/MatchLog";
import Reveal from "@/components/Reveal";
import { Card, CardHeader } from "@/components/ui";
import { loadPlayer, playerSlugs } from "@/lib/entities";

export const dynamicParams = false;
export const generateStaticParams = playerSlugs;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const p = loadPlayer((await params).slug);
  return { title: p ? `${p.name} · Closing Line` : "Closing Line" };
}

export default async function PlayerPage({ params }: { params: Promise<{ slug: string }> }) {
  const p = loadPlayer((await params).slug);
  if (!p) notFound();
  const e = p.entity;
  const wins10 = e.form.split("").filter((r) => r === "W").length;

  return (
    <>
      <Breadcrumb label="ATP" />
      <header className="mb-6 flex flex-col gap-4 md:mb-8 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-3">ATP · Elo #{p.eloRank} of the top {p.total}</p>
          <h1 className="mt-1.5 text-[34px] font-semibold leading-none tracking-tighter text-ink md:text-[44px]">{p.name}</h1>
        </div>
        <div className="text-left md:text-right">
          <p className="font-mono text-[40px] font-semibold leading-none tracking-tight text-ink tabular">{Math.round(e.elo)}</p>
          <p className={`mt-1 text-[13px] font-medium tabular ${e.change10 > 0 ? "text-up" : e.change10 < 0 ? "text-down" : "text-ink-3"}`}>
            {e.change10 > 0 ? "+" : e.change10 < 0 ? "−" : ""}{Math.abs(Math.round(e.change10))} over the last 10 matches
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-12 lg:gap-5">
        <Reveal i={0} className="lg:col-span-3">
          <Tile label="Last 10" value={`${wins10}–${10 - wins10}`} sub={`2025 onward: ${p.all.w}–${p.all.l}`} className="h-full" />
        </Reveal>
        <Reveal i={1} className="lg:col-span-4">
          <div className="h-full rounded-2xl border border-line/80 bg-surface p-5 shadow-diffuse">
            <p className="text-[12px] font-medium text-ink-3">Surface ratings</p>
            <dl className="mt-2 grid grid-cols-3 gap-3">
              {p.surfaces && ([["Hard", p.surfaces.hard], ["Clay", p.surfaces.clay], ["Grass", p.surfaces.grass]] as const).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-[11px] text-ink-3">{k}</dt>
                  <dd className="font-mono text-[20px] font-semibold text-ink tabular">{Math.round(v)}</dd>
                </div>
              ))}
            </dl>
          </div>
        </Reveal>
        <Reveal i={2} className="sm:col-span-2 lg:col-span-5">
          <div className="h-full rounded-2xl border border-line/80 bg-surface p-5 shadow-diffuse">
            <ExpectedVsActual expected={p.all.expectedWins} actual={p.all.w} n={p.all.p}
              market={{ expected: p.all.marketWins, actual: p.all.winsWithOdds, n: p.all.withOdds }} />
          </div>
        </Reveal>

        <Reveal i={3} className="sm:col-span-2 lg:col-span-8">
          <Card className="h-full">
            <CardHeader title="Elo after every match" hint="Overall rating. New players move fast; established ones slowly." />
            <EntityChart points={p.history} color="var(--color-atp)" />
          </Card>
        </Reveal>
        <Reveal i={4} className="sm:col-span-2 lg:col-span-4">
          <Card className="h-full">
            <CardHeader title="By surface, 2025 onward" hint="Record, and how many wins the model expected." />
            <ul className="flex flex-col gap-4">
              {p.bySurface.map((s) => (
                <li key={s.surface}>
                  <div className="flex items-baseline justify-between text-[13px]">
                    <span className="font-medium text-ink">{s.surface}</span>
                    <span className="font-mono text-ink tabular">{s.w}–{s.l}</span>
                  </div>
                  <span className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-down-soft" aria-hidden>
                    <span className="h-full rounded-full bg-atp" style={{ width: `${s.p ? (s.w / s.p) * 100 : 0}%` }} />
                  </span>
                  <p className="mt-1 text-[11px] text-ink-3 tabular">
                    {s.p ? `${Math.round((s.w / s.p) * 100)}% won · expected ${s.expectedWins.toFixed(1)} wins` : "No matches"}
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        </Reveal>

        <Reveal i={5} className="sm:col-span-2 lg:col-span-12">
          <Card>
            <CardHeader title="Upcoming and bets" />
            <UpcomingAndBets upcoming={p.upcoming} bets={p.bets} apiNames={p.apiNames} />
          </Card>
        </Reveal>

        <Reveal i={6} className="sm:col-span-2 lg:col-span-12">
          <section className="overflow-hidden rounded-[1.75rem] border border-line/80 bg-surface shadow-diffuse">
            <div className="px-6 pb-2 pt-6 md:px-7">
              <h2 className="text-[15px] font-semibold tracking-tight text-ink">Match log</h2>
              <p className="mt-1 text-[13px] text-ink-3">Newest first, 2025 onward. &ldquo;Upset&rdquo; = the model gave that result under 30%. Market = bookmaker probability with the margin removed.</p>
            </div>
            <MatchLog rows={p.rows} sport="atp" />
          </section>
        </Reveal>
      </div>
    </>
  );
}
