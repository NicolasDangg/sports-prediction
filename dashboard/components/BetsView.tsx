"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle, Clock, Receipt, WarningCircle, XCircle } from "@phosphor-icons/react";
import Segmented from "./Segmented";
import type { Bet } from "@/lib/data";
import { SPORT_COLOR, SPORT_SHORT, money, pct, sportOf, when } from "@/lib/format";

type Status = "open" | "settled" | "all";
type SportFilter = "all" | "epl" | "atp";

export default function BetsView({ bets }: { bets: Bet[] }) {
  const [status, setStatus] = useState<Status>("open");
  const [sport, setSport] = useState<SportFilter>("all");

  const bySport = useMemo(() => bets.filter((b) => sport === "all" || sportOf(b.wallet) === sport), [bets, sport]);
  const shown = bySport.filter((b) => status === "all" || (status === "open" ? b.status === "open" : b.status !== "open"));
  if (status === "open") shown.sort((a, b) => a.commence_time.localeCompare(b.commence_time)); // soonest kickoff first
  const settled = shown.filter((b) => b.status === "won" || b.status === "lost");
  const pnl = settled.reduce((s, b) => s + b.pnl, 0);
  const staked = shown.reduce((s, b) => s + b.stake, 0);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Segmented
          label="Bet status"
          value={status}
          onChange={setStatus}
          options={[
            { value: "open", label: "Open", count: bySport.filter((b) => b.status === "open").length },
            { value: "settled", label: "Settled", count: bySport.filter((b) => b.status !== "open").length },
            { value: "all", label: "All", count: bySport.length },
          ]}
        />
        <Segmented
          label="Sport"
          value={sport}
          onChange={setSport}
          options={[{ value: "all", label: "Both" }, { value: "epl", label: "EPL" }, { value: "atp", label: "ATP" }]}
        />
      </div>

      <div className="mb-5 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line/80 bg-line/80 md:grid-cols-4">
        {[
          { label: "Bets", value: String(shown.length) },
          { label: "Staked", value: money(staked) },
          { label: "Settled P&L", value: settled.length ? money(pnl, { sign: true }) : "—", tone: pnl > 0 ? "text-up" : pnl < 0 ? "text-down" : "" },
          { label: "Win rate", value: settled.length ? pct(settled.filter((b) => b.status === "won").length / settled.length, false, 0) : "—" },
        ].map((s) => (
          <div key={s.label} className="bg-surface px-5 py-4">
            <p className="text-[12px] font-medium text-ink-3">{s.label}</p>
            <p className={`mt-1 text-lg font-semibold tracking-tight tabular ${s.tone ?? "text-ink"}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {shown.length === 0 ? (
        <div className="flex flex-col items-start gap-3 rounded-[1.75rem] border border-dashed border-line bg-surface/60 px-6 py-10">
          <span className="grid size-10 place-items-center rounded-xl bg-surface text-ink-2 ring-1 ring-line"><Receipt size={18} aria-hidden /></span>
          <p className="text-sm font-semibold text-ink">{status === "settled" ? "Nothing settled yet" : "No bets here"}</p>
          <p className="max-w-[52ch] text-[13px] leading-relaxed text-ink-3">
            {status === "settled"
              ? "Results arrive the morning after each match, when the agent settles them at 06:00."
              : "Try another filter. New bets are placed every morning when the model's price beats the odds by 5% or more."}
          </p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-hidden rounded-[1.75rem] border border-line/80 bg-surface shadow-diffuse md:block">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-line text-left text-[12px] text-ink-3">
                  <th className="py-3 pl-6 pr-3 font-medium">Match</th>
                  <th className="px-3 py-3 font-medium">Pick</th>
                  <th className="px-3 py-3 text-right font-medium">Odds</th>
                  <th className="px-3 py-3 text-right font-medium">Elo / market</th>
                  <th className="px-3 py-3 text-right font-medium">Stake</th>
                  <th className="py-3 pl-3 pr-6 text-right font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                <AnimatePresence initial={false}>
                  {shown.map((b) => (
                    <motion.tr
                      key={b.bet_id}
                      layout
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.18 }}
                      className="border-b border-line-soft transition-colors last:border-0 hover:bg-sunken/50"
                    >
                      <td className="py-3.5 pl-6 pr-3">
                        <div className="flex items-center gap-2.5">
                          <span className="size-2 shrink-0 rounded-full" style={{ background: SPORT_COLOR[sportOf(b.wallet)] }} aria-label={SPORT_SHORT[sportOf(b.wallet)]} />
                          <div className="min-w-0">
                            <p className="font-medium text-ink">{b.match} <FlagBadge bet={b} /></p>
                            <p className="text-[12px] text-ink-3">{b.competition} · {when(b.commence_time)}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3.5 text-ink-2">{b.pick}</td>
                      <td className="px-3 py-3.5 text-right font-mono text-ink tabular">
                        {b.odds.toFixed(2)}
                        {b.exec_book && <span className="block font-sans text-[11px] text-ink-3">{b.exec_book}</span>}
                      </td>
                      <td className="px-3 py-3.5 text-right text-ink-2 tabular">{pct(b.model_p, false, 0)} / {pct(b.market_p, false, 0)}</td>
                      <td className="px-3 py-3.5 text-right text-ink tabular">{money(b.stake)}</td>
                      <td className="py-3.5 pl-3 pr-6 text-right"><Result bet={b} /></td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <ul className="flex flex-col gap-3 md:hidden">
            {shown.map((b) => (
              <li key={b.bet_id} className="rounded-2xl border border-line/80 bg-surface p-4 shadow-diffuse">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[14px] font-semibold text-ink">{b.pick}</p>
                    <p className="text-[12px] text-ink-3">{b.match}</p>
                    <FlagBadge bet={b} />
                  </div>
                  <Result bet={b} />
                </div>
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-3 tabular">
                  <span className="inline-flex items-center gap-1.5"><span className="size-1.5 rounded-full" style={{ background: SPORT_COLOR[sportOf(b.wallet)] }} />{SPORT_SHORT[sportOf(b.wallet)]}</span>
                  <span>@ {b.odds.toFixed(2)}</span>
                  <span>{money(b.stake)}</span>
                  <span>Elo {pct(b.model_p, false, 0)} / mkt {pct(b.market_p, false, 0)}</span>
                  <span>{when(b.commence_time)}</span>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Result({ bet }: { bet: Bet }) {
  if (bet.status === "won") return <span className="inline-flex items-center gap-1 font-semibold text-up tabular"><CheckCircle size={15} weight="fill" aria-hidden />{money(bet.pnl, { sign: true })}</span>;
  if (bet.status === "lost") return <span className="inline-flex items-center gap-1 font-semibold text-down tabular"><XCircle size={15} weight="fill" aria-hidden />{money(bet.pnl, { sign: true })}</span>;
  if (bet.status === "void") return <span className="text-ink-3">Void</span>;
  if (bet.status === "unresolved") return <span className="text-ink-3" title="No result found in any source; stake refunded. Check manually.">Unresolved</span>;
  return <span className="inline-flex items-center gap-1 rounded-full bg-sunken px-2 py-0.5 text-[11px] font-medium text-ink-2"><Clock size={12} aria-hidden />Open</span>;
}

function FlagBadge({ bet }: { bet: Bet }) {
  if (!bet.flag) return null;
  return (
    <span
      title={bet.flag.note}
      className="ml-1 inline-flex items-center gap-1 rounded-full bg-down-soft px-2 py-0.5 align-middle text-[11px] font-semibold text-down"
    >
      <WarningCircle size={12} weight="fill" aria-hidden />
      {bet.flag.flag === "identity_error" ? "Identity error" : bet.flag.flag}
    </span>
  );
}
