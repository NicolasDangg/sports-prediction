import Link from "next/link";
import { ArrowRight, Flask, Trophy } from "@phosphor-icons/react/ssr";
import { LogLossBars, ProgressBar, RulesSummary, StatusBadge } from "@/components/ExperimentBlocks";
import Reveal from "@/components/Reveal";
import { Card, CardHeader, EmptyState, PageHeader, SportTag, Stat } from "@/components/ui";
import { loadExperiments, TEST_BUDGET } from "@/lib/experiments";
import { money, pct } from "@/lib/format";

export const metadata = { title: "Experiments · Closing Line" };

export default function ExperimentsPage() {
  const x = loadExperiments();
  const ran = x.list.filter((e) => e.status !== "planned");
  const next = x.next[0];
  const best = x.leaderboard[0];
  const bars = x.benchmark
    ? [
        { label: "Raw Elo (elo_v0)", value: x.benchmark.raw_elo, tone: "base" as const },
        ...x.leaderboard.map((r, i) => ({ label: r.model.startsWith(r.id) ? r.model : `${r.id} · ${r.model}`, value: r.log_loss, tone: i === 0 ? ("best" as const) : ("model" as const) })),
        { label: "Bookmaker", value: x.benchmark.bookmaker, tone: "book" as const },
      ].sort((a, b) => b.value - a.value)
    : [];

  return (
    <>
      <PageHeader eyebrow="Research" title="Experiments" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
        <Reveal i={0} className="lg:col-span-12">
          <Card>
            <div className="grid grid-cols-2 gap-x-6 gap-y-5 md:grid-cols-4">
              <Stat label="Experiments run" value={ran.length}
                    sub={`${x.counts.not_shipped ?? 0} not shipped · ${(x.counts.live ?? 0) + (x.counts.collecting ?? 0)} collecting live data`} />
              <Stat label="Live now" value={x.live.length} sub={x.live.map((e) => e.id).join(" · ") || "none"} />
              <div className="min-w-0">
                <Stat label="Test-set looks" value={`${x.testLooks} / ${TEST_BUDGET}`} sub="each look wears the test years out" />
                <div className="mt-2 h-1.5 rounded-full bg-sunken">
                  <div className={`h-full rounded-full ${x.testLooks >= TEST_BUDGET ? "bg-down" : "bg-ink-3"}`}
                       style={{ width: `${Math.min(100, (x.testLooks / TEST_BUDGET) * 100)}%` }} />
                </div>
              </div>
              <Stat label="Next up" value={next ? next.id : "—"} sub={next ? next.title : "nothing planned"} />
            </div>
          </Card>
        </Reveal>

        <Reveal i={1} className="lg:col-span-7">
          <Card className="h-full">
            <CardHeader title="Best forecasters"
                        hint={x.benchmark ? `${x.benchmark.label}. Each experiment's best model on the same matches.` : undefined} />
            {bars.length ? <LogLossBars rows={bars} reference={x.benchmark?.bookmaker} /> : <p className="text-[13px] text-ink-3">No results yet.</p>}
            {best && x.benchmark && (
              <p className="mt-4 rounded-2xl bg-sunken/70 p-4 text-[13px] leading-relaxed text-ink-2 ring-1 ring-line/70">
                <Trophy size={15} weight="fill" className="mr-1.5 inline text-atp" aria-hidden />
                <b className="text-ink">{best.id}</b> is the most accurate so far, closing{" "}
                {pct((x.benchmark.raw_elo - best.log_loss) / (x.benchmark.raw_elo - x.benchmark.bookmaker), false, 0)} of the gap
                between raw Elo and the bookmaker. Being more accurate hasn&apos;t yet meant beating the odds.
              </p>
            )}
          </Card>
        </Reveal>

        <Reveal i={2} className="lg:col-span-5">
          <Card className="flex h-full flex-col">
            <CardHeader title="Live strategies" hint="Real paper bets placed before each match. The final judge." />
            {x.stats.length ? (
              <ul className="flex flex-col divide-y divide-line-soft">
                {x.stats.map((s) => (
                  <li key={s.wallet} className="flex items-center justify-between gap-3 py-3 first:pt-0">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <SportTag sport={s.sport} />
                      <span className="truncate font-mono text-[13px] text-ink">{s.strategy}</span>
                      {x.bestLive?.wallet === s.wallet && <Trophy size={14} weight="fill" className="text-atp" aria-label="best ROI" />}
                    </div>
                    <div className="text-right text-[12px] text-ink-3 tabular">
                      <span className={`font-semibold ${s.net >= 0 ? "text-up" : "text-down"}`}>{money(s.net, { sign: true })}</span>
                      <span className="ml-2">{s.settled} settled{s.winRate !== null ? ` · ${pct(s.winRate, false, 0)} won` : ""}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-ink-3">No wallets yet.</p>
            )}
            <Link href="/strategies" className="mt-auto inline-flex items-center gap-1 pt-4 text-[13px] font-medium text-ink-2 hover:text-ink">
              Compare side by side <ArrowRight size={14} aria-hidden />
            </Link>
          </Card>
        </Reveal>

        <Reveal i={3} className="lg:col-span-12">
          <Card>
            <CardHeader title="All experiments" hint="Newest first. Each one is pre-registered: its pass/fail rules were written down before the numbers were seen." />
            {x.list.length ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {x.list.map((e) => (
                  <Link key={e.id} href={`/experiments/${e.id.toLowerCase()}`}
                        className="group flex flex-col gap-3 rounded-2xl border border-line/80 bg-surface p-4 transition-colors hover:border-line hover:bg-sunken/40 active:scale-[0.99]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[12px] font-semibold text-ink-3">{e.id}</span>
                      <StatusBadge status={e.status} />
                    </div>
                    <div>
                      <p className="text-[14px] font-semibold leading-snug text-ink">{e.title}</p>
                      <p className="mt-1 text-[12px] text-ink-3">{e.date || "not started"} · {e.kind}</p>
                    </div>
                    <p className="line-clamp-3 text-[13px] leading-relaxed text-ink-2">{e.verdict ?? e.hypothesis}</p>
                    {e.progress_now && <ProgressBar {...e.progress_now} />}
                    <div className="mt-auto flex items-center justify-between pt-1">
                      <RulesSummary passed={e.rulesPassed} known={e.rulesKnown} total={e.rules.length} />
                      <ArrowRight size={14} className="text-ink-3 transition-transform group-hover:translate-x-0.5" aria-hidden />
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState icon={<Flask size={18} />} title="No experiments yet">Add entries to experiments/registry.json.</EmptyState>
            )}
          </Card>
        </Reveal>
      </div>
    </>
  );
}
