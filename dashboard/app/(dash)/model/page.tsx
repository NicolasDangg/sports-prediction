import { ShieldWarning } from "@phosphor-icons/react/ssr";
import BankrollChart from "@/components/BankrollChart";
import DecisionTree from "@/components/DecisionTree";
import { DepthChart, SplitRankingChart } from "@/components/TreeCharts";
import Reveal from "@/components/Reveal";
import { Card, CardHeader, PageHeader, SportTag } from "@/components/ui";
import { loadDashboard, loadTreeExperiment } from "@/lib/data";
import { money, pct } from "@/lib/format";

const STEPS = [
  {
    title: "Rate everyone",
    body: "Each team and player has an Elo number. Winners take points from losers; upsets move more points. Tennis keeps a separate rating per surface.",
  },
  {
    title: "Turn the gap into a probability",
    body: "A 400-point gap means roughly 91% for the stronger side. In football a small model, fitted on 2012–2022, splits that into home / draw / away.",
  },
  {
    title: "Compare with the odds",
    body: "Bookmaker odds become probabilities once the bookmaker's margin is removed. Edge = Elo probability × decimal odds − 1.",
  },
  {
    title: "Bet small, only on big gaps",
    body: "If the edge is at least +5%, the wallet stakes a quarter of the Kelly amount, capped at 5% of the bankroll. Otherwise it passes.",
  },
];

