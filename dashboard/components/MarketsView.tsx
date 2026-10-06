"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, CheckCircle, Target } from "@phosphor-icons/react";
import Segmented from "./Segmented";
import type { Dashboard } from "@/lib/data";
import { SPORT_COLOR, SPORT_SHORT, pct, when, type Sport } from "@/lib/format";

type Match = Dashboard["upcoming"][number];
type SportFilter = "all" | Sport;
type BetFilter = "bets" | "all";

const MIN_EDGE = 0.05;

/** pages: event ids that have a match page (today's quoted ATP matches). */
export default function MarketsView({ matches, pages = [] }: { matches: Match[]; pages?: string[] }) {
  const hasPage = new Set(pages);
  const [sport, setSport] = useState<SportFilter>("all");
  const [bets, setBets] = useState<BetFilter>("bets");

  const bySport = matches.filter((m) => sport === "all" || m.sport === sport);
  const shown = bySport.filter((m) => bets === "all" || m.hasBet);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Segmented
          label="Which matches"
          value={bets}
          onChange={setBets}
          options={[
            { value: "bets", label: "With a bet", count: bySport.filter((m) => m.hasBet).length },
            { value: "all", label: "All priced", count: bySport.length },
          ]}
        />
        <Segmented
          label="Sport"
          value={sport}
          onChange={setSport}
          options={[{ value: "all", label: "Both" }, { value: "epl", label: "EPL" }, { value: "atp", label: "ATP" }]}
        />
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px] text-ink-3">
        <span className="inline-flex items-center gap-2"><i className="h-1.5 w-5 rounded-full bg-ink" />Elo probability</span>
        <span className="inline-flex items-center gap-2"><i className="h-1.5 w-5 rounded-full bg-[#b9bfc9]" />Market (vig removed)</span>
        <span>Edge = Elo probability × odds − 1. Bets need +{MIN_EDGE * 100}% or more.</span>
      </div>

      {shown.length === 0 ? (
        <div className="flex flex-col items-start gap-3 rounded-[1.75rem] border border-dashed border-line bg-surface/60 px-6 py-10">
          <span className="grid size-10 place-items-center rounded-xl bg-surface text-ink-2 ring-1 ring-line"><Target size={18} aria-hidden /></span>
          <p className="text-sm font-semibold text-ink">No matches for this filter</p>
          <p className="max-w-[52ch] text-[13px] text-ink-3">Switch to &ldquo;All priced&rdquo; to see every match the agent priced this morning.</p>
        </div>
      ) : (
        <motion.div layout className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <AnimatePresence initial={false}>
            {shown.map((m) => (
              <motion.article
                key={m.event_id}
                layout
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ type: "spring", stiffness: 260, damping: 26 }}
                className={`rounded-[1.5rem] border bg-surface p-5 shadow-diffuse ${m.hasBet ? "border-ink/15" : "border-line/80"}`}
              >
                <header className="mb-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-[12px] font-medium text-ink-3">
                      <span className="size-1.5 rounded-full" style={{ background: SPORT_COLOR[m.sport as Sport] }} aria-label={SPORT_SHORT[m.sport as Sport]} />
                      <span className="truncate">{m.competition}</span>
                    </p>
                    <p className="mt-0.5 text-[12px] text-ink-3 tabular">{when(m.commence_time)}</p>
                    {hasPage.has(m.event_id) && (
                      <Link href={`/match/${m.event_id}`} className="mt-1 inline-flex min-h-8 items-center gap-1 text-[12px] font-medium text-ink-2 underline-offset-4 hover:text-ink hover:underline">
                        Odds board, H2H, form <ArrowRight size={12} aria-hidden />
                      </Link>
                    )}
                  </div>
                  {m.hasBet && (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-ink px-2.5 py-1 text-[11px] font-semibold text-surface">
                      <CheckCircle size={12} weight="fill" aria-hidden /> Bet placed
                    </span>
                  )}
                </header>
                {m.outcomes.some((o) => typeof o.elo_p !== "number" || Number.isNaN(o.elo_p)) && (
                  <p className="mb-2 rounded-lg bg-sunken px-3 py-2 text-[12px] text-ink-2">
                    Not bettable: a player could not be matched to their history ({m.identity ?? "unresolved"}). Market prices only.
                  </p>
                )}
                <ul className="divide-y divide-line-soft">
                  {m.outcomes.map((o) => {
                    const hasElo = typeof o.elo_p === "number" && !Number.isNaN(o.elo_p);
                    const picked = m.pick === o.outcome;
                    return (
                      <li key={o.outcome} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 py-3">
                        <p className={`truncate text-[14px] ${picked ? "font-semibold text-ink" : "font-medium text-ink-2"}`}>
                          {o.outcome}
                          <span className="ml-2 font-mono text-[12px] font-normal text-ink-3">{o.odds.toFixed(2)}</span>
                        </p>
                        <span className={`row-span-2 rounded-lg px-2 py-1 text-right text-[12px] font-semibold tabular ${hasElo && (o.edge ?? 0) >= MIN_EDGE ? "bg-up-soft text-up" : "text-ink-3"}`}>
                          {hasElo && o.edge !== null ? pct(o.edge, true) : "—"}
                        </span>
                        <div className="grid gap-1">
                          {hasElo && <Bar value={o.elo_p as number} label="Elo" strong />}
                          <Bar value={o.market_p} label="Mkt" />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </motion.article>
            ))}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}

function Bar({ value, label, strong = false }: { value: number; label: string; strong?: boolean }) {
  return (
    <div className="grid grid-cols-[30px_minmax(0,1fr)_36px] items-center gap-2" title={`${label}: ${(value * 100).toFixed(1)}%`}>
      <span className="text-[11px] text-ink-3">{label}</span>
      <span className="h-1.5 overflow-hidden rounded-full bg-sunken">
        <span className={`block h-full rounded-full ${strong ? "bg-ink" : "bg-[#b9bfc9]"}`} style={{ width: `${value * 100}%` }} />
      </span>
      <span className="text-right text-[11px] text-ink-2 tabular">{Math.round(value * 100)}%</span>
    </div>
  );
}
