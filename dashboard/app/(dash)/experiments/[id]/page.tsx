import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight, FileCode, LockKey, LockKeyOpen } from "@phosphor-icons/react/ssr";
import BankrollChart from "@/components/BankrollChart";
import { LogLossBars, MetricTable, ProgressBar, RuleList, StatusBadge } from "@/components/ExperimentBlocks";
import Reveal from "@/components/Reveal";
import { Card, CardHeader, SportTag, Stat } from "@/components/ui";
import { experimentIds, loadExperiment } from "@/lib/experiments";
import { SPORT_COLOR, strategyDash, money, pct } from "@/lib/format";

export const dynamicParams = false;
export const generateStaticParams = experimentIds;

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const x = loadExperiment((await params).id);
  return { title: x ? `${x.e.id} ${x.e.title} · Closing Line` : "Closing Line" };
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[12px] font-medium uppercase tracking-[0.12em] text-ink-3">{title}</h3>
      <div className="mt-1.5 max-w-[72ch] text-[14px] leading-relaxed text-ink-2">{children}</div>
    </div>
  );
}

export default async function ExperimentPage({ params }: { params: Promise<{ id: string }> }) {
  const x = loadExperiment((await params).id);
  if (!x) notFound();
  const { e, all } = x;
  const known = new Set(all.list.map((o) => o.id));
  const related = [...(e.depends_on ?? []).map((id) => ({ id, rel: "Builds on" })), ...e.followups.map((id) => ({ id, rel: "Led to" }))];
  const bars = (e.metrics ?? []).filter((m) => m.log_loss !== undefined).map((m) => ({
    label: m.model, value: m.log_loss!,
    tone: m.highlight ? ("best" as const) : /bookmaker/i.test(m.model) ? ("book" as const) : ("model" as const),
  }));

  return (
    <>
      <Link href="/experiments" className="mb-4 inline-flex min-h-9 items-center gap-1.5 text-[13px] font-medium text-ink-3 hover:text-ink">
        <ArrowLeft size={14} aria-hidden /> Experiments
      </Link>
      <header className="mb-6 flex flex-col gap-3 md:mb-8">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="font-mono text-[13px] font-semibold text-ink-3">{e.id}</span>
          <StatusBadge status={e.status} />
          {e.sport !== "both" && <SportTag sport={e.sport} />}
          <span className="text-[12px] text-ink-3">{e.kind}{e.date ? ` · ${e.date}` : ""}</span>
        </div>
        <h1 className="max-w-[28ch] text-[28px] font-semibold leading-tight tracking-tighter text-ink md:text-[36px]">{e.title}</h1>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
        <Reveal i={0} className="lg:col-span-7">
          <Card className="flex h-full flex-col gap-5">
            <Section title="The question">{e.hypothesis}</Section>
            <Section title="What changed">{e.change}</Section>
            {e.protocol && <Section title="How it was tested">{e.protocol}</Section>}
            <div className="mt-auto flex flex-wrap gap-x-5 gap-y-2 border-t border-line-soft pt-4 text-[12px] text-ink-3">
              {e.script && <span className="inline-flex items-center gap-1.5"><FileCode size={14} aria-hidden /><code>{e.script}</code></span>}
              {e.results_file && <span className="inline-flex items-center gap-1.5"><FileCode size={14} aria-hidden /><code>{e.results_file}</code></span>}
              {e.report && <span className="inline-flex items-center gap-1.5"><FileCode size={14} aria-hidden /><code>{e.report}</code></span>}
            </div>
          </Card>
        </Reveal>

        <Reveal i={1} className="lg:col-span-5">
          <Card className="flex h-full flex-col">
            <CardHeader title="Pass rules" hint="Written down before the results were seen." />
            <RuleList rules={e.rules} />
            {e.progress_now && <div className="mt-5"><ProgressBar {...e.progress_now} /></div>}
            <p className="mt-auto flex items-center gap-2 pt-5 text-[12px] text-ink-3">
              {e.test_look ? <LockKeyOpen size={15} aria-hidden /> : <LockKey size={15} aria-hidden />}
              {e.test_look ? "Used one look at the sealed test years." : "Test years untouched."}
            </p>
          </Card>
        </Reveal>

        {(e.metrics?.length ?? 0) > 0 && (
          <Reveal i={2} className="lg:col-span-12">
            <Card>
              <CardHeader title="Results" hint={e.metrics_note ?? "ATP validation years 2020–2022, the same matches for every model. Lower log loss is better."} />
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <MetricTable metrics={e.metrics!} />
                {bars.length > 1 && <LogLossBars rows={bars} />}
              </div>
            </Card>
          </Reveal>
        )}

        {e.verdict && (
          <Reveal i={3} className="lg:col-span-12">
            <Card>
              <CardHeader title="Verdict" />
              <p className="max-w-[80ch] text-[14px] leading-relaxed text-ink-2">{e.verdict}</p>
            </Card>
          </Reveal>
        )}

        {e.wallets.length > 0 && (
          <Reveal i={4} className="lg:col-span-12">
            <Card>
              <CardHeader title={`Live wallet${e.wallets.length > 1 ? "s" : ""}: ${e.strategy}`}
                          hint="Real paper bets placed before each match, net of money deposited." />
              <div className="grid grid-cols-2 gap-x-6 gap-y-5 md:grid-cols-5">
                {e.wallets.map((w) => (
                  <Stat key={w.wallet} label={w.wallet} value={money(w.net, { sign: true })}
                        sub={`${w.settled} settled · ${w.open} open`} />
                ))}
                <Stat label="Win rate" value={e.wallets[0].winRate === null ? "—" : pct(e.wallets[0].winRate, false, 0)}
                      sub={e.wallets[0].settled ? `model expected ${pct(e.wallets[0].expectedWins / e.wallets[0].settled, false, 0)}` : "nothing settled"} />
                <Stat label="ROI" value={e.wallets[0].roi === null ? "—" : pct(e.wallets[0].roi, true)} sub="settled stakes" />
                <Stat label="CLV" value={e.wallets[0].clv.mean === null ? "—" : pct(e.wallets[0].clv.mean, true)}
                      sub={e.wallets[0].clv.n ? `${e.wallets[0].clv.n} bets with a closing price` : "no closing prices yet"} />
              </div>
              <div className="mt-6">
                <BankrollChart series={e.wallets.map((w) => ({ name: w.wallet, color: SPORT_COLOR[w.sport], dash: strategyDash(w.strategy), points: w.curve }))}
                               height={200} start={0} startLabel="Break-even" signed />
              </div>
            </Card>
          </Reveal>
        )}

        {related.length > 0 && (
          <Reveal i={5} className="lg:col-span-12">
            <Card>
              <CardHeader title="Related" />
              <div className="flex flex-wrap gap-2">
                {related.map((r) => {
                  const o = all.list.find((z) => z.id === r.id);
                  const body = (
                    <>
                      <span className="text-ink-3">{r.rel}</span>
                      <span className="font-mono font-semibold text-ink">{r.id}</span>
                      {o && <span className="max-w-[28ch] truncate text-ink-2">{o.title}</span>}
                    </>
                  );
                  return known.has(r.id) ? (
                    <Link key={r.rel + r.id} href={`/experiments/${r.id.toLowerCase()}`}
                          className="inline-flex min-h-9 items-center gap-2 rounded-full bg-sunken/70 px-3.5 text-[13px] ring-1 ring-line/70 hover:bg-sunken">
                      {body}<ArrowRight size={13} className="text-ink-3" aria-hidden />
                    </Link>
                  ) : (
                    <span key={r.rel + r.id} className="inline-flex min-h-9 items-center gap-2 rounded-full bg-sunken/40 px-3.5 text-[13px] ring-1 ring-line/50">{body}</span>
                  );
                })}
              </div>
            </Card>
          </Reveal>
        )}
      </div>
    </>
  );
}