export default function ModelPage() {
  const d = loadDashboard();
  const b = d.backtest;
  const tree = loadTreeExperiment();

  return (
    <>
      <PageHeader eyebrow="Strategy elo_v0 · control group" title="Model" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
        <Reveal i={0} className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader title="How a bet happens" />
            <ol className="flex flex-col gap-5">
              {STEPS.map((s, i) => (
                <li key={s.title} className="grid grid-cols-[28px_minmax(0,1fr)] gap-3">
                  <span className="grid size-7 place-items-center rounded-full bg-sunken font-mono text-[12px] font-semibold text-ink-2 ring-1 ring-line">{i + 1}</span>
                  <div>
                    <p className="text-[14px] font-semibold text-ink">{s.title}</p>
                    <p className="mt-1 text-[13px] leading-relaxed text-ink-3">{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        </Reveal>

        <div className="flex flex-col gap-4 lg:col-span-7 lg:gap-5">
          <Reveal i={1}>
            <Card>
              <CardHeader
                title="Backtest scores"
                hint="Log loss on test years the model never saw during tuning. Lower is better; confident wrong predictions are punished hard."
              />
              {b ? (
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                  {(["epl", "atp"] as const).map((k) => {
                    const s = b[k];
                    const rows = [
                      { name: s.baseline_label, v: s.log_loss.baseline },
                      { name: "Elo", v: s.log_loss.elo },
                      { name: "Bookmaker", v: s.log_loss.bookmaker },
                    ];
                    const best = Math.min(...rows.map((r) => r.v));
                    const worst = Math.max(...rows.map((r) => r.v));
                    return (
                      <div key={k}>
                        <div className="flex items-center justify-between">
                          <SportTag sport={k} />
                          <span className="text-[11px] text-ink-3 tabular">{s.matches.toLocaleString()} matches</span>
                        </div>
                        <ul className="mt-3 flex flex-col gap-2.5">
                          {rows.map((r) => (
                            <li key={r.name}>
                              <div className="flex justify-between text-[12px]">
                                <span className={r.v === best ? "font-semibold text-ink" : "text-ink-2"}>{r.name}</span>
                                <span className={`font-mono tabular ${r.v === best ? "font-semibold text-ink" : "text-ink-3"}`}>{r.v.toFixed(4)}</span>
                              </div>
                              {/* bar length = how far below the worst score (more = better) */}
                              <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-sunken">
                                <span className={`block h-full rounded-full ${r.v === best ? "bg-ink" : "bg-[#b9bfc9]"}`}
                                      style={{ width: `${12 + ((worst - r.v) / (worst - best || 1)) * 88}%` }} />
                              </span>
                            </li>
                          ))}
                        </ul>
                        <p className="mt-3 text-[12px] text-ink-3 tabular">
                          Wallet: {s.wallet.bets.toLocaleString()} bets, ROI {pct(s.wallet.roi, true)}, ended {money(s.wallet.final_bankroll)}
                        </p>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-[13px] text-ink-3">Run backtest.py to generate results/summary.json.</p>
              )}
            </Card>
          </Reveal>

          <Reveal i={2}>
            <Card className="border-[#f0d9a8] bg-[#fffaf0]">
              <div className="flex gap-4">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface text-[#9a6a00] ring-1 ring-[#f0d9a8]">
                  <ShieldWarning size={20} weight="duotone" aria-hidden />
                </span>
                <div>
                  <h2 className="text-[15px] font-semibold tracking-tight text-ink">Don&apos;t tune against the test years</h2>
                  <p className="mt-1.5 max-w-[64ch] text-[13px] leading-relaxed text-ink-2">
                    Every time a setting is tweaked and re-checked on the same test years, the strategy quietly fits those years.
                    Try enough tweaks and one will look profitable by luck. That&apos;s <b className="font-semibold">overfitting</b>.
                    The live wallet is the honest judge: its bets are placed before each match and can&apos;t be adjusted afterwards.
                    Trust it over any backtest number.
                  </p>
                </div>
              </div>
            </Card>
          </Reveal>
        </div>

        <Reveal i={3} className="lg:col-span-8">
          <Card className="h-full">
            <CardHeader title="Backtest bankroll" hint="What the same rules would have done, replayed match by match through the test years." />
            {b && (
              <BankrollChart
                height={250}
                series={[
                  { name: "Premier League · elo_v0", color: "var(--color-epl)", points: d.backtestCurves.epl },
                  { name: "ATP Tour · elo_v0", color: "var(--color-atp)", points: d.backtestCurves.atp },
                ]}
              />
            )}
          </Card>
        </Reveal>

        <Reveal i={4} className="lg:col-span-4">
          <Card className="h-full">
            <CardHeader title="Settings" hint="Chosen on the training years only." />
            {b && (
              <dl className="divide-y divide-line-soft text-[13px]">
                {[
                  ["EPL K-factor", b.epl.params.k],
                  ["EPL home advantage", `${b.epl.params.home_adv} pts`],
                  ["EPL season carry-over", pct(b.epl.params.carryover, false, 0)],
                  ["ATP K scale", b.atp.params.k_scale],
                  ["ATP surface weight", pct(b.atp.params.surface_weight, false, 0)],
                  ["Minimum edge (live)", "+5%"],
                  ["Stake", "¼ Kelly, max 5%"],
                ].map(([k, v]) => (
                  <div key={String(k)} className="flex justify-between gap-4 py-2.5 first:pt-0 last:pb-0">
                    <dt className="text-ink-3">{k}</dt>
                    <dd className="font-mono text-ink tabular">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>
        </Reveal>
      </div>

      {tree && (
        <section className="mt-10">
          <div className="mb-5 flex flex-col gap-1">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-3">Experiment {tree.experiment} · ATP · not shipped</p>
            <h2 className="text-[22px] font-semibold tracking-tighter text-ink">Decision tree: split, split, split</h2>
            <p className="max-w-[72ch] text-[13px] leading-relaxed text-ink-3">
              A tree asks one yes/no question at a time, always the one that leaves the two groups most <em>pure</em>{" "}
              (Gini impurity: 0 = everyone in the group won, 0.5 = coin flip). Trained on {tree.train[0].slice(0, 4)}–{tree.train[1].slice(0, 4)} ({tree.n_train.toLocaleString()} matches,
              each also mirrored with the players swapped), depth chosen on {tree.validation[0].slice(0, 4)}–{tree.validation[1].slice(0, 4)}. Test years untouched.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
            <Reveal i={5} className="lg:col-span-5">
              <Card className="h-full">
                <CardHeader title="Which variable splits best?" hint="Each variable's single best yes/no question, ranked by how much purer it makes the groups. This picks the root of the tree." />
                <SplitRankingChart ranking={tree.split_ranking} />
              </Card>
            </Reveal>
            <Reveal i={6} className="lg:col-span-7">
              <Card className="h-full">
                <CardHeader title="Does the tree beat Elo?" hint={`Validation log loss on ${tree.n_validation.toLocaleString()} matches. Lower is better.`} />
                <ul className="flex flex-col gap-2.5">
                  {(() => {
                    const vals = tree.comparison.map((c) => c.val_log_loss);
                    const best = Math.min(...vals), worst = Math.max(...vals);
                    return tree.comparison.map((c) => (
                      <li key={c.model}>
                        <div className="flex justify-between text-[12px]">
                          <span className={c.val_log_loss === best ? "font-semibold text-ink" : "text-ink-2"}>{c.model}</span>
                          <span className="font-mono text-ink-2 tabular">{c.val_log_loss.toFixed(4)}</span>
                        </div>
                        <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-sunken">
                          <span className={`block h-full rounded-full ${c.model.startsWith("Decision") ? "bg-epl" : c.val_log_loss === best ? "bg-ink" : "bg-[#b9bfc9]"}`}
                                style={{ width: `${8 + ((worst - c.val_log_loss) / (worst - best || 1)) * 92}%` }} />
                        </span>
                      </li>
                    ));
                  })()}
                </ul>
                <div className="mt-6 border-t border-line-soft pt-5">
                  <p className="mb-2 text-[13px] font-medium text-ink">How deep should it grow?</p>
                  <DepthChart rows={tree.depth_search} chosen={tree.chosen_depth} />
                </div>
              </Card>
            </Reveal>

            <Reveal i={7} className="lg:col-span-12">
              <Card>
                <CardHeader
                  title="The tree, first three levels"
                  hint="Read from the top: answer each question, follow yes (left) or no (right). Leaves show how often Player 1 won in that group. The bar under each box is that win share."
                />
                <DecisionTree tree={tree.tree} />
              </Card>
            </Reveal>

            <Reveal i={8} className="lg:col-span-12">
              <Card className="border-[#d6e5f8] bg-[#f6f9fe]">
                <h3 className="text-[15px] font-semibold tracking-tight text-ink">What this tells us</h3>
                <ul className="mt-2 flex max-w-[80ch] list-disc flex-col gap-1.5 pl-5 text-[13px] leading-relaxed text-ink-2">
                  <li><b>The Elo gap is the strongest single predictor.</b> It wins the root split and carries {Math.round((tree.importance[0]?.importance ?? 0) * 100)}% of the tree&apos;s total purity gain. Rankings come next but add little once Elo is known.</li>
                  <li><b>Recent form (last 10) adds almost nothing</b> beyond Elo, which already summarises results. The same lesson as the Man United case.</li>
                  <li><b>The tree only matches a calibrated Elo.</b> It isn&apos;t better, and the bookmaker is still far ahead. More splits on the same information won&apos;t close that gap; it needs information Elo doesn&apos;t have.</li>
                </ul>
              </Card>
            </Reveal>
          </div>
        </section>
      )}
    </>
  );
}
