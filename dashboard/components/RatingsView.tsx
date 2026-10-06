"use client";

import { useState } from "react";
import EloHistoryChart from "./EloHistoryChart";
import Segmented from "./Segmented";
import type { Entity, RatingsData } from "@/lib/ratings";

type Tab = "epl" | "atp";
type Surfaces = Record<string, { hard: number; clay: number; grass: number }>;

/** Default lines: the top 4 plus the biggest riser and faller of the last 10 matches. */
function defaults(entities: Entity[]) {
  const top = entities.slice(0, 4).map((e) => e.name);
  const rest = entities.filter((e) => !top.includes(e.name));
  const riser = [...rest].sort((a, b) => b.change10 - a.change10)[0];
  const faller = [...rest].sort((a, b) => a.change10 - b.change10)[0];
  return [...top, riser?.name, faller?.name].filter(Boolean) as string[];
}

export default function RatingsView({ data, surfaces }: { data: RatingsData; surfaces: Surfaces }) {
  const [tab, setTab] = useState<Tab>("epl");
  const d = data[tab];
  const color = tab === "epl" ? "var(--color-epl)" : "var(--color-atp)";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Sport" value={tab} onChange={setTab}
          options={[{ value: "epl", label: "Premier League", count: data.epl.entities.length }, { value: "atp", label: "ATP top 40", count: data.atp.entities.length }]} />
        <p className="max-w-[62ch] text-[12px] text-ink-3">
          {tab === "epl"
            ? "Ratings keep 90% of last season and move slowly, so a bad start (or a great one) takes several games to show."
            : "Overall rating. New players move fast, veterans slowly. Predictions also blend in a rating per surface."}
        </p>
      </div>

      <section className="rounded-[1.75rem] border border-line/80 bg-surface p-6 shadow-diffuse md:p-7">
        <h2 className="mb-1 text-[15px] font-semibold tracking-tight text-ink">Elo over time</h2>
        <EloHistoryChart key={tab} entities={d.entities} rows={d.rows} seasonStarts={d.seasonStarts}
                         defaults={defaults(d.entities)} chipLimit={tab === "epl" ? 20 : 24} />
      </section>

      <div className="overflow-hidden rounded-[1.75rem] border border-line/80 bg-surface shadow-diffuse">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-[13px]">
            <thead>
              <tr className="border-b border-line text-left text-[12px] text-ink-3">
                <th className="w-12 py-3 pl-6 font-medium">#</th>
                <th className="px-3 py-3 font-medium">{tab === "epl" ? "Team" : "Player"}</th>
                {tab === "epl" && <th className="px-3 py-3 text-right font-medium">Table</th>}
                <th className="px-3 py-3 font-medium">{tab === "epl" ? "Last 5" : "Last 10"}</th>
                <th className="px-3 py-3 font-medium">Last 20 ratings</th>
                <th className="px-3 py-3 text-right font-medium" title="Elo change over the last 10 matches">±10</th>
                <th className={`py-3 text-right font-medium ${tab === "atp" ? "px-3" : "pl-3 pr-6"}`}>Elo</th>
                {tab === "atp" && (
                  <>
                    <th className="hidden px-3 py-3 text-right font-medium lg:table-cell">Hard</th>
                    <th className="hidden px-3 py-3 text-right font-medium lg:table-cell">Clay</th>
                    <th className="hidden py-3 pl-3 pr-6 text-right font-medium lg:table-cell">Grass</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {d.entities.map((e, i) => {
                const s = surfaces[e.name];
                return (
                  <tr key={`${tab}-${e.name}`} className="border-b border-line-soft last:border-0 hover:bg-sunken/50">
                    <td className="py-3 pl-6 text-ink-3 tabular">{i + 1}</td>
                    <td className="px-3 py-3 font-medium text-ink">{e.name}</td>
                    {tab === "epl" && (
                      <td className="px-3 py-3 text-right text-ink-2 tabular" title={`${e.pts} pts from ${e.played} games`}>
                        {e.pos}<span className="text-ink-3">{ordinal(e.pos ?? 0)}</span>
                      </td>
                    )}
                    <td className="px-3 py-3"><FormPills form={tab === "epl" ? e.form.slice(-5) : e.form} compact={tab === "atp"} /></td>
                    <td className="px-3 py-3"><Trend values={e.spark} color={color} /></td>
                    <td className={`px-3 py-3 text-right font-mono tabular ${e.change10 > 0 ? "text-up" : e.change10 < 0 ? "text-down" : "text-ink-3"}`}>
                      {e.change10 > 0 ? "+" : e.change10 < 0 ? "−" : ""}{Math.abs(Math.round(e.change10))}
                    </td>
                    <td className={`py-3 text-right font-mono font-medium text-ink tabular ${tab === "atp" ? "px-3" : "pl-3 pr-6"}`}>{Math.round(e.elo)}</td>
                    {tab === "atp" && (
                      <>
                        <td className="hidden px-3 py-3 text-right font-mono text-ink-3 tabular lg:table-cell">{s ? Math.round(s.hard) : "—"}</td>
                        <td className="hidden px-3 py-3 text-right font-mono text-ink-3 tabular lg:table-cell">{s ? Math.round(s.clay) : "—"}</td>
                        <td className="hidden py-3 pl-3 pr-6 text-right font-mono text-ink-3 tabular lg:table-cell">{s ? Math.round(s.grass) : "—"}</td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const ordinal = (n: number) => (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th");

/** Results as lettered pills (oldest to newest), so meaning never rests on colour alone. */
function FormPills({ form, compact = false }: { form: string; compact?: boolean }) {
  const tone = { W: "bg-up-soft text-up", D: "bg-sunken text-ink-3", L: "bg-down-soft text-down" } as Record<string, string>;
  return (
    <span className="inline-flex gap-1" aria-label={`Recent results, oldest first: ${form.split("").join(" ")}`}>
      {form.split("").map((r, i) => (
        <span key={i} className={`grid place-items-center rounded-md font-mono font-semibold ${compact ? "size-[18px] text-[10px]" : "size-6 text-[11px]"} ${tone[r] ?? ""}`}>
          {r}
        </span>
      ))}
    </span>
  );
}

/** Tiny step line of the last 20 ratings: shows the ups and downs at a glance. */
function Trend({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return <span className="text-ink-3">—</span>;
  const w = 96, h = 26;
  const lo = Math.min(...values), hi = Math.max(...values);
  const x = (i: number) => 2 + (i / (values.length - 1)) * (w - 4);
  const y = (v: number) => h - 3 - ((v - lo) / (hi - lo || 1)) * (h - 6);
  const d = values.map((v, i) => (i === 0 ? `M${x(i)},${y(v)}` : `H${x(i)}V${y(v)}`)).join("");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      <circle cx={x(values.length - 1)} cy={y(values.at(-1)!)} r={2.5} fill={color} />
    </svg>
  );
}
