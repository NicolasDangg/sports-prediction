import { notFound } from "next/navigation";
import EntityChart from "@/components/EntityChart";
import { Breadcrumb, ExpectedVsActual, Tile, UpcomingAndBets } from "@/components/EntityBlocks";
import MatchLog from "@/components/MatchLog";
import SquadView from "@/components/SquadView";
import { loadSquad } from "@/lib/squad";
import Reveal from "@/components/Reveal";
import { Card, CardHeader } from "@/components/ui";
import { loadTeam, teamSlugs } from "@/lib/entities";

export const dynamicParams = false;
export const generateStaticParams = teamSlugs;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const t = loadTeam((await params).slug);
  return { title: t ? `${t.name} · Closing Line` : "Closing Line" };
}

const ordinal = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
const rec = (r: { w: number; d: number; l: number }) => `${r.w}–${r.d}–${r.l}`;

export default async function TeamPage({ params }: { params: Promise<{ slug: string }> }) {
  const t = loadTeam((await params).slug);
  if (!t) notFound();
  const e = t.entity;
  const s = t.season;
  const squad = loadSquad(t.name);

  return (
    <>
      <Breadcrumb label="Premier League" />
      <header className="mb-6 flex flex-col gap-4 md:mb-8 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-3">Premier League · Elo #{t.eloRank} of {t.total}</p>
          <h1 className="mt-1.5 text-[34px] font-semibold leading-none tracking-tighter text-ink md:text-[44px]">{t.name}</h1>
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
          <Tile label="League position" value={e.pos ? ordinal(e.pos) : "—"} sub={`${e.pts} pts from ${e.played} games · Elo ranks them ${ordinal(t.eloRank)}`} className="h-full" />
        </Reveal>
        <Reveal i={1} className="lg:col-span-3">
          <Tile label="This season (W–D–L)" value={rec(s.all)} sub={`Goals ${s.all.gf}–${s.all.ga} · home ${rec(s.home)} · away ${rec(s.away)}`} className="h-full" />
        </Reveal>
        <Reveal i={2} className="lg:col-span-6">
          <div className="grid h-full grid-cols-1 gap-5 rounded-2xl border border-line/80 bg-surface p-5 shadow-diffuse sm:grid-cols-2">
            <ExpectedVsActual expected={s.all.expectedWins} actual={s.all.w} n={s.all.p} />
            <div className="border-line-soft sm:border-l sm:pl-5">
              <p className="text-[12px] font-medium text-ink-3">Since 2024/25</p>
              <p className="mt-1.5 text-[26px] font-semibold leading-none tracking-tight text-ink tabular">{rec(t.sinceStart.all)}</p>
              <p className="mt-2 text-[12px] text-ink-3">
                {t.sinceStart.all.w} wins vs {t.sinceStart.all.expectedWins.toFixed(1)} expected · home {rec(t.sinceStart.home)} · away {rec(t.sinceStart.away)}
              </p>
            </div>
          </div>
        </Reveal>

        <Reveal i={3} className="sm:col-span-2 lg:col-span-12">
          <Card>
            <CardHeader title="Elo after every match" hint="Each step is one game. Summer drops are the between-season pull toward the average." />
            <EntityChart points={t.history} color="var(--color-epl)" seasonStarts={t.seasonStarts} />
          </Card>
        </Reveal>

        {squad && (
          <Reveal i={4} className="sm:col-span-2 lg:col-span-12">
            <Card>
              <CardHeader title="Squad" hint="Click any player for their stats, expected goals and FPL numbers. Updated every morning." />
              <SquadView squad={squad} teamName={t.name} />
            </Card>
          </Reveal>
        )}

        <Reveal i={5} className="sm:col-span-2 lg:col-span-12">
          <Card>
            <CardHeader title="Upcoming and bets" />
            <UpcomingAndBets upcoming={t.upcoming} bets={t.bets} apiNames={t.apiNames} />
          </Card>
        </Reveal>

        <Reveal i={6} className="sm:col-span-2 lg:col-span-12">
          <section className="overflow-hidden rounded-[1.75rem] border border-line/80 bg-surface shadow-diffuse">
            <div className="px-6 pb-2 pt-6 md:px-7">
              <h2 className="text-[15px] font-semibold tracking-tight text-ink">Match log</h2>
              <p className="mt-1 text-[13px] text-ink-3">Newest first, since 2024/25. &ldquo;Upset&rdquo; = the model gave that result under 25%. Opponents link to their page.</p>
            </div>
            <MatchLog rows={t.rows} sport="epl" />
          </section>
        </Reveal>
      </div>
    </>
  );
}
