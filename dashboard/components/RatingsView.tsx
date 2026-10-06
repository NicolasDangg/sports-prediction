"use client";

import { useState } from "react";
import { motion } from "motion/react";
import Segmented from "./Segmented";

type Epl = { team: string; elo: number };
type Atp = { player: string; elo: number; elo_hard: number; elo_clay: number; elo_grass: number };
type Tab = "epl" | "atp";

export default function RatingsView({ epl, atp }: { epl: Epl[]; atp: Atp[] }) {
  const [tab, setTab] = useState<Tab>("epl");
  type Row = { name: string; elo: number; surfaces?: [number, number, number] };
  const rows: Row[] = tab === "epl"
    ? epl.map((r) => ({ name: r.team, elo: r.elo }))
    : atp.map((r) => ({ name: r.player, elo: r.elo, surfaces: [r.elo_hard, r.elo_clay, r.elo_grass] }));
  const lo = Math.min(...rows.map((r) => r.elo)) - 40;
  const hi = Math.max(...rows.map((r) => r.elo));
  const color = tab === "epl" ? "var(--color-epl)" : "var(--color-atp)";

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Sport" value={tab} onChange={setTab}
          options={[{ value: "epl", label: "Premier League", count: epl.length }, { value: "atp", label: "ATP top 60", count: atp.length }]} />
        <p className="text-[12px] text-ink-3">
          {tab === "epl" ? "Ratings carry over between seasons; promoted teams inherit the relegated teams' level." : "Overall rating plus one per surface. Predictions blend overall and surface 50/50."}
        </p>
      </div>

      <div className="overflow-hidden rounded-[1.75rem] border border-line/80 bg-surface shadow-diffuse">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-line text-left text-[12px] text-ink-3">
              <th className="w-12 py-3 pl-6 font-medium">#</th>
              <th className="px-3 py-3 font-medium">{tab === "epl" ? "Team" : "Player"}</th>
              <th className="hidden w-[36%] px-3 py-3 font-medium sm:table-cell"><span className="sr-only">Rating bar</span></th>
              <th className="px-3 py-3 text-right font-medium">Elo</th>
              {tab === "atp" && (
                <>
                  <th className="hidden px-3 py-3 text-right font-medium md:table-cell">Hard</th>
                  <th className="hidden px-3 py-3 text-right font-medium md:table-cell">Clay</th>
                  <th className="hidden py-3 pl-3 pr-6 text-right font-medium md:table-cell">Grass</th>
                </>
              )}
              {tab === "epl" && <th className="pr-6" />}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${tab}-${r.name}`} className="border-b border-line-soft last:border-0 hover:bg-sunken/50">
                <td className="py-3 pl-6 text-ink-3 tabular">{i + 1}</td>
                <td className="px-3 py-3 font-medium text-ink">{r.name}</td>
                <td className="hidden px-3 py-3 sm:table-cell">
                  <span className="block h-1.5 overflow-hidden rounded-full bg-sunken">
                    <motion.span
                      className="block h-full origin-left rounded-full"
                      style={{ background: color, width: `${((r.elo - lo) / (hi - lo)) * 100}%` }}
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ type: "spring", stiffness: 90, damping: 20, delay: Math.min(i, 20) * 0.02 }}
                    />
                  </span>
                </td>
                <td className="px-3 py-3 text-right font-mono font-medium text-ink tabular">{Math.round(r.elo)}</td>
                {r.surfaces?.map((v, j) => (
                  <td key={j} className={`hidden py-3 text-right font-mono text-ink-3 tabular md:table-cell ${j === 2 ? "pl-3 pr-6" : "px-3"}`}>{Math.round(v)}</td>
                ))}
                {tab === "epl" && <td className="pr-6" />}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
